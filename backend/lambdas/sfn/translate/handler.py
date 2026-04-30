"""
Translate a single IaC file using Amazon Bedrock Claude Sonnet 4.6.
On the 3rd retry the caller sets useOpus=true and we escalate to Opus 4.7.
"""
import json
import os

import boto3
from botocore.config import Config

from ddb_utils import update_job_step, add_job_tokens

s3      = boto3.client("s3", config=Config(signature_version="s3v4"))
ddb     = boto3.resource("dynamodb")
bedrock = boto3.client("bedrock-runtime", region_name=os.environ.get("AWS_REGION", "us-east-1"))

JOBS_TABLE         = os.environ["JOBS_TABLE"]
TRANSLATE_MODEL_ID = os.environ.get("TRANSLATE_MODEL_ID", "us.anthropic.claude-sonnet-4-6-v1:0")
OPUS_MODEL_ID      = os.environ.get("OPUS_MODEL_ID",      "us.anthropic.claude-opus-4-7-v1:0")

# ── Language metadata ──────────────────────────────────────────────────────────

LANG_LABELS = {
    "terraform":        "Terraform (HCL)",
    "cloudformation":   "AWS CloudFormation (YAML)",
    "sam":              "AWS SAM (YAML with Transform: AWS::Serverless-2016-10-31)",
    "cdk_typescript":   "AWS CDK (TypeScript)",
    "cdk_python":       "AWS CDK (Python)",
    "cdk_java":         "AWS CDK (Java)",
    "cdk_csharp":       "AWS CDK (C#)",
    "cdk_go":           "AWS CDK (Go)",
}

OUTPUT_EXTENSIONS = {
    "terraform":        ".tf",
    "cloudformation":   ".yaml",
    "sam":              ".yaml",
    "cdk_typescript":   ".ts",
    "cdk_python":       ".py",
    "cdk_java":         ".java",
    "cdk_csharp":       ".cs",
    "cdk_go":           ".go",
}

