"""
Build a project-wide symbol table from all source IaC files.

Parses variables/parameters, resource identifiers, outputs, and locals
across all files so each per-file translate invocation has cross-file context.

Parsers are pure-stdlib (no pip deps):
  - Terraform : custom brace-counting block extractor on HCL
  - CFN / SAM : yaml.safe_load (falls back to section-regex if unavailable)
  - CDK       : regex pattern matching on source code
"""
import json
import os
import re

import boto3

from ddb_utils import update_job_step

s3  = boto3.client("s3")
ddb = boto3.resource("dynamodb")

JOBS_TABLE = os.environ["JOBS_TABLE"]


# ── Entry point ────────────────────────────────────────────────────────────────

def handler(event, context):
    update_job_step(ddb, JOBS_TABLE, event["userId"], event["jobId"], "DEP_MAP")

    bucket      = event["artifactsBucket"]
    file_list   = event.get("preflightResult", {}).get("fileList", [])
    source_lang = event.get("sourceLang", "")
    cdk_lang    = event.get("sourceCdkLang", "typescript")

    if not file_list:
        return _empty()

    # Read all staged source files
    file_contents: dict[str, str] = {}
    for f in file_list:
        try:
            body = (
                s3.get_object(Bucket=bucket, Key=f["s3Key"])["Body"]
                .read()
                .decode("utf-8", errors="replace")
            )
            file_contents[f["path"]] = body
        except Exception:
            continue

    if source_lang == "terraform":
        return parse_terraform(file_contents)
    elif source_lang in ("cloudformation", "sam"):
        return parse_cfn(file_contents)
    elif source_lang == "cdk":
        return parse_cdk(file_contents, cdk_lang)
    return _empty()


def _empty():
    return {"variables": {}, "parameters": {}, "resources": {}, "outputs": {}, "symbolTable": {}}


# ── Terraform parser ───────────────────────────────────────────────────────────

def parse_terraform(files: dict[str, str]) -> dict:
    variables:    dict[str, dict] = {}
    resources:    dict[str, dict] = {}
    outputs:      dict[str, dict] = {}
    locals_map:   dict[str, dict] = {}
    data_sources: dict[str, dict] = {}

    for path, content in files.items():
        # Strip inline comments to avoid confusing the block parser
        content = re.sub(r"#[^\n]*", "", content)
        content = re.sub(r"//[^\n]*", "", content)

        for block in _hcl_blocks(content):
            btype  = block["type"]
            label1 = block["label1"]
            label2 = block.get("label2")
            body   = block["body"]

            if btype == "variable" and label1:
                info: dict = {"file": path}
                m = re.search(r"\btype\s*=\s*(\w+)", body)
                if m:
                    info["type"] = m.group(1)
                m = re.search(r'\bdefault\s*=\s*"?([^"\n,]+)"?', body)
                if m:
                    info["default"] = m.group(1).strip()
                m = re.search(r'\bdescription\s*=\s*"([^"]*)"', body)
                if m:
                    info["description"] = m.group(1)
                variables[label1] = info

            elif btype == "resource" and label1 and label2:
                # Key as "resource_type.resource_name" to avoid collisions when
                # multiple resource types share the same logical name.
                resources[f"{label1}.{label2}"] = {"type": label1, "name": label2, "file": path}

            elif btype == "output" and label1:
                m = re.search(r"\bvalue\s*=\s*(.+)", body)
                outputs[label1] = {
                    "value": m.group(1).strip() if m else "",
                    "file": path,
                }

            elif btype == "data" and label1 and label2:
                data_sources[f"{label1}.{label2}"] = {"file": path}

            elif btype == "locals":
                # Parse key = value pairs at the first indentation level
                for m in re.finditer(r"^\s{2}(\w+)\s*=\s*(.+)$", body, re.MULTILINE):
                    locals_map[m.group(1)] = {"value": m.group(2).strip(), "file": path}

    symbol_table: dict = {}
    if variables:
        symbol_table["variables"] = {
            name: (
                info.get("type", "any")
                + (f" (default: {info['default']})" if info.get("default") else "")
                + f"  [{info['file']}]"
            )
            for name, info in variables.items()
        }
    if resources:
        symbol_table["resources"] = {
            key: f"{info['type']}  [{info['file']}]"
            for key, info in resources.items()
        }
    if outputs:
        symbol_table["outputs"] = {
            name: f"{info['value']}  [{info['file']}]"
            for name, info in outputs.items()
        }
    if locals_map:
        symbol_table["locals"] = {
            name: f"{info['value']}  [{info['file']}]"
            for name, info in locals_map.items()
        }
    if data_sources:
        symbol_table["dataSources"] = list(data_sources.keys())

    return {
        "variables": variables,
        "resources": resources,
        "outputs": outputs,
        "locals": locals_map,
        "dataSources": data_sources,
        "symbolTable": symbol_table,
    }


