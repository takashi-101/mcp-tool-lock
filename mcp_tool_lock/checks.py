"""道具の定義（名前・説明・入力の定義・注釈）に仕込まれた危険を見つける。"""
from __future__ import annotations

import re

RULES = {
    "T01": ("高", "説明文への指示の埋め込み", "道具の説明にAIへの指示が書かれている（ツールポイズニング）", "ASI01 Agent Goal Hijack"),
    "T02": ("高", "認証情報のファイルへの言及", "鍵や設定ファイルの場所が説明に書かれている。読ませて送らせる手口に使われる", "ASI01, ASI03"),
    "T03": ("高", "見えない文字", "画面に表示されない文字が含まれている。人が読む説明とAIが読む内容が食い違う", "ASI01"),
    "T04": ("中", "他のサーバーの道具への言及", "別のサーバーの道具の使い方を指図している（ツールシャドーイング）", "ASI02 Tool Misuse"),
    "T05": ("高", "注釈と動作の食い違い", "「読み取りのみ」と申告しながら、削除・送信などの動作を示している", "ASI02"),
    "T06": ("低", "危険な動作に注釈なし", "削除・送信などの道具に readOnlyHint / destructiveHint が無い。承認を挟む判断に使えない", "ASI02"),
    "T07": ("中", "似せた名前", "英数字以外の文字を使った名前や、別のサーバーの道具と1文字違いの名前", "ASI04 Agentic Supply Chain"),
    "T08": ("中", "符号化された長い文字列", "Base64などの長いかたまりが説明に含まれている", "ASI01"),
    "T09": ("低", "長すぎる説明", "説明が1,500文字を超えている。人が読み切れない", "ASI01"),
    "R01": ("高", "承認後の書き換え", "固定した定義から変わっている（ラグプル）。もう一度確かめてから固定し直す", "ASI04"),
    "R02": ("中", "承認していない道具の追加", "固定したときに無かった道具が増えている", "ASI04"),
}

INSTRUCTION = [re.compile(p, re.I) for p in (
    r"ignore (all |any )?(the )?(previous|prior|above|earlier) (instructions|prompts|rules)",
    r"(do not|don't|never) (tell|inform|mention|reveal|show)\b.{0,20}\b(user|this)",
    r"<\s*/?\s*(important|system|instructions?)\s*>",
    r"before (using|calling|invoking) (this|any|the) tool",
    r"\bsystem prompt\b",
    r"\byou (must|should) (always |first )",
    r"\b(secretly|covertly)\b",
    r"\bsilently\s+(send|read|upload|include|copy|forward|pass|add|attach|exfiltrate)",
    r"(ユーザー|利用者)に(は)?(伝え|知らせ|言わ|見せ|表示し)(ない|るな|てはいけない)",
    r"(以前|前|上記|これまで)の指示を(無視|忘れ)",
    r"必ず(最初に|先に|事前に)",
    r"こっそり|密かに|気付かれ",
)]
CREDENTIAL = re.compile(r"~/\.ssh|id_rsa|id_ed25519|\.aws/credentials|\.netrc|\.npmrc|\.env\b|mcp\.json|claude_desktop_config"
                        r"|\.git-credentials|known_hosts|秘密鍵", re.I)
INVISIBLE = re.compile("[\u200b-\u200f\u2028-\u202e\u2060-\u2064\u2066-\u2069\ufeff\U000e0000-\U000e007f]")
# 道具の動作は「名前の先頭の語」と「説明の最初の動詞」で判断する（説明の途中に出る語では判断しない）。
# 公式の参照サーバーで試したとき、説明の途中の「send」「update」「run」で誤検出したための設計。
ACTION_VERBS = {"delete", "remove", "drop", "truncate", "write", "overwrite", "update", "edit", "move", "rename",
                "send", "post", "publish", "upload", "transfer", "pay", "purge", "kill", "exec", "execute", "run"}
JA_ACTION = re.compile(r"^(削除|消去|送信|書き込|上書|更新|送金|支払|実行)")
CLIENT_NOTICE = re.compile(r"^sends?\b.{0,40}\b(notification|log|progress)", re.I)


def action_of(tool: dict) -> str | None:
    """道具が書き換え・送信・実行をするかを、名前の先頭の語と説明の最初の動詞から判断する。"""
    name = str(tool.get("name", ""))
    first = re.split(r"[_\-\s.]|(?<=[a-z])(?=[A-Z])", name)[0].lower()
    desc = str(tool.get("description", "")).strip()
    lead = re.match(r"[A-Za-z]+", desc)
    verb = lead.group(0).lower() if lead else ""
    verb = verb[:-1] if verb.endswith("s") and verb[:-1] in ACTION_VERBS else verb
    if first in ACTION_VERBS:
        return first
    if verb in ACTION_VERBS and not CLIENT_NOTICE.match(desc):  # クライアントへの通知・ログは外部への送信に数えない
        return verb
    m = JA_ACTION.match(desc)
    return m.group(0) if m else None
