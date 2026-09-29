"""Validate archived graph bytes and structure without importing Modal or ComfyUI."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "workflows" / "comfyui" / "snapshots"


def main() -> int:
    checked = 0
    catalogs = sorted(ROOT.glob("*/catalog.json"))
    if not catalogs:
        raise ValueError("No workflow catalogs found")
    for catalog in catalogs:
        data = json.loads(catalog.read_text(encoding="utf-8-sig"))
        listed = set()
        for record in data["files"]:
            relative = record["path"]
            path = (catalog.parent / relative).resolve()
            if not path.is_relative_to(catalog.parent.resolve()):
                raise ValueError("Catalog path escapes snapshot directory")
            if relative in listed:
                raise ValueError(f"Duplicate catalog entry: {relative}")
            listed.add(relative)
            raw = path.read_bytes()
            if len(raw) != record["bytes"] or hashlib.sha256(raw).hexdigest() != record["sha256"]:
                raise ValueError(f"Snapshot bytes differ: {relative}")
            graph = json.loads(raw.decode("utf-8-sig"))
            if isinstance(graph, dict) and isinstance(graph.get("nodes"), list):
                if not graph["nodes"] or not all(isinstance(n, dict) and "type" in n for n in graph["nodes"]):
                    raise ValueError(f"Malformed UI nodes: {relative}")
            elif isinstance(graph, dict) and isinstance(graph.get("prompt"), dict):
                if not graph["prompt"] or not all(
                    isinstance(n, dict) and "class_type" in n and isinstance(n.get("inputs"), dict)
                    for n in graph["prompt"].values()
                ):
                    raise ValueError(f"Malformed wrapped API graph: {relative}")
            elif isinstance(graph, dict) and graph and all(
                isinstance(n, dict) and "class_type" in n and isinstance(n.get("inputs"), dict)
                for n in graph.values()
            ):
                pass
            else:
                raise ValueError(f"Unknown graph structure: {relative}")
            checked += 1
        actual = {p.relative_to(catalog.parent).as_posix() for p in catalog.parent.rglob("*.json")
                  if p != catalog}
        if actual != listed:
            raise ValueError("Catalog does not cover all snapshot JSON files")
    print(f"OK: {checked} workflow snapshots; hashes and JSON structure verified; no remote execution")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
