"""承認した道具の定義をハッシュで固定し、あとから書き換えられていないかを確かめる。"""
from __future__ import annotations

import hashlib
import json

from .checks import RULES

PARTS = ("description", "inputSchema", "outputSchema", "annotations", "title")


def _h(obj) -> str:
    return hashlib.sha256(json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def tool_digest(tool: dict) -> dict:
    return {"all": _h({k: tool.get(k) for k in ("name", *PARTS)}), **{k: _h(tool.get(k)) for k in PARTS}}


def build(snapshots: list[dict]) -> dict:
    servers = {}
    for s in snapshots:
        tools = {str(t.get("name", "")): tool_digest(t) for t in s["tools"]}
        servers[s["server"]] = {"fingerprint": _h(sorted(v["all"] for v in tools.values())), "tools": tools}
    return {"lockfileVersion": 1, "servers": servers}


def _f(rid, snap, tool, detail):
    sev, title, why, owasp = RULES[rid]
    return {"ID": rid, "重さ": sev, "指摘": title, "サーバー": snap["server"], "道具": tool, "場所": "lock",
            "内容": detail, "理由": why, "OWASP": owasp, "ファイル": snap.get("path", "")}


def verify(snapshots: list[dict], locked: dict) -> list[dict]:
    out = []
    for s in snapshots:
        base = locked.get("servers", {}).get(s["server"])
        now = {str(t.get("name", "")): tool_digest(t) for t in s["tools"]}
        if base is None:
            out += [_f("R02", s, n, "サーバーごと未登録") for n in now]
            continue
        for n, d in now.items():
            if n not in base["tools"]:
                out.append(_f("R02", s, n, "追加された道具"))
            elif d["all"] != base["tools"][n]["all"]:
                parts = [k for k in PARTS if d[k] != base["tools"][n].get(k)]
                out.append(_f("R01", s, n, "変わった部分：" + "、".join(parts)))
        out += [_f("R01", s, n, "削除された道具") for n in base["tools"] if n not in now]
    return out