BLOB = re.compile(r"[A-Za-z0-9+/]{60,}={0,2}|[0-9a-fA-F]{64,}")


def strings_read_by_model(tool: dict) -> list[tuple[str, str]]:
    """AIが読む文字列を（場所, 文字列）で集める。入力の定義の説明や列挙値も含める。"""
    out = [("name", str(tool.get("name", ""))), ("title", str(tool.get("title", ""))), ("description", str(tool.get("description", "")))]

    def walk(node, where):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("description", "title") and isinstance(v, str):
                    out.append((f"{where}.{k}", v))
                elif k == "properties" and isinstance(v, dict):
                    for pname, pv in v.items():
                        out.append((f"{where}.properties.{pname}（名前）", str(pname)))
                        walk(pv, f"{where}.properties.{pname}")
                elif k in ("enum", "examples", "default"):
                    out.extend((f"{where}.{k}", str(x)) for x in (v if isinstance(v, list) else [v]))
                elif isinstance(v, (dict, list)):
                    walk(v, f"{where}.{k}")
        elif isinstance(node, list):
            for i, x in enumerate(node):
                walk(x, f"{where}[{i}]")

    walk(tool.get("inputSchema") or {}, "inputSchema")
    return [(w, s) for w, s in out if s]


def _osa(a: str, b: str) -> int:
    """隣り合う文字の入れ替えも1回と数える編集距離。"""
    d = [[i + j if i * j == 0 else 0 for j in range(len(b) + 1)] for i in range(len(a) + 1)]
    for i in range(1, len(a) + 1):
        for j in range(1, len(b) + 1):
            cost = a[i - 1] != b[j - 1]
            d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
            if i > 1 and j > 1 and a[i - 1] == b[j - 2] and a[i - 2] == b[j - 1]:
                d[i][j] = min(d[i][j], d[i - 2][j - 2] + 1)
    return d[-1][-1]


def check(snapshots: list[dict]) -> list[dict]:
    """全サーバーの道具を点検し、指摘の一覧を返す。"""
    findings = []
    names = {(s["server"], str(t.get("name", ""))) for s in snapshots for t in s["tools"]}

    def add(rid, snap, tool, where, detail):
        sev, title, why, owasp = RULES[rid]
        findings.append({"ID": rid, "重さ": sev, "指摘": title, "サーバー": snap["server"], "道具": tool, "場所": where,
                         "内容": " ".join(detail.split())[:160], "理由": why, "OWASP": owasp, "ファイル": snap.get("path", "")})

    for snap in snapshots:
        for t in snap["tools"]:
            name = str(t.get("name", ""))
            texts = strings_read_by_model(t)
            for where, s in texts:
                if any(p.search(s) for p in INSTRUCTION):
                    add("T01", snap, name, where, s)
                if CREDENTIAL.search(s):
                    add("T02", snap, name, where, CREDENTIAL.search(s).group(0))
                if INVISIBLE.search(s):
                    add("T03", snap, name, where, f"U+{ord(INVISIBLE.search(s).group(0)):04X}")
                if BLOB.search(s):
                    add("T08", snap, name, where, BLOB.search(s).group(0)[:40] + "…")
            desc = " ".join(s for w, s in texts if w != "name")
            for other_server, other in sorted(names):
                if other_server != snap["server"] and len(other) >= 4 and re.search(rf"\b{re.escape(other)}\b", desc):
                    add("T04", snap, name, "description", f"{other_server} の {other}")
            ann = t.get("annotations") or {}
            act = action_of(t)
            if act and ann.get("readOnlyHint") is True:
                add("T05", snap, name, "annotations.readOnlyHint", f"readOnlyHint=true だが「{act}」")
            elif act and ann.get("destructiveHint") is False and re.match(r"delete|remove|drop|truncate|overwrite|purge|削除|消去|上書", act, re.I):
                add("T05", snap, name, "annotations.destructiveHint", f"destructiveHint=false だが「{act}」")
            elif act and "readOnlyHint" not in ann and "destructiveHint" not in ann:
                add("T06", snap, name, "annotations", f"「{act}」")
            if not name.isascii():
                add("T07", snap, name, "name", "英数字以外の文字を含む名前")
            for other_server, other in sorted(names):
                if name.isascii() and not other.isascii():
                    continue  # 似せた側（英数字以外を含む側）だけに付ける
                if other_server != snap["server"] and other != name and _osa(name.lower(), other.lower()) == 1:
                    add("T07", snap, name, "name", f"{other_server} の {other} と1文字違い")
            if len(str(t.get("description", ""))) > 1500:
                add("T09", snap, name, "description", f"{len(str(t.get('description', '')))}文字")
    order = {"高": 0, "中": 1, "低": 2}
    return sorted(findings, key=lambda f: (order[f["重さ"]], f["サーバー"], f["道具"], f["ID"]))
