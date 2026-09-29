#!/usr/bin/env python3
"""KLM scorer for Modal GUI flow audits.

Deterministic arithmetic only — no aesthetics, no judgement. Turns a click sequence
into a mental-operator count and a predicted execution time, so a flow change can be
argued with numbers instead of taste.

Operators (Card/Moran/Newell 1980):
    M  mental preparation (decide)     1.35 s
    P  pointing (move to target)       1.10 s
    H  homing (keyboard <-> mouse)     0.40 s
    K  keystroke                       0.20 s
    B  button press                    0.10 s

Usage:
    python klm_score.py score "M K K" "M H P B M P B"
    python klm_score.py steps "설정 열기" "동기화 누르기" "새로고침"
    python klm_score.py steps "저장=MK" "확인=MPB"
    python klm_score.py selftest

Exit codes: 0 ok, 1 usage/parse error, 2 selftest failure.
"""

from __future__ import annotations

import argparse
import json
import re
import sys

OPERATORS = {"M": 1.35, "P": 1.10, "H": 0.40, "K": 0.20, "B": 0.10}
TOKEN_RE = re.compile(r"^([MPHKB])(\d*)$", re.IGNORECASE)
# Default operator cost of a labelled step the caller did not decompose:
# decide (M) + move to target (P) + press (B).
DEFAULT_STEP = "MPB"


def _expand_run(raw: str) -> list[str] | None:
    """'MPB' / 'M2P3' -> ['M','P','B','M','M','P','P','P']; None if not a compact run."""
    pairs = re.findall(r"([MPHKB])(\d*)", raw, re.IGNORECASE)
    if not pairs:
        return None
    rebuilt = "".join(op.upper() + num for op, num in pairs)
    if rebuilt != raw.upper():
        return None
    tokens: list[str] = []
    for op, num in pairs:
        count = int(num) if num else 1
        if count < 1:
            raise ValueError(f"count must be >= 1 in {raw!r}")
        tokens.extend([op.upper()] * count)
    return tokens


def parse_sequence(text: str) -> list[str]:
    """'M K K' or compact 'MKK' -> ['M','K','K']; supports K3 repeat notation."""
    tokens: list[str] = []
    for raw in re.split(r"[\s,]+", text.strip()):
        if not raw:
            continue
        m = TOKEN_RE.match(raw)
        if m:
            op = m.group(1).upper()
            count = int(m.group(2)) if m.group(2) else 1
            if count < 1:
                raise ValueError(f"count must be >= 1 in {raw!r}")
            tokens.extend([op] * count)
            continue
        expanded = _expand_run(raw)
        if expanded is None:
            raise ValueError(
                f"unknown operator {raw!r} — use M/P/H/K/B (e.g. 'M K K' or 'MKK', K3 for repeats)"
            )
        tokens.extend(expanded)
    if not tokens:
        raise ValueError("empty sequence")
    return tokens


def score_tokens(tokens: list[str]) -> dict:
    seconds = round(sum(OPERATORS[t] for t in tokens), 2)
    return {
        "ops": " ".join(tokens),
        "steps": len(tokens),
        "mental": tokens.count("M"),
        "seconds": seconds,
    }


def score_one(text: str) -> dict:
    return score_tokens(parse_sequence(text))


def delta(a: dict, b: dict) -> dict:
    """Cost of b relative to a. Positive = b is more expensive than a."""
    return {
        "mental": b["mental"] - a["mental"],
        "seconds": round(b["seconds"] - a["seconds"], 2),
        "steps": b["steps"] - a["steps"],
        "ratio": round(b["seconds"] / a["seconds"], 2) if a["seconds"] else None,
    }


def _fmt_row(name: str, s: dict) -> str:
    return f"  {name:<22} ops={s['ops']:<28} M={s['mental']:<3} {s['seconds']:>6.2f} s"


