"""Write the new unit-aware ASL definition."""
import os

path = os.path.join(os.path.dirname(__file__), "..",
                    "infra", "modules", "state-machine", "asl.tf")

content = """locals {
  lambda_retry = [
    {
      ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.TooManyRequestsException", "Lambda.SdkClientException"]
      IntervalSeconds = 2
      MaxAttempts     = 3
      BackoffRate     = 2
    }
  ]

  std_catch = [
    {
      ErrorEquals = ["States.ALL"]
      ResultPath  = "$.error"
      Next        = "MarkJobFailed"
    }
  ]

  sfn_definition = jsonencode({
    Comment = "Rosetta IaC translation pipeline - unit-aware"
    StartAt = "Preflight"
    States = {

      Preflight = {
        Type           = "Task"
        Resource       = aws_lambda_function.workers["preflight"].arn
        ResultPath     = "$.preflightResult"
        TimeoutSeconds = 180
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        Next           = "CheckIfSAMTarget"
      }

      CheckIfSAMTarget = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.targetLang"
            StringEquals = "sam"
            Next         = "CompatibilityCheck"
          }
        ]
        Default = "PlanTranslation"
      }

      CompatibilityCheck = {
        Type           = "Task"
        Resource       = aws_lambda_function.workers["compatibility_check"].arn
        ResultPath     = "$.compatResult"
        TimeoutSeconds = 60
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        Next           = "CheckCompatResult"
      }

      CheckCompatResult = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.compatResult.compatible"
            BooleanEquals = true
            Next          = "PlanTranslation"
          }
        ]
        Default = "MarkJobIncompatible"
      }

      MarkJobIncompatible = {
        Type     = "Task"
        Resource = aws_lambda_function.workers["mark_failed"].arn
        Parameters = {
          "userId.$"  = "$.userId"
          "jobId.$"   = "$.jobId"
          errorMsg    = "Target SAM requires all resources to be serverless-compatible."
        }
        Retry = local.lambda_retry
        End   = true
      }

      PlanTranslation = {
        Type           = "Task"
        Resource       = aws_lambda_function.workers["plan_translation"].arn
        ResultPath     = "$.planResult"
        TimeoutSeconds = 120
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        Next           = "TranslateUnits"
      }

      TranslateUnits = {
        Type           = "Map"
        ItemsPath      = "$.planResult.units"
        MaxConcurrency = 5
        Parameters = {
          "unit.$"            = "$$.Map.Item.Value"
          "userId.$"          = "$.userId"
          "jobId.$"           = "$.jobId"
          "sourceLang.$"      = "$.sourceLang"
          "sourceCdkLang.$"   = "$.sourceCdkLang"
          "targetLang.$"      = "$.targetLang"
          "targetCdkLang.$"   = "$.targetCdkLang"
          "artifactsBucket.$" = "$.artifactsBucket"
          "depGraph.$"        = "$.planResult"
          "retryCount.$"      = "$.retryCount"
          "useOpus.$"         = "$.useOpus"
          "validateResult.$"  = "$.validateResult"
        }
        Iterator = {
          StartAt = "TranslateUnit"
          States = {
            TranslateUnit = {
              Type           = "Task"
              Resource       = aws_lambda_function.workers["translate"].arn
              TimeoutSeconds = 300
              Retry          = local.lambda_retry
              End            = true
            }
          }
        }
        ResultPath = "$.translateResults"
        Catch      = local.std_catch
        Next       = "Validate"
      }

      Validate = {
        Type           = "Task"
        Resource       = aws_lambda_function.workers["validate"].arn
        ResultPath     = "$.validateResult"
        TimeoutSeconds = 300
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        Next           = "ValidationDecision"
      }

      ValidationDecision = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.validateResult.ok"
            BooleanEquals = true
            Next          = "Package"
          },
          {
            And = [
              { Variable = "$.validateResult.ok", BooleanEquals = false },
              { Variable = "$.retryCount",        NumericLessThan = 2   }
            ]
            Next = "IncrementRetry"
          },
          {
            And = [
              { Variable = "$.validateResult.ok", BooleanEquals = false },
              { Variable = "$.retryCount",        NumericEquals = 2     }
            ]
            Next = "IncrementRetryOpus"
          }
        ]
        Default = "PackageWithWarnings"
      }

      IncrementRetry = {
        Type = "Pass"
        Parameters = {
          "userId.$"           = "$.userId"
          "jobId.$"            = "$.jobId"
          "sourceLang.$"       = "$.sourceLang"
          "sourceCdkLang.$"    = "$.sourceCdkLang"
          "targetLang.$"       = "$.targetLang"
          "targetCdkLang.$"    = "$.targetCdkLang"
          "artifactsBucket.$"  = "$.artifactsBucket"
          "preflightResult.$"  = "$.preflightResult"
          "planResult.$"       = "$.planResult"
          "validateResult.$"   = "$.validateResult"
          "retryCount.$"       = "States.MathAdd($.retryCount, 1)"
          useOpus              = false
        }
        Next = "TranslateUnits"
      }

      IncrementRetryOpus = {
        Type = "Pass"
        Parameters = {
          "userId.$"           = "$.userId"
          "jobId.$"            = "$.jobId"
          "sourceLang.$"       = "$.sourceLang"
          "sourceCdkLang.$"    = "$.sourceCdkLang"
          "targetLang.$"       = "$.targetLang"
          "targetCdkLang.$"    = "$.targetCdkLang"
          "artifactsBucket.$"  = "$.artifactsBucket"
          "preflightResult.$"  = "$.preflightResult"
          "planResult.$"       = "$.planResult"
          "validateResult.$"   = "$.validateResult"
          "retryCount.$"       = "States.MathAdd($.retryCount, 1)"
          useOpus              = true
        }
        Next = "TranslateUnits"
      }

      Package = {
        Type     = "Task"
        Resource = aws_lambda_function.workers["package"].arn
        Parameters = {
          "userId.$"           = "$.userId"
          "jobId.$"            = "$.jobId"
          "artifactsBucket.$"  = "$.artifactsBucket"
          status               = "COMPLETED"
        }
        TimeoutSeconds = 180
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        End            = true
      }

      PackageWithWarnings = {
        Type     = "Task"
        Resource = aws_lambda_function.workers["package"].arn
        Parameters = {
          "userId.$"           = "$.userId"
          "jobId.$"            = "$.jobId"
          "artifactsBucket.$"  = "$.artifactsBucket"
          status               = "COMPLETED_WITH_WARNINGS"
        }
        TimeoutSeconds = 180
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        End            = true
      }

      MarkJobFailed = {
        Type     = "Task"
        Resource = aws_lambda_function.workers["mark_failed"].arn
        Retry = [
          {
            ErrorEquals     = ["Lambda.ServiceException", "Lambda.TooManyRequestsException"]
            IntervalSeconds = 1
            MaxAttempts     = 2
          }
        ]
        End = true
      }
    }
  })
}
"""

with open(path, "w", encoding="utf-8") as f:
    f.write(content)
print("ASL written OK, lines:", len(content.splitlines()))
