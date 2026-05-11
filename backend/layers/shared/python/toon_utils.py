"""
Minimal TOON (Token-Oriented Object Notation) encoder for Rosetta.

TOON is an LLM-input format that replaces JSON for structured data sent TO
the model. It saves 30–60% tokens on tabular/flat data by declaring field
names once (as a header) rather than repeating them on every row.

IMPORTANT: TOON is input-only. Model outputs still use JSON / tool use.
Only use this to compress data we send in prompts, never to request output.

Spec subset implemented here:
  - Tabular arrays  →  name[N]{f1,f2,...}:\n  v1,v2,...
  - Flat objects    →  key: value (one per line)
  - Nested objects  →  key:\n  child_key: value (indented)

Reference: https://toonformat.dev
"""
from __future__ import annotations


def _escape_value(val: str) -> str:
    """Quote a value if it contains commas, newlines, or leading/trailing spaces."""
    val = str(val)
    if "," in val or "\n" in val or val != val.strip():
        # Use double-quotes; escape internal double-quotes by doubling them
        val = '"' + val.replace('"', '""') + '"'
    return val


def toon_table(name: str, rows: list[dict], fields: list[str]) -> str:
    """
    Encode a uniform list of dicts as a TOON tabular array.

    Example:
        toon_table("files", [{"path":"main.tf","size":1234}], ["path","size"])
        →
        files[1]{path,size}:
          main.tf,1234
    """
    if not rows:
        return f"{name}[0]{{{','.join(fields)}}}:"
    lines = [f"{name}[{len(rows)}]{{{','.join(fields)}}}:"]
    for row in rows:
        values = [_escape_value(row.get(f, "")) for f in fields]
        lines.append("  " + ",".join(values))
    return "\n".join(lines)


def toon_flat(obj: dict) -> str:
    """
    Encode a flat dict as TOON key: value pairs.

    Example:
        toon_flat({"userId": "abc", "jobId": "123"})
        →
        userId: abc
        jobId: 123
    """
    return "\n".join(f"{k}: {_escape_value(v)}" for k, v in obj.items())


def toon_symbol_table(symbol_table: dict) -> str:
    """
    Encode the plan_translation symbol table in TOON.

    The symbol table has sections: variables, resources, outputs, modules.
    Each section is a flat name→description mapping.

    Example output:
        variables[2]{name,type_file}:
          env,string (variables.tf)
          region,string (variables.tf)
        resources[1]{name,type_file}:
          my_bucket,aws_s3_bucket (main.tf)
    """
    parts = []
    for section, entries in symbol_table.items():
        if not entries or not isinstance(entries, dict):
            continue
        rows = [{"name": k, "value": v} for k, v in entries.items()]
        parts.append(toon_table(section, rows, ["name", "value"]))
    return "\n\n".join(parts) if parts else "(empty)"


def toon_file_inventory(file_list: list[dict], directory_tree: dict) -> str:
    """
    Encode the project file inventory as TOON.

    file_list items have: path, size, s3Key
    Returns a tabular array with path, directory, and size_bytes.
    """
    rows = []
    for f in file_list:
        path = f.get("path", "")
        # Derive directory from path
        directory = path.rsplit("/", 1)[0] if "/" in path else "."
        rows.append({
            "path":      path,
            "dir":       directory,
            "size":      f.get("size", 0),
        })
    return toon_table("files", rows, ["path", "dir", "size"])
