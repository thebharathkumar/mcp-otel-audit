"""Tabulate Weaver live-check output across all targets into a quick-look table.

Reads captures/<target>.weaver.json for each known target and prints a
consolidated table. Run after `make score-all`. The hand-written report
in reports/REPORT.md is the canonical artifact; this is a sanity-check
helper so you can eyeball the captures.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

TARGETS = ["traceloop", "fastmcp", "logfire", "splunk"]


def walk_advice(o):
    """Yield every entry from any nested 'all_advice' list."""
    if isinstance(o, dict):
        if isinstance(o.get("all_advice"), list):
            yield from o["all_advice"]
        for v in o.values():
            yield from walk_advice(v)
    elif isinstance(o, list):
        for x in o:
            yield from walk_advice(x)


def summarize(path: Path) -> dict:
    j = json.loads(path.read_text())
    by_id: Counter[str] = Counter()
    by_level: Counter[str] = Counter()
    for advice in walk_advice(j):
        if isinstance(advice, dict):
            by_id[advice.get("id", "?")] += 1
            by_level[advice.get("level", "?")] += 1
    stats = j.get("statistics", {}) or {}
    seen_attrs = sorted(
        k for k, v in (stats.get("seen_registry_attributes") or {}).items() if v
    )
    return {
        "by_id": dict(by_id.most_common()),
        "by_level": dict(by_level.most_common()),
        "total_entities": stats.get("total_entities"),
        "total_advisories": stats.get("total_advisories"),
        "seen_attrs": seen_attrs,
    }


def main() -> int:
    base = Path(sys.argv[1] if len(sys.argv) > 1 else "captures")
    if not base.exists():
        print(f"no captures dir: {base}", file=sys.stderr)
        return 2

    print()
    print("Quick-look summary (run after `make score-all`)")
    print("=" * 64)
    for t in TARGETS:
        f = base / f"{t}.weaver.json"
        if not f.exists():
            print(f"\n## {t}: MISSING (run scripts/score.sh {t})")
            continue
        s = summarize(f)
        print(f"\n## {t}")
        print(f"  entities={s['total_entities']} advisories={s['total_advisories']}")
        print(f"  by level: {s['by_level']}")
        print(f"  by id:    {s['by_id']}")
        mcp_attrs = [a for a in s["seen_attrs"] if a.startswith("mcp.") or a.startswith("gen_ai.")]
        print(f"  MCP/gen_ai attrs seen: {mcp_attrs or '(none)'}")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
