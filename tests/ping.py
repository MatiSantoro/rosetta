"""
Full pipeline smoke test — no dependencies beyond stdlib.

Usage:
    python tests/ping.py <api-url> <token> <sample-dir> <source-lang> <target-lang> [cdk-lang]

Examples:
    python tests/ping.py "https://..." "eyJ..." tests/samples/cfn_to_terraform cloudformation terraform
    python tests/ping.py "https://..." "eyJ..." tests/samples/terraform_to_cfn terraform cloudformation
    python tests/ping.py "https://..." "eyJ..." tests/samples/sam_serverless sam cloudformation
"""
import io
import json
import sys
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

if len(sys.argv) < 6:
    print(__doc__)
    sys.exit(1)

API         = sys.argv[1].rstrip("/")
TOKEN       = sys.argv[2]
SAMPLE_DIR  = Path(sys.argv[3])
SOURCE_LANG = sys.argv[4]
TARGET_LANG = sys.argv[5]
CDK_LANG    = sys.argv[6] if len(sys.argv) > 6 else None

POLL_INTERVAL = 4
POLL_TIMEOUT  = 300


def call(method, path, body=None, base=API):
    data = json.dumps(body).encode() if body else None
    req  = urllib.request.Request(
        base + path if base == API else base,
        data=data,
        headers={"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"},
        method=method,
    )
    with urllib.request.urlopen(req, timeout=20) as r:
        return r.status, json.loads(r.read())


def put_bytes(url, data, content_type="application/zip"):
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": content_type},
        method="PUT",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.status


def zip_dir(directory):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in sorted(directory.rglob("*")):
            if p.is_file():
                zf.write(p, p.relative_to(directory))
    buf.seek(0)
    return buf.read()


def step(label):
    print(f"\n[{label}]")


def ok(msg):   print(f"  OK  {msg}")
def err(msg):  print(f"  ERR {msg}"); sys.exit(1)
def info(msg): print(f"  ... {msg}")


# ── 1. Verify auth ────────────────────────────────────────────────────────────
step("1/6  Auth check")
try:
    status, body = call("GET", "/jobs")
    ok(f"GET /jobs -> {status}  (existing jobs: {len(body['items'])})")
except Exception as e:
    err(f"Auth failed: {e}")

# ── 2. Create job ─────────────────────────────────────────────────────────────
step("2/6  Create job")
try:
    payload = {"sourceLang": SOURCE_LANG, "targetLang": TARGET_LANG}
    if CDK_LANG and SOURCE_LANG == "cdk":
        payload["sourceCdkLang"] = CDK_LANG
    if CDK_LANG and TARGET_LANG == "cdk":
        payload["targetCdkLang"] = CDK_LANG
    status, body = call("POST", "/jobs", payload)
    job_id    = body["jobId"]
    upload_url = body["uploadUrl"]
    ok(f"jobId={job_id}")
except urllib.error.HTTPError as e:
    err(f"POST /jobs -> HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    err(f"POST /jobs -> {e}")

# ── 3. Zip sample and upload ──────────────────────────────────────────────────
step("3/6  Upload sample zip")
info(f"Zipping {SAMPLE_DIR} ...")
try:
    zipped = zip_dir(SAMPLE_DIR)
    info(f"Zip size: {len(zipped):,} bytes")
    status = put_bytes(upload_url, zipped)
    ok(f"S3 PUT -> {status}")
except urllib.error.HTTPError as e:
    err(f"S3 PUT -> HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    err(f"S3 PUT -> {e}")

# ── 4. Start job ──────────────────────────────────────────────────────────────
step("4/6  Start pipeline")
try:
    status, body = call("POST", f"/jobs/{job_id}/start")
    ok(f"status={body.get('status')}")
except urllib.error.HTTPError as e:
    err(f"POST /start -> HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    err(f"POST /start -> {e}")

# ── 5. Poll ───────────────────────────────────────────────────────────────────
step("5/6  Polling (timeout 300s)")
start      = time.monotonic()
last_step  = None
last_tick  = 0.0
TERMINAL   = {"COMPLETED", "COMPLETED_WITH_WARNINGS", "FAILED"}

while True:
    elapsed = time.monotonic() - start
    if elapsed > POLL_TIMEOUT:
        err(f"Timed out after {POLL_TIMEOUT}s — check CloudWatch /aws/states/rosetta-dev-translate-job")

    try:
        _, job = call("GET", f"/jobs/{job_id}")
    except Exception as e:
        info(f"Poll error: {e}")
        time.sleep(POLL_INTERVAL)
        continue

    status = job.get("status", "?")
    current_step = job.get("step", "")

    if current_step != last_step:
        print(f"  [{elapsed:5.1f}s] step={current_step or '(none)'}  status={status}")
        last_step = current_step
        last_tick = elapsed
    elif elapsed - last_tick >= 15:
        print(f"  [{elapsed:5.1f}s] still waiting...  status={status}")
        last_tick = elapsed

    if status in TERMINAL:
        break

    time.sleep(POLL_INTERVAL)

if status == "FAILED":
    err(f"Job FAILED: {job.get('errorMsg', 'no detail')}")
else:
    ok(f"Job {status} in {elapsed:.1f}s")

# ── 6. Download ───────────────────────────────────────────────────────────────
step("6/6  Download result")
try:
    _, body = call("GET", f"/jobs/{job_id}/download")
    url = body["downloadUrl"]
    req = urllib.request.Request(url)
    with urllib.request.urlopen(req, timeout=30) as r:
        result_bytes = r.read()

    out = Path(__file__).parent / "results"
    out.mkdir(exist_ok=True)
    out_path = out / f"{job_id}_result.zip"
    out_path.write_bytes(result_bytes)
    ok(f"Saved {len(result_bytes):,} bytes -> {out_path}")

    with zipfile.ZipFile(io.BytesIO(result_bytes)) as zf:
        ok(f"Contents: {zf.namelist()}")

except urllib.error.HTTPError as e:
    err(f"Download -> HTTP {e.code}: {e.read().decode()}")
except Exception as e:
    err(f"Download -> {e}")

print("\nAll steps passed.")