TARGET_RULES = {
    "terraform": """\
9. Use the hashicorp/aws provider. All resource type names must use the aws_ prefix (e.g., aws_s3_bucket, aws_lambda_function, aws_dynamodb_table).
10. IAM managed policies: always use a separate aws_iam_role_policy_attachment resource — never the managed_policy_arns argument on aws_iam_role.
11. Lambda functions without a code artifact in the source: set filename = "placeholder.zip" and add lifecycle { ignore_changes = [filename, source_code_hash] } with a comment explaining the code must be provided separately.
12. Data sources (aws_caller_identity, aws_region, etc.): only declare them if they are referenced in the output. Never declare an unused data source.
13. Only include provider and terraform blocks if this is clearly the entry-point file of the project.""",

    "cloudformation": """\
9. Use YAML. Always include AWSTemplateFormatVersion: '2010-09-09' at the top.
10. CRITICAL — file structure: Terraform's file separation (variables.tf, outputs.tf, main.tf) does NOT map to CloudFormation files. Every CloudFormation template MUST contain a Resources section. When translating a Terraform module directory, merge variables.tf → Parameters, main.tf → Resources, outputs.tf → Outputs into a SINGLE .yaml file. Never produce a CloudFormation template that has only Parameters or only Outputs and no Resources.
11. Intrinsic functions: prefer !Ref for same-resource references, !GetAtt for attributes, !Sub for string interpolation with multiple tokens. Avoid !Sub when plain !Ref suffices.
12. IAM: place short policies inline on the role (Policies:) for ≤3 statements; use AWS::IAM::ManagedPolicy + AttachRolePolicies for larger or reusable policies.
13. Lambda without a code artifact in the source: use ZipFile with a stub handler comment, or S3Bucket/S3Key placeholders with a comment that the code must be provided separately.
14. Outputs: always include an Export.Name using !Sub '${AWS::StackName}-<LogicalId>' so the value can be imported by other stacks.
15. Use DependsOn only when CloudFormation cannot infer the dependency from a !Ref or !GetAtt — do not add it redundantly.
16. Stateful resources (AWS::DynamoDB::Table, AWS::S3::Bucket, AWS::RDS::*): always add DeletionPolicy: Retain and UpdateReplacePolicy: Retain to prevent accidental data loss.
17. Do not add security hardening rules (VPC placement, KMS encryption, S3 access logging) unless they were explicitly present in the source template — translate what exists, not what cfn-guard recommends.""",

    "sam": """\
9. CRITICAL — file structure: same rule as CloudFormation. Every SAM template MUST have a Resources section. Merge variables.tf/outputs.tf into the same .yaml file as the resources. Never produce a template with only Parameters or only Outputs.
10. Always include AWSTemplateFormatVersion: '2010-09-09' AND Transform: AWS::Serverless-2016-10-31.
10. Use AWS::Serverless:: resource types wherever a SAM equivalent exists (Function, Api, HttpApi, SimpleTable, StateMachine, LayerVersion, Application).
11. IAM: always prefer SAM policy templates over inline statements (DynamoDBCrudPolicy, DynamoDBReadPolicy, S3CrudPolicy, SQSPollerPolicy, LambdaInvokePolicy, etc.). Only fall back to inline SAM::Policy when no template covers the permission.
12. Use the Globals section for properties shared across all functions (Runtime, Timeout, MemorySize, Environment, Architectures) to avoid repetition.
13. Lambda without code in the source: use InlineCode with a stub handler, or add a comment that the deployment package must be provided via CodeUri.
14. All resources MUST be serverless — no EC2, RDS (non-serverless), ElastiCache, or NAT Gateways.""",

    "cdk_typescript": """\
9. Import from 'aws-cdk-lib' (core) and 'aws-cdk-lib/aws-<service>' sub-modules. Never import from the old '@aws-cdk/*' scoped packages.
10. Export a single Stack class extending cdk.Stack. All resources must be defined in the constructor.
11. Use L2 constructs wherever available (s3.Bucket, lambda.Function, dynamodb.Table, iam.Role). Fall back to L1 (CfnBucket, CfnFunction, etc.) only when an L2 property is unavailable.
12. IAM: use grant methods on L2 constructs (bucket.grantRead(fn), table.grantWriteData(fn)) instead of manually writing policy statements when the source uses simple resource-to-resource permissions.
13. Use enum values, not raw strings: s3.BucketEncryption.S3_MANAGED, dynamodb.AttributeType.STRING, lambda.Runtime.PYTHON_3_13, cdk.RemovalPolicy.RETAIN.
14. Lambda without code: use lambda.Code.fromAsset('placeholder') with a comment that the asset path must be updated.
15. For timeouts and sizes: use cdk.Duration.seconds(30), cdk.Size.mebibytes(256) — never raw numbers where a typed helper exists.""",

    "cdk_python": """\
9. Import pattern: 'import aws_cdk as cdk' plus 'from aws_cdk import aws_s3 as s3, aws_lambda as lambda_, aws_dynamodb as dynamodb, aws_iam as iam' etc.
10. Define a single Stack class extending Stack. All resources in __init__(self, scope, id, **kwargs).
11. Use L2 constructs wherever available. Fall back to L1 (CfnBucket, etc.) only when necessary.
12. IAM: use grant methods on L2 constructs (bucket.grant_read(fn), table.grant_write_data(fn)) for simple permissions instead of manual policy statements.
13. Use enum values: s3.BucketEncryption.S3_MANAGED, dynamodb.AttributeType.STRING, lambda_.Runtime.PYTHON_3_13, cdk.RemovalPolicy.RETAIN.
14. Lambda without code: use lambda_.Code.from_asset("placeholder") with a comment.
15. Duration and Size: use Duration.seconds(30), Size.mebibytes(256). Never raw numbers where a typed helper exists.""",

    "cdk_java": """\
9. Imports: 'software.amazon.awscdk.*' for core, 'software.amazon.awscdk.services.<service>.*' for each AWS service.
10. All constructs use the Builder pattern: Bucket.Builder.create(this, "MyBucket").versioned(true).build().
11. Define a class extending Stack. Constructor signature: public MyStack(final Construct scope, final String id, final StackProps props).
12. Use L2 constructs wherever available.
13. IAM: use grant methods (bucket.grantRead(fn), table.grantWriteData(fn)) for simple permissions.
14. Enums: BucketEncryption.S3_MANAGED, AttributeType.STRING, Runtime.PYTHON_3_13, RemovalPolicy.RETAIN.
15. Duration and Size: Duration.seconds(30), Size.mebibytes(256). Use typed helpers, never raw numbers.""",

    "cdk_csharp": """\
9. Imports: 'using Amazon.CDK;' for core, 'using Amazon.CDK.AWS.<Service>;' for each service.
10. All constructs use props objects: new Bucket(this, "MyBucket", new BucketProps { Versioned = true }).
11. Define a class extending Stack. Constructor: public MyStack(Construct scope, string id, IStackProps props = null) : base(scope, id, props).
12. Use L2 constructs wherever available.
13. IAM: use grant methods (bucket.GrantRead(fn), table.GrantWriteData(fn)) for simple permissions.
14. Enums: BucketEncryption.S3_MANAGED, AttributeType.STRING, Runtime.PYTHON_3_13, RemovalPolicy.RETAIN.
15. Duration and Size: Duration.Seconds(30), Size.Mebibytes(256). Use typed helpers.""",

    "cdk_go": """\
9. Imports: 'github.com/aws/aws-cdk-go/awscdk/v2' for core, 'github.com/aws/aws-cdk-go/awscdk/v2/aws<service>' for each service.
10. All string/number/bool props must be wrapped: jsii.String("value"), jsii.Number(30), jsii.Bool(true). Never pass raw literals to props.
11. Define a constructor function: func NewMyStack(scope constructs.Construct, id string, props *MyStackProps) awscdk.Stack.
12. Use L2 constructs wherever available.
13. IAM: use grant methods (bucket.GrantRead(fn), table.GrantWriteData(fn)) for simple permissions.
14. Enums are package-level vars: awss3.BucketEncryption_S3_MANAGED, awsdynamodb.AttributeType_STRING, awslambda.Runtime_PYTHON_3_13().
15. Duration and Size: awscdk.Duration_Seconds(jsii.Number(30)), awscdk.Size_Mebibytes(jsii.Number(256)).""",
}

