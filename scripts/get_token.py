#!/usr/bin/env python3
"""
Dev helper: fetch a Cognito access token via PKCE + Hosted UI.

Usage:
    cd infra/envs/dev
    python ../../../scripts/get_token.py \
        --domain $(terraform output -raw cognito_hosted_ui_domain) \
        --client-id $(terraform output -raw cognito_user_pool_client_id)

The script starts a temporary server on localhost:5173, opens the Hosted UI
in your browser, captures the auth code on the callback, exchanges it for
tokens, and prints the access token ready to copy into curl / Postman.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import http.server
import json
import secrets
import threading
import urllib.parse
import urllib.request
import webbrowser

REDIRECT_URI = "http://localhost:5173/auth/callback"
SCOPE = "openid email profile"
CALLBACK_PATH = "/auth/callback"


def pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return verifier, challenge


def build_auth_url(domain: str, client_id: str, challenge: str) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": SCOPE,
        "redirect_uri": REDIRECT_URI,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    return f"https://{domain}/oauth2/authorize?" + urllib.parse.urlencode(params)


def exchange_code(domain: str, client_id: str, code: str, verifier: str) -> dict:
    data = urllib.parse.urlencode({
        "grant_type": "authorization_code",
        "client_id": client_id,
        "code": code,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier,
    }).encode()
    req = urllib.request.Request(
        f"https://{domain}/oauth2/token",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    with urllib.request.urlopen(req) as resp:
        return json.loads(resp.read())


def make_handler(code_holder: list):
    class _Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            parsed = urllib.parse.urlparse(self.path)
            if not parsed.path.startswith(CALLBACK_PATH):
                self.send_response(404)
                self.end_headers()
                return
            params = urllib.parse.parse_qs(parsed.query)
            if "error" in params:
                msg = params.get("error_description", params["error"])[0]
                self.send_response(400)
                self.end_headers()
                self.wfile.write(f"<h2>Error: {msg}</h2>".encode())
                code_holder.append(None)
            elif "code" in params:
                code_holder.append(params["code"][0])
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"<h2>Got it! You can close this tab.</h2>")
            else:
                self.send_response(400)
                self.end_headers()

        def log_message(self, *args):
            pass  # silence request logs

    return _Handler


def main():
    parser = argparse.ArgumentParser(description="Fetch a Cognito access token (PKCE)")
    parser.add_argument("--domain", required=True, help="Cognito Hosted UI domain (no https://)")
    parser.add_argument("--client-id", required=True, help="Cognito app client ID")
    args = parser.parse_args()

    verifier, challenge = pkce_pair()
    auth_url = build_auth_url(args.domain, args.client_id, challenge)

    code_holder: list = []
    server = http.server.HTTPServer(("localhost", 5173), make_handler(code_holder))
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print(f"\nOpening browser for Google sign-in…\n{auth_url}\n")
    webbrowser.open(auth_url)
    thread.join(timeout=120)
    server.server_close()

    if not code_holder or code_holder[0] is None:
        print("ERROR: did not receive an auth code (timed out or Cognito returned an error).")
        return

    print("Exchanging code for tokens…")
    try:
        tokens = exchange_code(args.domain, args.client_id, code_holder[0], verifier)
    except urllib.error.HTTPError as e:
        print(f"Token exchange failed ({e.code}): {e.read().decode()}")
        return

    access = tokens.get("access_token", "")
    id_tok = tokens.get("id_token", "")

    print("\n" + "=" * 60)
    print("ACCESS TOKEN  (use as: -H 'Authorization: Bearer <token>')")
    print("=" * 60)
    print(access)

    print("\n" + "=" * 60)
    print("ID TOKEN")
    print("=" * 60)
    print(id_tok)

    print("\n--- Quick curl test ---")
    api = input("\nPaste your api_endpoint (or press Enter to skip): ").strip()
    if api:
        api = api.rstrip("/")
        print(f'\ncurl -s -H "Authorization: Bearer {access}" {api}/jobs | python -m json.tool')


if __name__ == "__main__":
    main()
