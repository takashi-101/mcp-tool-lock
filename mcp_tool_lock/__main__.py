"""使い方：
  python -m mcp_tool_lock check  スナップショット.json ... [--sarif out.sarif] [--fail-on 高]
  python -m mcp_tool_lock lock   スナップショット.json ... --lock mcp-tools.lock.json
  python -m mcp_tool_lock verify スナップショット.json ... --lock mcp-tools.lock.json
  python -m mcp_tool_lock snapshot --cmd "python server.py" --server 名前 --out スナップショット.json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import checks, lock, sarif, snapshot

ORDER = {"高": 0, "中": 1, "低": 2}


def _print(findings):
    if not findings:
        print("指摘はありません。")
    for f in findings:
        print(f"[{f['重さ']}] {f['ID']} {f['指摘']}｜{f['サーバー']} / {f['道具']}｜{f['場所']}｜{f['内容']}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="mcp_tool_lock", description="MCPの道具の定義を点検し、承認した定義を固定する")
    sub = p.add_subparsers(dest="action", required=True)
    c = sub.add_parser("check", help="道具の定義を点検する")
    c.add_argument("files", nargs="+")
    c.add_argument("--sarif")
    c.add_argument("--fail-on", choices=list(ORDER))
    lk = sub.add_parser("lock", help="今の定義を承認したものとして固定する")
    lk.add_argument("files", nargs="+")
    lk.add_argument("--lock", required=True)
    v = sub.add_parser("verify", help="固定した定義から変わっていないかを確かめる")
    v.add_argument("files", nargs="+")
    v.add_argument("--lock", required=True)
    sn = sub.add_parser("snapshot", help="手元のMCPサーバーを起動して道具の定義を保存する（道具は呼ばない）")
    sn.add_argument("--cmd", required=True)
    sn.add_argument("--server", required=True)
    sn.add_argument("--out", required=True)
    a = p.parse_args(argv)

    if a.action == "snapshot":
        data = {"server": a.server, **snapshot.fetch(a.cmd)}
        Path(a.out).write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"道具 {len(data['tools'])} 件を保存しました：{a.out}")
        return 0
    snaps = [snapshot.load(f) for f in a.files]
    if a.action == "lock":
        Path(a.lock).write_text(json.dumps(lock.build(snaps), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{len(snaps)} サーバー、道具 {sum(len(s['tools']) for s in snaps)} 件を固定しました：{a.lock}")
        return 0
    if a.action == "verify":
        fs = lock.verify(snaps, json.loads(Path(a.lock).read_text(encoding="utf-8")))
        _print(fs)
        return 1 if fs else 0
    fs = checks.check(snaps)
    _print(fs)
    if a.sarif:
        Path(a.sarif).write_text(json.dumps(sarif.build(fs, {s["path"]: s["text"] for s in snaps}), ensure_ascii=False, indent=2), encoding="utf-8")
    if a.fail_on:
        return 1 if any(ORDER[f["重さ"]] <= ORDER[a.fail_on] for f in fs) else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
