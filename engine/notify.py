"""Telegram: notification + veto channel. NOT an approval gate anymore.

Outbound: every live order, fill, breaker trip, graduation, and daily summary.
Inbound commands (operator chat id only):
  HALT    — stop all live trading immediately (paper continues)
  RESUME  — clear HALT
  FLAT    — flatten every live position (GFV-safe), then HALT
  STATUS  — send current equity, positions, book stats
Silence from the operator means the system keeps running. That is the design.
"""
import json
import os
import urllib.parse
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OFFSET_PATH = os.path.join(ROOT, "state", ".tg_offset")

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT = os.environ.get("TELEGRAM_CHAT_ID", "")


def _call(method, timeout=20, **params):
    if not TOKEN:
        return {}
    data = urllib.parse.urlencode(params).encode()
    try:
        with urllib.request.urlopen(f"https://api.telegram.org/bot{TOKEN}/{method}", data=data, timeout=timeout) as r:
            return json.load(r)
    except Exception:
        return {}


def send(text):
    if TOKEN and CHAT:
        _call("sendMessage", chat_id=CHAT, text=text)


def poll_commands():
    """Return list of uppercase commands from the operator since last poll."""
    if not (TOKEN and CHAT):
        return []
    offset = None
    if os.path.exists(OFFSET_PATH):
        try:
            offset = int(open(OFFSET_PATH).read().strip())
        except Exception:
            offset = None
    params = {"timeout": 0}
    if offset:
        params["offset"] = offset
    updates = _call("getUpdates", **params)
    cmds = []
    last_id = offset
    for u in updates.get("result", []):
        last_id = u["update_id"] + 1
        msg = u.get("message") or {}
        if str((msg.get("chat") or {}).get("id", "")) != str(CHAT):
            continue
        txt = (msg.get("text") or "").strip().upper()
        if txt in ("HALT", "RESUME", "FLAT", "STATUS"):
            cmds.append(txt)
    if last_id and last_id != offset:
        os.makedirs(os.path.dirname(OFFSET_PATH), exist_ok=True)
        with open(OFFSET_PATH, "w") as f:
            f.write(str(last_id))
    return cmds
