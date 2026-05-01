#!/usr/bin/env python3
"""
End-to-end test runner for Rosetta.

Zips each sample directory, submits a translation job via the API,
polls until completion, downloads the result zip, and reports pass/fail.

Usage (from repo root):
    cd infra/envs/dev
    python ../../../tests/run_e2e.py \
        --api  $(terraform output -raw api_endpoint) \
        --token eyJ...

Or pass --token-cmd to run a shell command that prints the token:
    python tests/run_e2e.py --api <url> --token-cmd "cat /tmp/token.txt"
"""

from __future__ import annotations

import argparse
import io
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

# ── ANSI colours ─────────────────────────────────────────────────────────────
GREEN  = "\033[92m"
RED    = "\033[91m"
YELLOW = "\033[93m"
CYAN   = "\033[96m"
BOLD   = "\033[1m"
RESET  = "\033[0m"

def ok(msg):   print(f"  {GREEN}✓{RESET} {msg}")
def fail(msg): print(f"  {RED}✗{RESET} {msg}")
def info(msg): print(f"  {CYAN}·{RESET} {msg}")
def warn(msg): print(f"  {YELLOW}!{RESET} {msg}")

# ── Test cases ────────────────────────────────────────────────────────────────

TESTS = [
    {
        "name":        "CloudFormation → Terraform",
        "sample_dir":  "samples/cfn_to_terraform",
        "source_lang": "cloudformation",
        "target_lang": "terraform",
    },
    {
        "name":        "Terraform → CloudFormation",
        "sample_dir":  "samples/terraform_to_cfn",
        "source_lang": "terraform",
        "target_lang": "cloudformation",
    },
    {
        "name":        "SAM (serverless) → CloudFormation",
        "sample_dir":  "samples/sam_serverless",
        "source_lang": "sam",
        "target_lang": "cloudformation",
    },
    {
        "name":        "Terraform modules (12 files, 4 dirs) → CloudFormation",
        "sample_dir":  "samples/tf_modules",
        "source_lang": "terraform",
        "target_lang": "cloudformation",
    },
    {
        "name":        "CloudFormation → CDK (TypeScript)",
        "sample_dir":  "samples/cfn_to_terraform",
        "source_lang": "cloudformation",
        "target_lang": "cdk",
        "target_cdk_lang": "typescript",
    },
    {
        "name":        "Terraform → CDK (Python)",
        "sample_dir":  "samples/terraform_to_cfn",
        "source_lang": "terraform",
        "target_lang": "cdk",
        "target_cdk_lang": "python",
    },
    {
        "name":        "SAM → Terraform",
        "sample_dir":  "samples/sam_serverless",
        "source_lang": "sam",
        "target_lang": "terraform",
    },
    {
        "name":        "CDK (TypeScript) → CloudFormation",
        "sample_dir":  "samples/cdk_to_cfn",
        "source_lang": "cdk",
        "source_cdk_lang": "typescript",
        "target_lang": "cloudformation",
    },
    {
        "name":        "Terraform modules → CDK (TypeScript)",
        "sample_dir":  "samples/tf_modules",
        "source_lang": "terraform",
        "target_lang": "cdk",
        "target_cdk_lang": "typescript",
    },
]

