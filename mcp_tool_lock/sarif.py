"""指摘を SARIF 2.1.0 にする（GitHub の Code scanning に取り込める形式）。"""
from __future__ import annotations

import re

from .checks import RULES

LEVEL = {"高": "error", "中": "warning", "低": "note"}
SCORE = {"高": "8.0", "中": "5.0", "低": "3.0"}


def _line(text: str, tool: str) -> int:
    m = re.search(r'"name"\s*:\s*"' + re.escape(tool) + '"', text or "")
    return (text[: m.start()].count("\n") + 1) if m else 1


def build(findings: list[dict], texts: dict[str, str]) -> dict:
    rules = [{"id": rid, "name": title, "shortDescription": {"text": title}, "fullDescription": {"text": why},
              "helpUri": "https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/",
              "properties": {"tags": ["security", "mcp", *[x.strip() for x in owasp.split(",")]], "security-severity": SCORE[sev]}}
             for rid, (sev, title, why, owasp) in RULES.items()]
    results = [{"ruleId": f["ID"], "level": LEVEL[f["重さ"]],
                "message": {"text": f"[{f['サーバー']} / {f['道具']}] {f['指摘']}：{f['内容']}"},
                "locations": [{"physicalLocation": {"artifactLocation": {"uri": f["ファイル"].replace("\\", "/")},
                                                    "region": {"startLine": _line(texts.get(f["ファイル"], ""), f["道具"])}}}]}
               for f in findings]
    return {"$schema": "https://json.schemastore.org/sarif-2.1.0.json", "version": "2.1.0",
            "runs": [{"tool": {"driver": {"name": "mcp-tool-lock", "informationUri": "https://github.com/takashi-101/mcp-tool-lock",
                                          "version": "0.1.0", "rules": rules}}, "results": results}]}
