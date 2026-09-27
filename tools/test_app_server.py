#!/usr/bin/env python3
"""A mock Codex app-server used by the app's chat-adapter tests.

Speaks newline-delimited JSON-RPC over stdio and implements just the slice the
app uses: initialize, account/login/start, thread/start, turn/start,
turn/interrupt. During a turn it asks the host for fresh tokens through the
`account/chatgptAuthTokens/refresh` server request and then streams a canned
assistant message. Everything received is appended to --dump for assertions.
"""
import argparse
import json
import sys

STATE = {"dump": None}


def send(payload: dict) -> None:
    sys.stdout.write(json.dumps(payload, ensure_ascii=False) + "\n")
    sys.stdout.flush()


def dump(entry: dict) -> None:
    if not STATE["dump"]:
        return
    with open(STATE["dump"], "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def notify(method: str, params: dict) -> None:
    send({"jsonrpc": "2.0", "method": method, "params": params})


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dump", default=None)
    parser.add_argument("command", nargs="?")
    args = parser.parse_args()
    STATE["dump"] = args.dump
    pending_server_request = None
    thread_counter = [0]
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        message = json.loads(line)
        dump(message)
        if "method" not in message:
            # A response to our refresh request.
            pending_server_request = message
            continue
        method = message.get("method")
        message_id = message.get("id")
        if method == "initialize":
            send({"jsonrpc": "2.0", "id": message_id, "result": {"userAgent": "mock-app-server"}})
        elif method == "account/login/start":
            send({"jsonrpc": "2.0", "id": message_id, "result": {}})
        elif method == "thread/start":
            # Each thread/start gets its own id so a client can be checked for
            # keeping one thread per conversation instead of one per account.
            thread_counter[0] += 1
            send({"jsonrpc": "2.0", "id": message_id,
                  "result": {"thread": {"id": f"thread-test-{thread_counter[0]}"}}})
        elif method == "turn/start":
            params = message.get("params") or {}
            text = ""
            for item in params.get("input") or []:
                if item.get("type") == "text":
                    text = item.get("text", "")
            send({"jsonrpc": "2.0", "id": message_id, "result": {"turn": {"id": "turn-test-1"}}})
            notify("turn/started", {"threadId": params.get("threadId"), "turn": {"id": "turn-test-1"}})
            # Ask the host for tokens, like the real runtime does on a 401.
            send({
                "jsonrpc": "2.0",
                "id": 9001,
                "method": "account/chatgptAuthTokens/refresh",
                "params": {"reason": "unauthorized", "previousAccountId": "acct-test-1"},
            })
            reply = text
            for chunk in [f"mock reply: {reply}", " (done)"]:
                notify("item/agentMessage/delta", {
                    "threadId": params.get("threadId"),
                    "turnId": "turn-test-1",
                    "itemId": "item-1",
                    "delta": chunk,
                })
            notify("turn/completed", {
                "threadId": params.get("threadId"),
                "turn": {"id": "turn-test-1", "status": "completed"},
            })
        elif method == "turn/interrupt":
            params = message.get("params") or {}
            send({"jsonrpc": "2.0", "id": message_id, "result": {}})
            notify("turn/completed", {
                "threadId": params.get("threadId"),
                "turn": {"id": params.get("turnId"), "status": "interrupted"},
            })
        else:
            send({"jsonrpc": "2.0", "id": message_id, "error": {"code": -32601, "message": f"unsupported: {method}"}})


if __name__ == "__main__":
    main()