POLL_INTERVAL_S  = 4
POLL_TIMEOUT_S   = 300   # 5 min; plenty for the stub pipeline
TERMINAL_STATUSES = {"COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def api_request(method: str, url: str, token: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type":  "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise RuntimeError(f"HTTP {e.code}: {body_text}") from e


def upload_zip(upload_url: str, zip_bytes: bytes) -> None:
    req = urllib.request.Request(
        upload_url,
        data=zip_bytes,
        headers={"Content-Type": "application/zip"},
        method="PUT",
    )
    with urllib.request.urlopen(req) as resp:
        if resp.status not in (200, 204):
            raise RuntimeError(f"S3 upload returned HTTP {resp.status}")


def zip_directory(directory: Path) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in sorted(directory.rglob("*")):
            if path.is_file():
                zf.write(path, path.relative_to(directory))
    buf.seek(0)
    return buf.read()


def download_result(download_url: str, dest: Path) -> None:
    with urllib.request.urlopen(download_url) as resp:
        dest.write_bytes(resp.read())


# ── Single test case ──────────────────────────────────────────────────────────

def run_test(test: dict, api: str, token: str, tests_dir: Path, out_dir: Path) -> bool:
    name       = test["name"]
    sample_dir = tests_dir / test["sample_dir"]

    print(f"\n{BOLD}{CYAN}▶ {name}{RESET}")

    # 1. Zip the sample
    info("Zipping sample files…")
    try:
        zip_bytes = zip_directory(sample_dir)
        info(f"Zipped {len(zip_bytes):,} bytes from {sample_dir.name}/")
    except Exception as e:
        fail(f"Failed to zip sample: {e}")
        return False

    # 2. Create job
    info("Creating job…")
    try:
        body = {"sourceLang": test["source_lang"], "targetLang": test["target_lang"]}
        if "source_cdk_lang" in test:
            body["sourceCdkLang"] = test["source_cdk_lang"]
        if "target_cdk_lang" in test:
            body["targetCdkLang"] = test["target_cdk_lang"]
        resp = api_request("POST", f"{api}/jobs", token, body)
        job_id     = resp["jobId"]
        upload_url = resp["uploadUrl"]
        ok(f"Job created: {job_id}")
    except Exception as e:
        fail(f"POST /jobs failed: {e}")
        return False

    # 3. Upload zip
    info("Uploading zip to S3…")
    try:
        upload_zip(upload_url, zip_bytes)
        ok("Upload complete")
    except Exception as e:
        fail(f"S3 PUT failed: {e}")
        return False

    # 4. Start job
    info("Starting pipeline…")
    try:
        api_request("POST", f"{api}/jobs/{job_id}/start", token)
        ok("Pipeline started")
    except Exception as e:
        fail(f"POST /jobs/{job_id}/start failed: {e}")
        return False

    # 5. Poll until terminal status
    info(f"Polling every {POLL_INTERVAL_S}s (timeout {POLL_TIMEOUT_S}s)…")
    start = time.monotonic()
    last_step   = None
    last_ticker = 0.0
    TICKER_EVERY = 15  # print elapsed time every N seconds even if nothing changes

    while True:
        elapsed = time.monotonic() - start
        if elapsed > POLL_TIMEOUT_S:
            fail(f"Timed out after {POLL_TIMEOUT_S}s — check CloudWatch logs (see --logs hint below)")
            return False

        try:
            job = api_request("GET", f"{api}/jobs/{job_id}", token)
        except Exception as e:
            warn(f"Poll error (retrying): {e}")
            time.sleep(POLL_INTERVAL_S)
            continue

        status = job.get("status", "?")
        step   = job.get("step", "")

        if step and step != last_step:
            print(f"  {CYAN}→{RESET} [{elapsed:5.1f}s] step={step}  status={status}")
            last_step   = step
            last_ticker = elapsed
        elif elapsed - last_ticker >= TICKER_EVERY:
            print(f"  {YELLOW}…{RESET} [{elapsed:5.1f}s] status={status}  step={step or '(none)'}", flush=True)
            last_ticker = elapsed

        if status in TERMINAL_STATUSES:
            break

        time.sleep(POLL_INTERVAL_S)

    if status == "FAILED":
        fail(f"Job FAILED — {job.get('errorMsg', 'no detail')}")
        return False

    if status == "COMPLETED_WITH_WARNINGS":
        warn("Job completed WITH WARNINGS")
    else:
        ok(f"Job COMPLETED in {elapsed:.1f}s")

    # 6. Download result
    info("Downloading result zip…")
    try:
        dl = api_request("GET", f"{api}/jobs/{job_id}/download", token)
        download_url = dl["downloadUrl"]
        result_path  = out_dir / f"{test['sample_dir'].replace('/', '_')}_result.zip"
        download_result(download_url, result_path)
        size = result_path.stat().st_size
        ok(f"Saved {size:,} bytes → {result_path.name}")
    except Exception as e:
        fail(f"Download failed: {e}")
        return False

    # 7. Inspect the zip contents
    info("Result contains:")
    try:
        with zipfile.ZipFile(result_path) as zf:
            for name_ in sorted(zf.namelist()):
                info(f"  {name_}")
    except Exception:
        warn("Could not inspect zip contents")

    return True


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Rosetta end-to-end test runner")
    parser.add_argument("--api",       required=True,  help="API base URL (terraform output api_endpoint)")
    parser.add_argument("--token",     default="",     help="Cognito access token")
    parser.add_argument("--token-cmd", default="",     help="Shell command that prints the token")
    parser.add_argument("--tests",     default=None,   help="Comma-separated test names to run (default: all)")
    args = parser.parse_args()

    api = args.api.rstrip("/")

    if args.token_cmd:
        token = subprocess.check_output(args.token_cmd, shell=True).decode().strip()
    elif args.token:
        token = args.token
    else:
        print(f"{RED}Error: provide --token or --token-cmd{RESET}")
        sys.exit(1)

    tests_dir = Path(__file__).parent
    out_dir   = tests_dir / "results"
    out_dir.mkdir(exist_ok=True)

    tests_to_run = TESTS
    if args.tests:
        names = {n.strip().lower() for n in args.tests.split(",")}
        tests_to_run = [t for t in TESTS if any(n in t["name"].lower() for n in names)]
        if not tests_to_run:
            print(f"{RED}No matching tests found for: {args.tests}{RESET}")
            sys.exit(1)

    print(f"\n{BOLD}Rosetta E2E — {len(tests_to_run)} test(s) against {api}{RESET}")

    results = {}
    for test in tests_to_run:
        passed = run_test(test, api, token, tests_dir, out_dir)
        results[test["name"]] = passed

    # Summary
    print(f"\n{BOLD}── Summary {'─' * 40}{RESET}")
    all_passed = True
    for name, passed in results.items():
        symbol = f"{GREEN}PASS{RESET}" if passed else f"{RED}FAIL{RESET}"
        print(f"  {symbol}  {name}")
        if not passed:
            all_passed = False

    print()
    if all_passed:
        print(f"{GREEN}{BOLD}All tests passed.{RESET}")
        sys.exit(0)
    else:
        print(f"{RED}{BOLD}Some tests failed.{RESET}")
        sys.exit(1)


if __name__ == "__main__":
    main()
