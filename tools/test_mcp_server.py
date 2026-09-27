#!/usr/bin/env python3
"""A tiny stdio MCP server used by the app's connection tests.

It implements just enough of the protocol (initialize, tools/list, tools/call)
to exercise the client end to end without any network access:

* ``echo``        returns the text it was given
* ``write_frame`` writes a real PNG file and returns its path
* ``slow``        sleeps, to exercise client timeouts
* ``fail``        always answers with an MCP tool error
"""
import json
import os
import struct
import sys
import time
import zlib

PROTOCOL_VERSION = "2025-06-18"
OUTPUT_DIR = os.path.join(os.environ.get("TEMP", "."), "modal-gui-mcp-test")

TOOLS = [
    {
        "name": "echo",
        "description": "Echo the provided text back.",
        "inputSchema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
    {
        "name": "write_frame",
        "description": "Write a small PNG frame and return its path.",
        "inputSchema": {
            "type": "object",
            "properties": {"name": {"type": "string"}},
        },
    },
    {
        "name": "slow",
        "description": "Wait for the given number of seconds.",
        "inputSchema": {
            "type": "object",
            "properties": {"seconds": {"type": "number"}},
        },
    },
    {
        "name": "fail",
        "description": "Always fail, for error-path tests.",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def png_bytes(width: int = 96, height: int = 54) -> bytes:
    """A deterministic two-tone RGB PNG (no third-party libraries)."""
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        for x in range(width):
            if (x // 12 + y // 12) % 2 == 0:
                raw.extend((24, 40, 64))
            else:
                raw.extend((200, 120, 60))

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (
            struct.pack(">I", len(payload))
            + tag
            + payload
            + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + chunk(b"IEND", b"")
    )


def call_tool(name: str, arguments: dict) -> dict:
    if name == "echo":
        text = str(arguments.get("text", ""))
        return {"content": [{"type": "text", "text": f"echo: {text}"}]}
    if name == "write_frame":
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        base = str(arguments.get("name") or "frame")
        path = os.path.join(OUTPUT_DIR, f"{base}.png")
        with open(path, "wb") as handle:
            handle.write(png_bytes())
        return {
            "content": [{"type": "text", "text": path}],
            "structuredContent": {"path": path, "bytes": os.path.getsize(path)},
        }
    if name == "slow":
        time.sleep(float(arguments.get("seconds", 1)))
        return {"content": [{"type": "text", "text": "slept"}]}
    if name == "fail":
        return {
            "content": [{"type": "text", "text": "intentional failure"}],
            "isError": True,
        }
    raise ValueError(f"unknown tool: {name}")


def handle(message: dict):
    method = message.get("method")
    message_id = message.get("id")
    if method == "initialize":
        result = {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "modal-gui-test-server", "version": "0.1.0"},
        }
    elif method == "notifications/initialized":
        return None
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        params = message.get("params") or {}
        try:
            result = call_tool(str(params.get("name")), params.get("arguments") or {})
        except Exception as error:  # noqa: BLE001 - reported back to the client
            return {
                "jsonrpc": "2.0",
                "id": message_id,
                "error": {"code": -32602, "message": str(error)},
            }
    else:
        return {
            "jsonrpc": "2.0",
            "id": message_id,
            "error": {"code": -32601, "message": f"unsupported method: {method}"},
        }
    if message_id is None:
        return None
    return {"jsonrpc": "2.0", "id": message_id, "result": result}


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        response = handle(message)
        if response is not None:
            sys.stdout.write(json.dumps(response) + "\n")
            sys.stdout.flush()


if __name__ == "__main__":
    main()
