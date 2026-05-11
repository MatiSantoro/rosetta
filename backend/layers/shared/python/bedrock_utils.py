"""
Bedrock helpers — throttling-aware converse() wrapper.

Bedrock imposes both per-minute (TPM) and per-day (TPD) token quotas at the
account level, shared across all users. When multiple jobs run concurrently or
a single large job exhausts the daily budget, Bedrock returns ThrottlingException.

The SFN lambda_retry policy only catches Lambda *service* errors (e.g. timeout,
out-of-memory). A ThrottlingException thrown from inside application code is an
unhandled Lambda error that SFN does NOT retry automatically — the state machine
catches it as a generic error and routes to MarkJobFailed.

This wrapper retries ThrottlingException and ServiceUnavailableException with
exponential back-off + full jitter so that concurrent requests naturally spread out.
"""
import random
import time

from botocore.exceptions import ClientError

# Throttling error codes returned by Bedrock
_THROTTLE_CODES = frozenset(
    {
        "ThrottlingException",
        "ServiceUnavailableException",
        "ModelStreamErrorException",
        "InternalServerException",
    }
)

_DEFAULT_MAX_RETRIES = 6
_BASE_DELAY_S = 2.0
_MAX_DELAY_S = 60.0


def bedrock_converse(bedrock_client, *, max_retries: int = _DEFAULT_MAX_RETRIES, **kwargs):
    """
    Drop-in wrapper around bedrock_client.converse() with retry logic.

    All keyword arguments are forwarded to converse() unchanged.
    Raises the last exception if all retries are exhausted.
    """
    last_exc = None
    for attempt in range(max_retries + 1):
        try:
            return bedrock_client.converse(**kwargs)
        except ClientError as exc:
            code = exc.response["Error"]["Code"]
            if code not in _THROTTLE_CODES:
                raise  # non-retryable — propagate immediately
            last_exc = exc
            if attempt == max_retries:
                break
            # Exponential back-off with full jitter:
            # delay = random(0, min(MAX, BASE * 2^attempt))
            cap = min(_MAX_DELAY_S, _BASE_DELAY_S * (2 ** attempt))
            delay = random.uniform(0, cap)
            time.sleep(delay)

    raise last_exc


def bedrock_tool_call(
    bedrock_client,
    *,
    tool_name: str,
    tool_description: str,
    output_schema: dict,
    max_retries: int = _DEFAULT_MAX_RETRIES,
    use_cache: bool = True,
    **kwargs,
) -> tuple[dict, dict]:
    """
    Call Bedrock Converse forcing the model to use a single named tool.

    Instead of asking the model to "return ONLY valid JSON" (which is fragile —
    the model can add markdown fences, explanations, or produce truncated output),
    this forces the API to validate and return structured data matching output_schema.

    The tool input is returned as a plain Python dict — no json.loads() needed,
    no fence-stripping, no parse errors.

    Returns:
        (response, tool_input_dict)  — the full Bedrock response and the parsed result.

    Usage:
        response, result = bedrock_tool_call(
            bedrock,
            tool_name="submit_plan",
            tool_description="Submit the translation plan",
            output_schema={
                "type": "object",
                "properties": {"units": {"type": "array", ...}},
                "required": ["units"],
            },
            modelId=model_id,
            system=[...],
            messages=[...],
            inferenceConfig={...},
        )
    """
    tools = [
        {
            "toolSpec": {
                "name": tool_name,
                "description": tool_description,
                "inputSchema": {"json": output_schema},
            }
        }
    ]

    # Cache the system prompt — it's identical across all parallel units in a job
    # and across retries, so subsequent calls get cache hits at ~10% token cost.
    # Tool-level caching is omitted here as Bedrock's support for cachePoint inside
    # toolConfig.tools is inconsistent across model versions.
    if use_cache and "system" in kwargs:
        system = list(kwargs.pop("system"))
        system.append({"cachePoint": {"type": "default"}})
        kwargs["system"] = system

    # Bedrock Converse API nests tool definitions + choice inside toolConfig,
    # not as top-level parameters.
    response = bedrock_converse(
        bedrock_client,
        toolConfig={
            "tools":      tools,
            "toolChoice": {"tool": {"name": tool_name}},
        },
        max_retries=max_retries,
        **kwargs,
    )

    for block in response["output"]["message"]["content"]:
        if "toolUse" in block:
            return response, block["toolUse"]["input"]

    raise ValueError(f"Model did not invoke tool '{tool_name}' — unexpected response structure")
