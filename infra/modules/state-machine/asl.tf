locals {
  # Retry config applied to all Lambda Task states
  lambda_retry = [
    {
      ErrorEquals     = ["Lambda.ServiceException", "Lambda.AWSLambdaException", "Lambda.TooManyRequestsException", "Lambda.SdkClientException"]
      IntervalSeconds = 2
      MaxAttempts     = 3
      BackoffRate     = 2
    }
  ]

  # Catch-all: preserve input, append error, route to MarkJobFailed
  std_catch = [
    {
      ErrorEquals = ["States.ALL"]
      ResultPath  = "$.error"
      Next        = "MarkJobFailed"
    }
  ]

  sfn_definition = jsonencode({
    Comment = "Rosetta IaC translation pipeline"
    StartAt = "Preflight"
    States = {

      # ── 1. Unzip, filter, upload to staging ──────────────────────────────
      Preflight = {
        Type           = "Task"
        Resource       = aws_lambda_function.workers["preflight"].arn
        ResultPath     = "$.preflightResult"
        TimeoutSeconds = 180
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        Next           = "CheckIfSAMTarget"
      }

      # ── Route: only SAM target needs the serverless compat check ─────────
      CheckIfSAMTarget = {
        Type = "Choice"
        Choices = [
          {
            Variable     = "$.targetLang"
            StringEquals = "sam"
            Next         = "CompatibilityCheck"
          }
        ]
        Default = "DependencyMap"
      }

      # ── 2. SAM-only: verify all resources are serverless ─────────────────
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
            Next          = "DependencyMap"
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

      # ── 3. Build cross-file dependency / symbol graph ────────────────────
      DependencyMap = {
        Type           = "Task"
        Resource       = aws_lambda_function.workers["dependency_map"].arn
        ResultPath     = "$.depGraph"
        TimeoutSeconds = 300
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        Next           = "TranslateFiles"
      }

      # ── 4. Translate each file in parallel (max 10 concurrent) ───────────
      TranslateFiles = {
        Type           = "Map"
        ItemsPath      = "$.preflightResult.fileList"
        MaxConcurrency = 10
        Parameters = {
          "file.$"            = "$$.Map.Item.Value"
          "userId.$"          = "$.userId"
          "jobId.$"           = "$.jobId"
          "sourceLang.$"      = "$.sourceLang"
          "sourceCdkLang.$"   = "$.sourceCdkLang"
          "targetLang.$"      = "$.targetLang"
          "targetCdkLang.$"   = "$.targetCdkLang"
          "artifactsBucket.$" = "$.artifactsBucket"
          "depGraph.$"        = "$.depGraph"
          "retryCount.$"      = "$.retryCount"
          useOpus             = false
        }
        Iterator = {
          StartAt = "TranslateFile"
          States = {
            TranslateFile = {
              Type           = "Task"
              Resource       = aws_lambda_function.workers["translate"].arn
              TimeoutSeconds = 180
              Retry          = local.lambda_retry
              End            = true
            }
          }
        }
        ResultPath = "$.translateResults"
        Catch      = local.std_catch
        Next       = "Validate"
      }

      # ── 5. Validate generated output ─────────────────────────────────────
      Validate = {
        Type           = "Task"
        Resource       = aws_lambda_function.workers["validate"].arn
        ResultPath     = "$.validateResult"
        TimeoutSeconds = 300
        Retry          = local.lambda_retry
        Catch          = local.std_catch
        Next           = "ValidationDecision"
      }

      # ── Route: validation result → package or package-with-warnings ───────
      # Retry loop with Bedrock escalation will be added when wiring real calls.
      ValidationDecision = {
        Type = "Choice"
        Choices = [
          {
            Variable      = "$.validateResult.ok"
            BooleanEquals = true
            Next          = "Package"
          }
        ]
        Default = "PackageWithWarnings"
      }

      # ── 6a. Zip output and mark COMPLETED ────────────────────────────────
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

      # ── 6b. Zip output and mark COMPLETED_WITH_WARNINGS ──────────────────
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

      # ── Error handler: update DDB status → FAILED ────────────────────────
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
