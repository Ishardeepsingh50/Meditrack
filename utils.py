"""utils.py - Small helpers for readable console output."""
import json
from datetime import datetime, date
from bson import ObjectId, Decimal128


def _default(o):
    if isinstance(o, (datetime, date)):
        return o.strftime("%Y-%m-%d") if o.hour == 0 and o.minute == 0 else o.isoformat(timespec="minutes")
    if isinstance(o, ObjectId):
        return str(o)
    if isinstance(o, Decimal128):
        return float(o.to_decimal())
    return str(o)


def pretty(obj) -> str:
    return json.dumps(obj, indent=2, default=_default, ensure_ascii=False)


def banner(title: str, char: str = "=") -> None:
    print("\n" + char * 78)
    print(f" {title}")
    print(char * 78)


def show(title: str, docs, limit: int = 5) -> None:
    """Print a title followed by up to `limit` documents."""
    print(f"\n--- {title}")
    if isinstance(docs, (dict, str, int, float)) or docs is None:
        print(pretty(docs) if isinstance(docs, dict) else docs)
        return
    docs = list(docs)
    print(f"({len(docs)} result{'s' if len(docs) != 1 else ''})")
    for d in docs[:limit]:
        print(pretty(d))
    if len(docs) > limit:
        print(f"... {len(docs) - limit} more not shown")


def table(rows, columns) -> None:
    """Print a list of dicts as an aligned text table."""
    if not rows:
        print("(no rows)")
        return
    def fmt(v):
        if isinstance(v, float):
            return f"{v:,.2f}".rstrip("0").rstrip(".") if v != int(v) else f"{int(v):,}"
        if isinstance(v, datetime):
            return v.strftime("%Y-%m-%d")
        return str(v)
    rows = [{c: fmt(r.get(c, "")) for c in columns} for r in rows]
    widths = [max(len(c), *(len(r[c]) for r in rows)) + 2 for c in columns]
    line = "".join(c.upper().ljust(w) for c, w in zip(columns, widths))
    print(line)
    print("-" * len(line))
    for r in rows:
        print("".join(r[c].ljust(w) for c, w in zip(columns, widths)))
