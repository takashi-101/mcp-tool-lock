"""tools/list の結果を読む。手元で起動するMCPサーバーから取得することもできる。"""
from __future__ import annotations

import json
import os
import shlex
# 利用者が指定した手元のMCPサーバーを起動するために使う（shellは使わない）
import subprocess  # nosec B404
from pathlib import Path

PROTOCOL = "2025-06-18"


def load(path: str) -> dict:
    """{"server": 名前, "tools": [...], "path": ファイル, "text": 本文} を返す。"""
    text = Path(path).read_text(encoding="utf-8")
    data = json.loads(text)
    if isinstance(data, list):
        tools, server = data, None
    else:
        tools = data.get("tools") or (data.get("result") or {}).get("tools") or []
        server = data.get("server")
    return {"server": server or Path(path).stem, "tools": [t for t in tools if isinstance(t, dict)], "path": path, "text": text}


def fetch(command: str, timeout: int = 20) -> dict:
    """手元のMCPサーバー（標準入出力）を起動し、initialize → tools/list の結果を返す。道具は呼び出さない。"""
    msgs = [
        {"jsonrpc": "2.0", "id": 1, "method": "initialize",
         "params": {"protocolVersion": PROTOCOL, "capabilities": {}, "clientInfo": {"name": "mcp-tool-lock", "version": "0.1.0"}}},
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    # Windowsのパスの「\」を消さないよう、Windowsでは非POSIX方式で分け、前後の引用符だけ外す
    argv = shlex.split(command) if os.name != "nt" else [t.strip('"') for t in shlex.split(command, posix=False)]
    proc = subprocess.run(argv, input="\n".join(json.dumps(m) for m in msgs) + "\n",  # noqa: S603  # nosec B603
                          capture_output=True, text=True, encoding="utf-8", timeout=timeout, check=False)
    for line in proc.stdout.splitlines():
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        if msg.get("id") == 2 and "result" in msg:
            return {"tools": msg["result"].get("tools", [])}
    raise RuntimeError(f"tools/list の応答が得られませんでした（終了コード {proc.returncode}）")