def cmd_score(args: argparse.Namespace) -> int:
    results = []
    names = args.label or [f"path{i + 1}" for i in range(len(args.sequence))]
    for name, seq in zip(names, args.sequence):
        r = score_one(seq)
        r["label"] = name
        results.append(r)

    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0

    print("KLM score")
    for r in results:
        print(_fmt_row(r["label"], r))
    if len(results) >= 2:
        d = delta(results[0], results[1])
        sign = lambda v: f"{v:+g}"  # noqa: E731
        print(
            f"\n  Δ ({results[1]['label']} vs {results[0]['label']}): "
            f"M {sign(d['mental'])}, steps {sign(d['steps'])}, "
            f"{sign(d['seconds'])} s (x{d['ratio']})"
        )
        print("  → report ΔM first; seconds second.")
    return 0


def _step_to_ops(item: str) -> tuple[str, str]:
    """'저장=MK' -> ('저장','MK'); '저장' -> ('저장', DEFAULT_STEP)."""
    if "=" in item:
        label, _, ops = item.partition("=")
        label, ops = label.strip(), ops.strip()
        if not label or not ops:
            raise ValueError(f"malformed step {item!r} — expected 'label=OPS'")
        return label, ops
    return item.strip(), DEFAULT_STEP


def cmd_steps(args: argparse.Namespace) -> int:
    results = []
    for item in args.step:
        label, ops = _step_to_ops(item)
        r = score_one(ops)
        r["label"] = label
        results.append(r)

    total = score_tokens([t for r in results for t in parse_sequence(r["ops"])])
    if args.json:
        print(json.dumps({"steps": results, "total": total}, ensure_ascii=False, indent=2))
        return 0

    print(f"KLM score — {len(results)} steps")
    for r in results:
        print(_fmt_row(r["label"], r))
    print(f"\n  TOTAL  M={total['mental']} (decisions)   {total['seconds']:.2f} s")
    print("  → each step assumed to be M P B; pass 'label=OPS' to refine one step.")
    return 0


def cmd_selftest(_args: argparse.Namespace) -> int:
    failures: list[str] = []

    def check(name: str, got, want):
        if got != want:
            failures.append(f"{name}: got {got!r}, want {want!r}")
        else:
            print(f"  ok  {name} = {got}")

    print("selftest — textbook examples (About Face / Textbook of Usability)")
    shortcut = score_one("M K K")
    menu = score_one("M H P B M P B")
    check("Ctrl+S seconds", shortcut["seconds"], 1.75)
    check("menu seconds", menu["seconds"], 5.50)
    check("menu mental operators", menu["mental"], 2)
    check("menu is 3x shortcut", round(menu["seconds"] / shortcut["seconds"], 2), 3.14)

    check("repeat notation K3", parse_sequence("K3"), ["K", "K", "K"])
    check("compact run MPB", parse_sequence("MPB"), ["M", "P", "B"])
    check("compact with counts M2PB", parse_sequence("M2PB"), ["M", "M", "P", "B"])
    check("label without ops defaults to MPB", _step_to_ops("저장"), ("저장", "MPB"))
    check("extra confirm step costs its M", delta(shortcut, menu)["mental"], 1)

    if failures:
        print("\nFAIL")
        for f in failures:
            print(f"  - {f}")
        return 2
    print("\nOK")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="klm_score.py", description="Score interaction cost for Modal GUI flow audits."
    )
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_score = sub.add_parser("score", help="score explicit operator sequences")
    p_score.add_argument("sequence", nargs="+", help="e.g. \"M K K\" \"M H P B\"")
    p_score.add_argument("--label", nargs="*", help="names for the sequences, in order")
    p_score.add_argument("--json", action="store_true", help="machine-readable output")
    p_score.set_defaults(func=cmd_score)

    p_steps = sub.add_parser("steps", help="score labelled steps (default M P B each)")
    p_steps.add_argument("step", nargs="+", help="e.g. \"설정 열기\" \"저장=MPBMPB\"")
    p_steps.add_argument("--json", action="store_true", help="machine-readable output")
    p_steps.set_defaults(func=cmd_steps)

    p_self = sub.add_parser("selftest", help="verify the operator table")
    p_self.set_defaults(func=cmd_selftest)

    args = parser.parse_args(argv)
    if getattr(args, "label", None) and len(args.label) != len(args.sequence):
        parser.error("--label count must match the number of sequences")
    try:
        return args.func(args)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
