#!/usr/bin/env python3
"""Bootstrap GMAIL_REFRESH_TOKEN as a GitHub Actions secret.

One-command flow for the operations board:
  1. Prompts for `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` (env or stdin).
  2. Runs the Google OAuth installed-app flow on `127.0.0.1` with PKCE.
  3. Exchanges the auth code for an offline refresh token.
  4. Pipes the refresh token directly into `gh secret set GMAIL_REFRESH_TOKEN`.
  5. Never persists or echoes the token.

The helper depends only on Python's standard library and the `gh` CLI.
"""

from __future__ import annotations

import argparse
import base64
import getpass
import hashlib
import http.server
import json
import os
import secrets
import shutil
import subprocess
import sys
import threading
import urllib.error
import urllib.parse
import urllib.request
import webbrowser

DEFAULT_REPO = "CryptoPhilo/blockchain-economics-lab"
DEFAULT_SECRET = "GMAIL_REFRESH_TOKEN"
DEFAULT_SCOPE = "https://www.googleapis.com/auth/gmail.modify"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    server_version = "BootstrapHelper/1.0"

    def do_GET(self):  # noqa: N802 (BaseHTTPRequestHandler API)
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        self.server.oauth_result = {  # type: ignore[attr-defined]
            "code": params.get("code", [None])[0],
            "state": params.get("state", [None])[0],
            "error": params.get("error", [None])[0],
        }
        body = (
            "<html><body style='font-family:sans-serif'>"
            "<h2>Gmail OAuth bootstrap complete.</h2>"
            "<p>You can close this tab and return to the terminal.</p>"
            "</body></html>"
        ).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args, **_kwargs):  # silence access log
        return


def _read_secret(name: str) -> str:
    value = os.environ.get(name)
    if value:
        return value.strip()
    try:
        value = getpass.getpass(f"{name}: ")
    except (KeyboardInterrupt, EOFError):
        print("\nAborted.", file=sys.stderr)
        sys.exit(130)
    value = value.strip()
    if not value:
        print(f"{name} is required.", file=sys.stderr)
        sys.exit(2)
    return value


def _pkce_pair() -> tuple[str, str]:
    verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode()
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode()).digest()
    ).rstrip(b"=").decode()
    return verifier, challenge


def _wait_for_code(scope: str, client_id: str) -> tuple[str, str, str]:
    state = secrets.token_urlsafe(24)
    verifier, challenge = _pkce_pair()
    server = http.server.HTTPServer(("127.0.0.1", 0), _CallbackHandler)
    server.oauth_result = None  # type: ignore[attr-defined]
    port = server.server_address[1]
    redirect_uri = f"http://127.0.0.1:{port}"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": scope,
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"

    thread = threading.Thread(target=server.handle_request, daemon=True)
    thread.start()

    print("Opening Google consent page in your browser...", file=sys.stderr)
    print(f"If it does not open, paste this URL manually:\n  {auth_url}", file=sys.stderr)
    try:
        webbrowser.open(auth_url, new=1, autoraise=True)
    except webbrowser.Error:
        pass

    thread.join(timeout=300)
    server.server_close()
    result = getattr(server, "oauth_result", None)
    if not result:
        print("Timed out waiting for OAuth callback (5 min).", file=sys.stderr)
        sys.exit(1)
    if result.get("error"):
        print(f"OAuth error: {result['error']}", file=sys.stderr)
        sys.exit(1)
    if result.get("state") != state:
        print("OAuth state mismatch; aborting for safety.", file=sys.stderr)
        sys.exit(1)
    code = result.get("code")
    if not code:
        print("No authorization code received.", file=sys.stderr)
        sys.exit(1)
    return code, verifier, redirect_uri


def _exchange_token(
    *,
    code: str,
    verifier: str,
    redirect_uri: str,
    client_id: str,
    client_secret: str,
) -> str:
    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
            "code_verifier": verifier,
        }
    ).encode("utf-8")
    req = urllib.request.Request(
        TOKEN_URL,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        print(f"Token exchange failed ({exc.code}): {body}", file=sys.stderr)
        sys.exit(1)
    refresh_token = payload.get("refresh_token")
    if not refresh_token:
        print(
            "Token response did not include refresh_token. Revoke prior consent at "
            "https://myaccount.google.com/permissions and retry.",
            file=sys.stderr,
        )
        sys.exit(1)
    return refresh_token


def _publish_secret(refresh_token: str, repo: str, secret_name: str) -> None:
    if shutil.which("gh") is None:
        print(
            "GitHub CLI (`gh`) is not installed or not on PATH. "
            "Install via https://cli.github.com/ and rerun.",
            file=sys.stderr,
        )
        sys.exit(127)
    try:
        completed = subprocess.run(
            ["gh", "secret", "set", secret_name, "--repo", repo, "--body", "-"],
            input=refresh_token,
            text=True,
            capture_output=True,
            check=False,
        )
    except FileNotFoundError:
        print("`gh` CLI invocation failed.", file=sys.stderr)
        sys.exit(127)
    if completed.returncode != 0:
        stderr = completed.stderr.strip() or "unknown error"
        print(f"`gh secret set` failed: {stderr}", file=sys.stderr)
        sys.exit(completed.returncode or 1)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.strip())
    parser.add_argument("--repo", default=DEFAULT_REPO)
    parser.add_argument("--secret-name", default=DEFAULT_SECRET)
    parser.add_argument("--scope", default=DEFAULT_SCOPE)
    args = parser.parse_args()

    print(f"Repository: {args.repo}", file=sys.stderr)
    print(f"Secret name: {args.secret_name}", file=sys.stderr)

    client_id = _read_secret("GMAIL_CLIENT_ID")
    client_secret = _read_secret("GMAIL_CLIENT_SECRET")

    code, verifier, redirect_uri = _wait_for_code(args.scope, client_id)
    refresh_token = _exchange_token(
        code=code,
        verifier=verifier,
        redirect_uri=redirect_uri,
        client_id=client_id,
        client_secret=client_secret,
    )
    _publish_secret(refresh_token, args.repo, args.secret_name)

    print(f"Secret {args.secret_name} registered on {args.repo}.")


if __name__ == "__main__":
    main()
