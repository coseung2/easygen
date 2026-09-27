#!/usr/bin/env python3
"""A mock OAuth 2.0 authorization server used by the app's login tests.

It is *not* OpenAI; it exists so the host-side flow (PKCE, state handling,
token exchange, refresh rotation and single-flight) can be verified without a
real account. Behaviour hooks:

* refresh responses omit ``refresh_token`` unless the incoming token contains
  ``-rotate`` (rotation-safety test)
* an incoming refresh token containing ``-invalid`` answers 400 invalid_grant
* GET /stats reports how many token requests were served
* ``--token-delay-ms`` delays authorization-code token responses so a cancel
  arriving during the exchange can be tested
"""
import argparse
import base64
import json
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

STATE = {"token_requests": 0, "refresh_requests": 0, "last_refresh": "", "auth_codes": [], "token_delay_ms": 0}


def b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def make_id_token(email: str, account_id: str) -> str:
    header = b64url(json.dumps({"alg": "none", "typ": "JWT"}).encode())
    payload = b64url(json.dumps({
        "email": email,
        "chatgpt_account_id": account_id,
        "https://api.openai.com/auth": {"chatgpt_account_id": account_id},
    }).encode())
    return f"{header}.{payload}.signature"


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def log_message(self, *args):  # keep the test output clean
        pass

    def _send(self, status: int, payload: dict):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802 - http.server API
        if urlparse(self.path).path == "/stats":
            self._send(200, STATE)
            return
        self._send(404, {"error": "not_found"})

    def do_POST(self):  # noqa: N802 - http.server API
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length).decode("utf-8")
        form = {key: values[0] for key, values in parse_qs(body).items()}
        path = urlparse(self.path).path
        if path != "/oauth/token":
            self._send(404, {"error": "not_found"})
            return
        STATE["token_requests"] += 1
        grant = form.get("grant_type")
        if grant == "authorization_code":
            if not form.get("code_verifier"):
                self._send(400, {"error": "invalid_request", "error_description": "code_verifier missing"})
                return
            if not form.get("code", "").startswith("code-"):
                self._send(400, {"error": "invalid_grant", "error_description": "unknown code"})
                return
            STATE["auth_codes"].append(form["code"])
            if STATE["token_delay_ms"]:
                time.sleep(STATE["token_delay_ms"] / 1000.0)
            self._send(200, {
                "access_token": "access-1",
                "refresh_token": "refresh-1",
                "expires_in": 3600,
                "id_token": make_id_token("tester@example.com", "acct-test-1"),
            })
            return
        if grant == "refresh_token":
            STATE["refresh_requests"] += 1
            token = form.get("refresh_token", "")
            STATE["last_refresh"] = token
            if "-invalid" in token:
                self._send(400, {"error": "invalid_grant", "error_description": "refresh token revoked"})
                return
            payload = {
                "access_token": f"access-r{STATE['refresh_requests']}",
                "expires_in": 3600,
            }
            if "-rotate" in token:
                payload["refresh_token"] = f"refresh-r{STATE['refresh_requests']}"
            self._send(200, payload)
            return
        self._send(400, {"error": "unsupported_grant_type"})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--token-delay-ms", type=int, default=0)
    args = parser.parse_args()
    STATE["token_delay_ms"] = args.token_delay_ms
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"PORT {server.server_address[1]}", flush=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        while True:
            line = sys.stdin.readline()
            if not line:
                break
    except KeyboardInterrupt:
        pass
    server.shutdown()


if __name__ == "__main__":
    main()
