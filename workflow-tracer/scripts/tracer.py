#!/usr/bin/env python3
"""Record a context trace: the folder tree, then every file an agent opens while routing a task.

    python -I tracer.py tree ROOT -d DIR [--depth 7] [--max-children 60] [--include-hidden]
    python -I tracer.py read PATH -d DIR --layer L2 --why "..." [--via FROM] [--named]
    python -I tracer.py scan "PATTERN" -d DIR --why "..."       # a glob/grep outside the catalog
    python -I tracer.py miss "WHAT" -d DIR --why "..."          # routing dead end
    python -I tracer.py done -d DIR --task "..." [--finding "..." ...]
    python -I tracer.py html -d DIR [-o FILE]                     # one self-contained page (tree and done run it too)

DIR holds tree.json (from `tree`), trace.jsonl (one line per step, appended as you go),
trace.json (written by `done`: steps, totals, invariant checks) and trace.html, the dashboard
with both json files inlined, rewritten by `tree`, `done` and `html`. Standard library only. Token counts are bytes/4, which is close enough to see a
budget blow.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

SKIP = {"node_modules", "__pycache__", ".git", ".trash", "dist", "build", ".scratch"}
CATALOG = {"agents.md", "claude.md", "gemini.md", "readme.md", "index.md", "_index.md"}
TEXT_EXT = {".md", ".txt", ".json", ".jsonl", ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".py",
            ".html", ".css", ".yaml", ".yml", ".toml", ".csv", ".sh", ".ps1", ".sql", ".xml", ".svg"}
BUDGET = 8000  # invariant 7: one contract plus its inputs
HOPS = 3       # entry file plus at most two more reads to reach the control point
ASSETS = Path(__file__).resolve().parent.parent / "assets"
DASH = ASSETS / "dashboard.html"
FAVICON = ASSETS / "brand" / "favicon.svg"   # Don's Bookshelf; the page's colours and fonts are its colors_and_type.css, inlined in dashboard.html


def skeleton() -> str:
    # dashboard.html is a fragment; this is the document around it, with the brand favicon embedded so the one file carries it.
    icon = ""
    if FAVICON.exists():
        from urllib.parse import quote
        icon = '<link rel="icon" type="image/svg+xml" href="data:image/svg+xml,' + quote(FAVICON.read_text(encoding="utf-8")) + '">'
    return ('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">' + icon +
            '<style>:root{color-scheme:light}body{margin:0;font:14px system-ui,sans-serif}img{max-width:100%}[hidden]{display:none!important}</style></head><body>')


def role_of(path: Path, is_dir: bool) -> str:
    parts = {p.lower() for p in path.parts}
    name = path.name.lower()
    if is_dir:
        if name in ("_templates", "templates"):
            return "template"
        if name in ("_tools", "scripts", "tools"):
            return "tool"
        if name in ("_shared", "references", "docs", "_meta"):
            return "factory"
        if name in ("output", "_archive", "archive"):
            return "product"
        if len(name) > 3 and name[:2].isdigit() and name[2] in "_-":
            return "stage"
        return "folder"
    if name in CATALOG:
        return "catalog"
    if name == "context.md":
        return "contract"
    if parts & {"_templates", "templates"}:
        return "template"
    if parts & {"_tools", "scripts", "tools"} or path.suffix.lower() in (".py", ".mjs", ".sh", ".ps1"):
        return "tool"
    if parts & {"_shared", "references", "docs", "_meta"}:
        return "factory"
    if parts & {"output", "_archive", "archive"}:
        return "product"
    return "file"


def tokens_of(path: Path, size: int) -> int:
    return size // 4 if path.suffix.lower() in TEXT_EXT or path.suffix == "" else 0


def walk(root: Path, cur: Path, depth: int, args) -> dict:
    rel = cur.relative_to(root).as_posix() or "."
    node = {"n": cur.name or str(cur), "p": rel, "d": True, "r": role_of(cur, True) if rel != "." else "root",
            "c": [], "files": 0, "t": 0}
    if depth >= args.depth:
        node["folded"] = True
    try:
        entries = sorted(cur.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower()))
    except OSError:
        return node
    kept = []
    for e in entries:
        if e.name in SKIP or (e.name.startswith(".") and not args.include_hidden):
            continue
        kept.append(e)
    shown = kept if depth < args.depth else []
    for e in shown[: args.max_children]:
        if e.is_dir():
            child = walk(root, e, depth + 1, args)
        else:
            size = e.stat().st_size
            child = {"n": e.name, "p": e.relative_to(root).as_posix(), "d": False,
                     "r": role_of(e.relative_to(root), False), "b": size, "t": tokens_of(e, size)}
        node["c"].append(child)
    if len(shown) > args.max_children:
        node["c"].append({"n": f"+{len(shown) - args.max_children} more", "p": rel + "/…", "d": False, "r": "more", "b": 0, "t": 0})
    # counts cover the whole subtree even when folded, so a collapsed folder still says its size
    for e in kept:
        if e.is_dir():
            sub = next((c for c in node["c"] if c["p"] == e.relative_to(root).as_posix()), None)
            if sub:
                node["files"] += sub["files"]
                node["t"] += sub["t"]
            else:
                for dp, dn, fn in os.walk(e):
                    dn[:] = [d for d in dn if d not in SKIP and (args.include_hidden or not d.startswith("."))]
                    for f in fn:
                        fp = Path(dp) / f
                        try:
                            s = fp.stat().st_size
                        except OSError:
                            continue
                        node["files"] += 1
                        node["t"] += tokens_of(fp, s)
        else:
            node["files"] += 1
            node["t"] += tokens_of(e, e.stat().st_size)
    return node


def cmd_tree(args):
    root = Path(args.root).resolve()
    out = Path(args.dir)
    out.mkdir(parents=True, exist_ok=True)
    tree = walk(root, root, 0, args)
    tree["n"] = root.name or str(root)
    data = {"root": str(root), "generated": time.strftime("%Y-%m-%d %H:%M"), "tree": tree}
    (out / "tree.json").write_text(json.dumps(data), encoding="utf-8")
    (out / "trace.jsonl").write_text("", encoding="utf-8")
    (out / "trace.json").write_text(json.dumps({"root": str(root), "task": "", "steps": [], "pending": True}), encoding="utf-8")
    print(f"tree.json: {tree['files']} files, ~{tree['t']:,} tokens under {root}")
    write_html(args)


def write_html(args, out_file=None):
    out = Path(args.dir)
    tree = (out / "tree.json").read_text(encoding="utf-8")
    trace = (out / "trace.json").read_text(encoding="utf-8")
    page = DASH.read_text(encoding="utf-8")
    # A "</" inside the json (a why line quoting html) would close the script tag early; escape it.
    body = f"{{tree:{tree},trace:{trace}}}".replace("</", "<\\/")
    data = f"<script>window.TRACE_DATA={body}</script>\n"
    html = skeleton() + data + page + "</body></html>"
    dest = Path(out_file or args.out or out / "trace.html")
    dest.write_text(html, encoding="utf-8")
    print(f"html: {dest}")


def cmd_html(args):
    write_html(args)


def append(args, step):
    out = Path(args.dir)
    lines = (out / "trace.jsonl").read_text(encoding="utf-8").splitlines() if (out / "trace.jsonl").exists() else []
    step["i"] = len(lines) + 1
    step["at"] = time.strftime("%H:%M:%S")
    with (out / "trace.jsonl").open("a", encoding="utf-8") as f:
        f.write(json.dumps(step) + "\n")
    rng = f" (lines {step['lines'][0]}-{step['lines'][1]} of ~{step['bytes'] // 4:,})" if step.get("lines") else ""
    print(f"{step['i']:>2}. {step['kind']:<4} {step.get('path') or step.get('what')}  [{step.get('layer', '-')}] ~{step.get('tokens', 0):,} tok{rng}")


def rel_to_root(args, p: str) -> str:
    root = Path(json.loads((Path(args.dir) / "tree.json").read_text(encoding="utf-8"))["root"])
    path = Path(p)
    if not path.is_absolute():
        path = (Path.cwd() / path)
    try:
        return path.resolve().relative_to(root.resolve()).as_posix(), path
    except ValueError:
        return path.as_posix(), path


def cmd_read(args):
    rel, path = rel_to_root(args, args.path)
    exists = path.exists() and path.is_file()
    size = path.stat().st_size if exists else 0
    step = {"kind": "named" if args.named else "read", "path": rel, "layer": args.layer, "why": args.why, "via": args.via,
            "exists": exists, "bytes": size, "tokens": 0 if args.named else tokens_of(path, size)}
    # --lines A-B: the walker opened a slice, so charge the slice. The whole-file size stays in "bytes" and on the
    # tree node; the step carries what was loaded. A 95k-token module read at one function is not a 95k read.
    if args.lines and exists and not args.named:
        a, b = (int(x) for x in args.lines.split("-"))
        chunk = b"".join(path.read_bytes().splitlines(keepends=True)[a - 1:b])
        step.update({"lines": [a, b], "loaded": len(chunk), "tokens": tokens_of(path, len(chunk))})
    # --named: the contract names it as an input and the walker checked it exists, but did not open it. No tokens.
    append(args, step)


def cmd_scan(args):
    append(args, {"kind": "scan", "what": args.pattern, "path": args.pattern, "layer": "-", "why": args.why, "tokens": 0})


def cmd_miss(args):
    append(args, {"kind": "miss", "what": args.what, "path": args.what, "layer": "-", "why": args.why, "tokens": 0})


def cmd_done(args):
    out = Path(args.dir)
    steps = [json.loads(l) for l in (out / "trace.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    reads = [s for s in steps if s["kind"] == "read"]
    named = [s for s in steps if s["kind"] == "named"]
    l2 = next((s["i"] for s in reads if s["layer"] == "L2"), None)
    working = sum(s["tokens"] for s in reads if s["layer"] in ("L2", "L3", "L4"))
    total = sum(s["tokens"] for s in reads)
    # A read must exist. A named path is this run's input or output, which may not be made yet: it passes if its
    # folder exists, or if it is a placeholder (runs/<id>/...), the same rule links.py applies to working inputs.
    root = Path(json.loads((out / "tree.json").read_text(encoding="utf-8"))["root"])
    def named_ok(s):
        if s["exists"] or "<" in s["path"]:
            return True
        p = Path(s["path"])
        return ((p if p.is_absolute() else root / p).parent).exists()
    missing = [s["path"] for s in reads if not s["exists"]] + [s["path"] for s in named if not named_ok(s)]
    scans = [s for s in steps if s["kind"] == "scan"]
    misses = [s for s in steps if s["kind"] == "miss"]
    checks = [
        {"name": "Control point within entry + 2 reads", "pass": l2 is not None and l2 <= HOPS,
         "note": f"stage contract reached at read {l2}" if l2 else "no L2 contract was reached"},
        {"name": f"Contract plus inputs under {BUDGET:,} tokens", "pass": working <= BUDGET,
         "note": f"~{working:,} tokens across L2-L4 (~{total:,} with routing)"},
        {"name": "Routed by the catalog, not by search", "pass": not scans and not misses,
         "note": f"{len(scans)} scan(s), {len(misses)} dead end(s)"},
        {"name": "Every path read exists", "pass": not missing,
         "note": "all resolved" if not missing else "missing: " + ", ".join(missing)},
    ]
    data = {"root": json.loads((out / "tree.json").read_text(encoding="utf-8"))["root"], "task": args.task,
            "finished": time.strftime("%Y-%m-%d %H:%M"), "steps": steps,
            "totals": {"reads": len(reads), "named": len(named), "tokens": total, "working": working, "scans": len(scans),
                       "misses": len(misses), "l2_at": l2},
            "checks": checks, "findings": args.finding or []}
    (out / "trace.json").write_text(json.dumps(data), encoding="utf-8")
    for c in checks:
        print(("PASS " if c["pass"] else "FAIL ") + c["name"] + " - " + c["note"])
    print(f"trace.json: {len(reads)} reads, ~{total:,} tokens")
    write_html(args)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    t = sub.add_parser("tree"); t.add_argument("root"); t.add_argument("-d", "--dir", required=True)
    t.add_argument("--depth", type=int, default=7); t.add_argument("--max-children", type=int, default=60)
    t.add_argument("--include-hidden", action="store_true"); t.add_argument("-o", "--out"); t.set_defaults(fn=cmd_tree)
    r = sub.add_parser("read"); r.add_argument("path"); r.add_argument("-d", "--dir", required=True)
    r.add_argument("--layer", default="L4", choices=["L0", "L1", "L2", "L3", "L4"])
    r.add_argument("--why", required=True); r.add_argument("--via", default="")
    r.add_argument("--named", action="store_true", help="named as an input and checked, not opened")
    r.add_argument("--lines", help="A-B: only these lines were read; tokens are charged for the slice"); r.set_defaults(fn=cmd_read)
    s = sub.add_parser("scan"); s.add_argument("pattern"); s.add_argument("-d", "--dir", required=True)
    s.add_argument("--why", required=True); s.set_defaults(fn=cmd_scan)
    m = sub.add_parser("miss"); m.add_argument("what"); m.add_argument("-d", "--dir", required=True)
    m.add_argument("--why", required=True); m.set_defaults(fn=cmd_miss)
    d = sub.add_parser("done"); d.add_argument("-d", "--dir", required=True); d.add_argument("--task", required=True)
    d.add_argument("--finding", action="append"); d.add_argument("-o", "--out"); d.set_defaults(fn=cmd_done)
    h = sub.add_parser("html"); h.add_argument("-d", "--dir", required=True); h.add_argument("-o", "--out"); h.set_defaults(fn=cmd_html)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