SYSTEM_PROMPT_TMPL = """\
You are an expert AWS infrastructure engineer specialising in IaC translation.

Task: translate the source file from {source_label} to {target_label}.

General rules — follow exactly:
1. Output ONLY the translated file content. No markdown fences, no explanations, no preamble, no trailing commentary.
2. Convert resource identifiers to the naming convention of the TARGET format:
   - Terraform: snake_case (e.g., data_bucket, jobs_table, processor_role)
   - CloudFormation/SAM: PascalCase (e.g., DataBucket, JobsTable)
   - CDK: camelCase for variables, PascalCase for construct IDs
3. Preserve all configuration values exactly: memory sizes, timeouts, environment variables, ARNs, tags, retention periods.
4. Use idiomatic {target_label} syntax and best practices throughout.
5. Include every resource, variable, parameter, and output from the source — omit nothing.
6. For cross-file references (variables declared elsewhere, data sources, imports), create appropriate lookups in the target format.
7. Substitute AWS account/region intrinsics correctly for the target format.
8. Only declare helper resources (data sources, locals) that are actually referenced in the output — no unused declarations.
9. You are TRANSLATING the source template into a standalone equivalent. Do NOT reference the source format's infrastructure (e.g., never use aws_cloudformation_stack, no Terraform remote state lookups, no CDK fromLookup calls). The output must be self-contained.
{target_rules}"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def lang_key(lang: str, cdk_lang: str | None) -> str:
    return f"cdk_{cdk_lang}" if lang == "cdk" and cdk_lang else lang


def output_path(source_path: str, target_key: str) -> str:
    base = os.path.splitext(source_path)[0]
    return base + OUTPUT_EXTENSIONS.get(target_key, ".tf")


def build_messages(source_content: str, file_info: dict, event: dict, retry_errors: list) -> tuple[str, str]:
    src_key = lang_key(event["sourceLang"], event.get("sourceCdkLang"))
    tgt_key = lang_key(event["targetLang"], event.get("targetCdkLang"))
    src_label = LANG_LABELS.get(src_key, src_key)
    tgt_label = LANG_LABELS.get(tgt_key, tgt_key)

    system = SYSTEM_PROMPT_TMPL.format(
        source_label=src_label,
        target_label=tgt_label,
        target_rules=TARGET_RULES.get(tgt_key, ""),
    )

    dep_graph = event.get("depGraph") or {}
    symbol_section = ""
    if dep_graph.get("symbolTable"):
        symbol_section = (
            "\n\nProject-wide symbol table — all identifiers across every file in this project:\n"
            + json.dumps(dep_graph["symbolTable"], indent=2)
            + "\n\nWhen translating THIS file:\n"
            "- Identifiers defined in this file: translate them normally.\n"
            "- Identifiers referenced but NOT defined in this file: they exist in another translated file — reference them correctly (e.g., var.name in Terraform, !Ref LogicalId in CFN, imported variable in CDK). Do NOT redefine them here.\n"
            "- Do not duplicate definitions that belong entirely to other files."
        )

    error_section = ""
    if retry_errors:
        error_section = (
            "\n\nPrevious translation attempt had these validation errors — fix them in this attempt:\n"
            + "\n".join(f"- {e}" for e in retry_errors)
        )

    user_msg = (
        f"File: {file_info['path']}\n"
        f"Source format: {src_label}\n"
        f"Target format: {tgt_label}"
        f"{symbol_section}"
        f"{error_section}"
        f"\n\nSource content:\n{source_content}"
        f"\n\nTranslate to {tgt_label}:"
    )

    return system, user_msg, tgt_key


# ── Handler ────────────────────────────────────────────────────────────────────

def handler(event, context):
    user_id   = event["userId"]
    job_id    = event["jobId"]
    file_info = event["file"]
    bucket    = event["artifactsBucket"]
    use_opus  = event.get("useOpus", False)

    update_job_step(ddb, JOBS_TABLE, user_id, job_id, "TRANSLATE")

    source_content = (
        s3.get_object(Bucket=bucket, Key=file_info["s3Key"])["Body"]
        .read()
        .decode("utf-8", errors="replace")
    )

    # Collect validation errors from a previous retry if present
    retry_errors = []
    if event.get("validateResult") and not event["validateResult"].get("ok"):
        retry_errors = [e.get("msg", str(e)) for e in event["validateResult"].get("errors", [])]

    system_prompt, user_msg, tgt_key = build_messages(source_content, file_info, event, retry_errors)

    model_id = OPUS_MODEL_ID if use_opus else TRANSLATE_MODEL_ID

    response = bedrock.converse(
        modelId=model_id,
        system=[{"text": system_prompt}],
        messages=[{"role": "user", "content": [{"text": user_msg}]}],
        inferenceConfig={"maxTokens": 8192},
    )

    translated = response["output"]["message"]["content"][0]["text"].strip()
    tokens_in  = response["usage"]["inputTokens"]
    tokens_out = response["usage"]["outputTokens"]

    out_name = output_path(file_info["path"], tgt_key)
    out_key  = f"staging/{user_id}/{job_id}/out/{out_name}"
    s3.put_object(Bucket=bucket, Key=out_key, Body=translated.encode("utf-8"))

    add_job_tokens(ddb, JOBS_TABLE, user_id, job_id, tokens_in, tokens_out)

    return {"path": out_name, "outKey": out_key, "tokensIn": tokens_in, "tokensOut": tokens_out}
