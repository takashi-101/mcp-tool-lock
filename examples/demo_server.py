"""試験用の小さなMCPサーバー（標準入出力）。tools/list に calc-server の定義を返す。"""
import json
import sys
from pathlib import Path

TOOLS = json.loads((Path(__file__).parent / "snapshots" / "calc-server.json").read_text(encoding="utf-8"))["tools"]

for line in sys.stdin:
    if not line.strip():
        continue
    msg = json.loads(line)
    if msg.get("method") == "initialize":
        res = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "demo", "version": "0"}}
    elif msg.get("method") == "tools/list":
        res = {"tools": TOOLS}
    else:
        continue
    sys.stdout.write(json.dumps({"jsonrpc": "2.0", "id": msg.get("id"), "result": res}) + "\n")
    sys.stdout.flush()
