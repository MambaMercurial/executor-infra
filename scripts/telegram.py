#!/usr/bin/env python3
"""
telegram.py — the approval channel. Blake-style: agent proposes, you tap YES.

Setup (one time):
  1. In Telegram, message @BotFather → /newbot → get TELEGRAM_BOT_TOKEN.
  2. Message your new bot anything, then visit
     https://api.telegram.org/bot<TOKEN>/getUpdates to find your chat id.
  3. export TELEGRAM_BOT_TOKEN=... ; export TELEGRAM_CHAT_ID=...
     (put them in ~/.executor.env and `source` it in cron.)

Usage:
  python3 scripts/telegram.py send "message"
  python3 scripts/telegram.py propose <id>     # sends state/pending/<id>.json summary
  python3 scripts/telegram.py wait <id>        # blocks until 'YES <id>' or 'NO <id>' (30 min timeout)
Exit codes for wait: 0=APPROVED, 1=DENIED, 2=TIMEOUT
"""
import json, os, sys, time, urllib.parse, urllib.request

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
CHAT  = os.environ.get("TELEGRAM_CHAT_ID", "")
API   = f"https://api.telegram.org/bot{TOKEN}"
TIMEOUT_MIN = 30

def call(method, **params):
    data = urllib.parse.urlencode(params).encode()
    with urllib.request.urlopen(f"{API}/{method}", data=data, timeout=30) as r:
        return json.load(r)

def send(text):
    return call("sendMessage", chat_id=CHAT, text=text)

def propose(pid):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    p = json.load(open(os.path.join(root, "state", "pending", f"{pid}.json")))
    msg = (f"🔔 TRADE PROPOSAL {pid}\n"
           f"{p['side'].upper()} {p['symbol']} — {p['sleeve']}\n"
           f"${p['notional']:.2f} @ ~{p['entry']}\n"
           f"Stop {p.get('stop','—')} · Target {p.get('target','—')}\n"
           f"Max loss ${p.get('max_loss',0):.2f}\n"
           f"Thesis: {p.get('thesis','')}\n\n"
           f"Reply:  YES {pid}   or   NO {pid}")
    send(msg)
    print(f"proposed {pid}")

def wait(pid):
    deadline = time.time() + TIMEOUT_MIN * 60
    offset = None
    yes, no = f"yes {pid}".lower(), f"no {pid}".lower()
    while time.time() < deadline:
        params = {"timeout": 25}
        if offset: params["offset"] = offset
        try:
            updates = call("getUpdates", **params)
        except Exception:
            time.sleep(5); continue
        for u in updates.get("result", []):
            offset = u["update_id"] + 1
            txt = (u.get("message", {}) or {}).get("text", "").strip().lower()
            chat = str((u.get("message", {}) or {}).get("chat", {}).get("id", ""))
            if chat != str(CHAT):   # only the operator can approve
                continue
            if txt == yes:
                send(f"✅ {pid} APPROVED — executing."); print("APPROVED"); sys.exit(0)
            if txt == no:
                send(f"🛑 {pid} DENIED — standing down."); print("DENIED"); sys.exit(1)
        time.sleep(2)
    send(f"⌛ {pid} timed out with no approval — standing down.")
    print("TIMEOUT"); sys.exit(2)

if __name__ == "__main__":
    if not TOKEN or not CHAT:
        print("Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID first."); sys.exit(3)
    cmd = sys.argv[1]
    if cmd == "send":    send(sys.argv[2]); print("sent")
    elif cmd == "propose": propose(sys.argv[2])
    elif cmd == "wait":  wait(sys.argv[2])