def _hcl_blocks(content: str) -> list[dict]:
    """
    Extract top-level HCL blocks using brace-depth tracking.
    Handles both single-line and multi-line blocks.
    Does NOT handle heredocs or complex nested expressions — good enough
    for extracting variable/resource/output metadata.
    """
    blocks = []
    lines  = content.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        # keyword "label1" [optional "label2"] {
        m = re.match(r'^(\w+)\s+"([^"]+)"(?:\s+"([^"]+)")?\s*\{(.*)', line)
        if not m:
            i += 1
            continue

        btype, label1, label2, inline = m.group(1), m.group(2), m.group(3), m.group(4).strip()

        # Single-line block: keyword "a" "b" { ... }
        if inline.endswith("}"):
            blocks.append({"type": btype, "label1": label1, "label2": label2, "body": inline[:-1]})
            i += 1
            continue

        # Multi-line block: accumulate until depth returns to 0
        depth       = 1
        body_lines  = [inline] if inline else []
        i += 1
        while i < len(lines) and depth > 0:
            l = lines[i]
            depth += l.count("{") - l.count("}")
            if depth > 0:
                body_lines.append(l)
            i += 1

        blocks.append({"type": btype, "label1": label1, "label2": label2, "body": "\n".join(body_lines)})

    return blocks


# ── CloudFormation / SAM parser ────────────────────────────────────────────────

def parse_cfn(files: dict[str, str]) -> dict:
    parameters: dict[str, dict] = {}
    resources:  dict[str, dict] = {}
    outputs:    dict[str, dict] = {}

    for path, content in files.items():
        template = _load_template(content)
        if not isinstance(template, dict):
            continue

        for name, props in (template.get("Parameters") or {}).items():
            if not isinstance(props, dict):
                continue
            parameters[name] = {
                "type":    props.get("Type", "String"),
                "default": props.get("Default"),
                "allowed": props.get("AllowedValues"),
                "file":    path,
            }

        for logical_id, res in (template.get("Resources") or {}).items():
            if not isinstance(res, dict):
                continue
            resources[logical_id] = {"type": res.get("Type", ""), "file": path}

        for name, out in (template.get("Outputs") or {}).items():
            if not isinstance(out, dict):
                continue
            val    = out.get("Value", "")
            export = out.get("Export", {})
            outputs[name] = {
                "value":  str(val)[:120],
                "export": str(export.get("Name", ""))[:80] if isinstance(export, dict) else "",
                "file":   path,
            }

    symbol_table: dict = {}
    if parameters:
        symbol_table["parameters"] = {
            name: (
                info.get("type", "String")
                + (f" (default: {info['default']})" if info.get("default") is not None else "")
            )
            for name, info in parameters.items()
        }
    if resources:
        symbol_table["resources"] = {
            lid: f"{info['type']}  [{info['file']}]"
            for lid, info in resources.items()
        }
    if outputs:
        symbol_table["outputs"] = {
            name: (
                info["value"][:80]
                + (f"  (export: {info['export']})" if info.get("export") else "")
            )
            for name, info in outputs.items()
        }

    return {
        "parameters": parameters,
        "resources":  resources,
        "outputs":    outputs,
        "symbolTable": symbol_table,
    }


def _load_template(content: str):
    """
    Try YAML (with CloudFormation intrinsic function tag support),
    fall back to JSON, fall back to section-based regex.
    """
    try:
        import yaml

        # CloudFormation uses non-standard YAML tags (!Sub, !Ref, !GetAtt, etc.)
        # Register a catch-all constructor so SafeLoader doesn't error on them.
        _CFN_TAGS = [
            "!Sub", "!Ref", "!GetAtt", "!Select", "!If", "!Join", "!Split",
            "!FindInMap", "!Base64", "!Condition", "!And", "!Or", "!Not",
            "!Equals", "!ImportValue", "!Transform", "!Cidr",
        ]
        for tag in _CFN_TAGS:
            yaml.SafeLoader.add_constructor(
                tag,
                lambda loader, node: (
                    loader.construct_sequence(node)
                    if node.id == "sequence"
                    else loader.construct_scalar(node)
                ),
            )

        return yaml.safe_load(content)
    except Exception:
        pass
    try:
        return json.loads(content)
    except Exception:
        pass
    return _parse_cfn_sections_regex(content)


def _parse_cfn_sections_regex(content: str) -> dict:
    """
    Minimal CFN YAML parser using regex — used when PyYAML is unavailable.
    Extracts only the resource logical IDs and parameter names.
    """
    result: dict = {"Parameters": {}, "Resources": {}, "Outputs": {}}
    current = None
    indent_base: int | None = None

    for line in content.splitlines():
        stripped = line.lstrip()
        indent   = len(line) - len(stripped)

        # Detect top-level section headers
        m = re.match(r"^(Parameters|Resources|Outputs|Globals)\s*:", line)
        if m:
            current     = m.group(1)
            indent_base = None
            continue

        if current and stripped and not stripped.startswith("#"):
            if indent_base is None and indent > 0:
                indent_base = indent

            if indent_base and indent == indent_base:
                m = re.match(r"^(\w+)\s*:", stripped)
                if m:
                    key = m.group(1)
                    if current == "Resources":
                        result["Resources"][key] = {"Type": ""}
                        _current_resource_key = key
                    elif current == "Parameters":
                        result["Parameters"][key] = {"Type": "String"}
                    elif current == "Outputs":
                        result["Outputs"][key] = {"Value": ""}

            # Capture Type: field one level deeper than resource/param keys
            elif indent_base and indent == indent_base + 2:
                m_type = re.match(r"^Type\s*:\s*(.+)$", stripped)
                if m_type and current == "Resources":
                    last_key = list(result["Resources"].keys())[-1] if result["Resources"] else None
                    if last_key:
                        result["Resources"][last_key]["Type"] = m_type.group(1).strip()

            elif indent_base and indent < indent_base:
                current     = None
                indent_base = None

    return result


# ── CDK parser (all languages) ─────────────────────────────────────────────────

_CDK_PATTERNS: dict[str, list[str]] = {
    "typescript": [
        # new aws_s3.Bucket(this, 'MyBucket', {...})
        r"new\s+\w[\w.]*\s*\(\s*(?:this|scope)\s*,\s*['\"]([^'\"]+)['\"]",
        # const myBucket = new s3.Bucket(...)
        r"(?:const|let|var)\s+(\w+)\s*=\s*new\s+\w",
    ],
    "python": [
        # s3.Bucket(self, "MyBucket", ...)
        r"\w+\.\w+\s*\(\s*\w+\s*,\s*['\"]([^'\"]+)['\"]",
        # my_bucket = s3.Bucket(...)
        r"(\w+)\s*=\s*\w+\.\w+\s*\(",
    ],
    "java": [
        # Bucket.Builder.create(this, "MyBucket").build()
        r"\.create\s*\(\s*\w+\s*,\s*\"([^\"]+)\"",
        r"new\s+\w+\s*\(\s*\w+\s*,\s*\"([^\"]+)\"",
    ],
    "csharp": [
        # new Bucket(this, "MyBucket", ...)
        r"new\s+\w+\s*\(\s*\w+\s*,\s*\"([^\"]+)\"",
    ],
    "go": [
        # awss3.NewBucket(stack, jsii.String("MyBucket"), ...)
        r'jsii\.String\s*\(\s*"([^"]+)"\s*\)',
    ],
}

def parse_cdk(files: dict[str, str], cdk_lang: str) -> dict:
    patterns = _CDK_PATTERNS.get(cdk_lang, _CDK_PATTERNS["typescript"])
    resources: dict[str, dict] = {}
    imports:   list[str]       = []

    for path, content in files.items():
        for pattern in patterns:
            for m in re.finditer(pattern, content):
                construct_id = m.group(1)
                if construct_id and construct_id not in ("this", "self", "scope", "stack"):
                    resources[construct_id] = {"file": path}

        # Extract import statements for context
        if cdk_lang == "typescript":
            for m in re.finditer(r"import\s+.*?from\s+'(aws-cdk-lib[^']*)'", content):
                imports.append(m.group(1))
        elif cdk_lang == "python":
            for m in re.finditer(r"from\s+(aws_cdk\S*)\s+import", content):
                imports.append(m.group(1))

    symbol_table: dict = {}
    if resources:
        symbol_table["constructs"] = {
            cid: f"[{info['file']}]" for cid, info in resources.items()
        }
    if imports:
        symbol_table["imports"] = sorted(set(imports))

    return {
        "resources":   resources,
        "imports":     sorted(set(imports)),
        "symbolTable": symbol_table,
    }
