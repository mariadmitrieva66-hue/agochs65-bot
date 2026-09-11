"""Бот @agochs65_bot для MAX Business — Webhook версия"""
import asyncio
import json
import logging
import os
import ssl
from datetime import datetime
from aiohttp import web
import aiohttp
from dotenv import load_dotenv

load_dotenv()
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# ========== НАСТРОЙКИ ==========
TOKEN = os.getenv("MAX_BOT_TOKEN")
WEBHOOK_URL = os.getenv("WEBHOOK_URL", "https://compliance-alternatives-promote-announced.trycloudflare.com/webhook")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
ADMIN_CHAT_ID = os.getenv("ADMIN_CHAT_ID", "")
BASE_URL = "https://platform-api2.max.ru"

if not TOKEN:
    raise RuntimeError("В .env не указан MAX_BOT_TOKEN")

ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE

session = None
user_states = {}

EMERGENCY_TYPES = {
    "em_fire": "🔥 Пожар",
    "em_flood": "🌊 Наводнение / Цунами",
    "em_accident": "🏚️ Обрушение / ДТП",
    "em_other": "⚠️ Другое",
}

# ========== API ==========
async def get_session():
    global session
    if session is None or session.closed:
        connector = aiohttp.TCPConnector(ssl=ssl_ctx)
        session = aiohttp.ClientSession(
            headers={"Authorization": TOKEN},
            connector=connector
        )
    return session

async def send_message(chat_id, text, reply_markup=None):
    s = await get_session()
    payload = {"text": text, "format": "markdown"}
    if reply_markup:
        payload["attachments"] = [reply_markup]
    try:
        async with s.post(f"{BASE_URL}/messages", json=payload, params={"chat_id": chat_id}) as resp:
            if resp.status == 200:
                logger.info(f"✅ Отправлено в чат {chat_id}")
            else:
                logger.error(f"❌ Ошибка: {resp.status} {await resp.text()}")
    except Exception as e:
        logger.error(f"Ошибка API: {e}")

async def register_webhook():
    if not WEBHOOK_URL:
        logger.warning("⚠️ WEBHOOK_URL не указан — пропускаю регистрацию")
        return
    s = await get_session()
    # Удаляем старые подписки
    try:
        async with s.delete(f"{BASE_URL}/subscriptions") as resp:
            logger.info("🧹 Старые вебхуки удалены")
    except:
        pass
    # Регистрируем новый
    payload = {
        "url": WEBHOOK_URL,
        "update_types": ["message_created", "message_callback", "bot_started"],
    }
    if WEBHOOK_SECRET:
        payload["secret"] = WEBHOOK_SECRET
    try:
        async with s.post(f"{BASE_URL}/subscriptions", json=payload) as resp:
            res = await resp.json()
            logger.info(f"✅ Webhook зарегистрирован: {res}")
    except Exception as e:
        logger.error(f"❌ Ошибка регистрации: {e}")

def save_incident(data):
    incident = {
        "id": datetime.now().strftime("%Y%m%d%H%M%S"),
        "timestamp": datetime.now().isoformat(),
        "user_id": data.get("user_id"),
        "username": data.get("username"),
        "type": data.get("type"),
        "location": data.get("location"),
        "details": data.get("details"),
    }
    try:
        incidents = []
        if os.path.exists("incidents.json"):
            with open("incidents.json", "r", encoding="utf-8") as f:
                incidents = json.load(f)
        incidents.append(incident)
        with open("incidents.json", "w", encoding="utf-8") as f:
            json.dump(incidents, f, ensure_ascii=False, indent=2)
        logger.info(f"💾 Заявка {incident['id']} сохранена")
        return True
    except Exception as e:
        logger.error(f"Ошибка сохранения: {e}")
        return False

# ========== КЛАВИАТУРЫ ==========
def get_main_kb():
    return {"type": "inline_keyboard", "payload": {"buttons": [
        [{"type": "callback", "text": "🚨 Сообщить о ЧС", "payload": "menu_report"}],
        [{"type": "callback", "text": "🌩️ Предупреждения", "payload": "menu_alerts"},
         {"type": "callback", "text": "📞 Контакты", "payload": "menu_contacts"}]
    ]}}

def get_emergency_first_kb():
    return {"type": "inline_keyboard", "payload": {"buttons": [
        [{"type": "callback", "text": "📞 Позвонить 112", "payload": "call_112"}],
        [{"type": "callback", "text": "📝 Оставить заявку через бота", "payload": "report_via_bot"}],
        [{"type": "callback", "text": "❌ Отмена", "payload": "cancel"}]
    ]}}

def get_types_kb():
    return {"type": "inline_keyboard", "payload": {"buttons": [
        [{"type": "callback", "text": "🔥 Пожар", "payload": "em_fire"}],
        [{"type": "callback", "text": "🌊 Наводнение", "payload": "em_flood"}],
        [{"type": "callback", "text": "🏚️ ДТП/Обрушение", "payload": "em_accident"}],
        [{"type": "callback", "text": "⚠️ Другое", "payload": "em_other"}],
        [{"type": "callback", "text": "❌ Отмена", "payload": "cancel"}]
    ]}}

def get_confirm_kb():
    return {"type": "inline_keyboard", "payload": {"buttons": [
        [{"type": "callback", "text": "✅ Отправить", "payload": "confirm"},
         {"type": "callback", "text": "❌ Отмена", "payload": "cancel"}]
    ]}}

# ========== ОБРАБОТЧИКИ ==========
async def handle_event(event):
    update_type = event.get("update_type")
    logger.info(f"📨 Событие: {update_type}")

    if update_type == "message_created":
        await handle_message(event)
    elif update_type == "message_callback":
        await handle_callback(event)
    elif update_type == "bot_started":
        await handle_bot_started(event)

async def handle_bot_started(event):
    chat_id = str(event.get("chat_id", ""))
    user = event.get("user", {})
    payload = event.get("payload", "")
    logger.info(f"🚀 Диплинк: payload={payload}")
    await send_message(chat_id,
        "⚠️ *БОТ В ТЕСТОВОМ РЕЖИМЕ*\n\n"
        "Здравствуйте! Это тестовая версия бота Агентства ГОЧС Сахалинской области.\n\n"
        "🔸 Заявки через бота НЕ передаются диспетчерам.\n"
        "🔸 При реальной угрозе звоните *112*.",
        reply_markup=get_main_kb())

async def handle_message(event):
    msg = event.get("message", {})
    chat_id = str(msg.get("recipient", {}).get("chat_id") or msg.get("sender", {}).get("user_id"))
    user = msg.get("sender", {})
    text = msg.get("body", {}).get("text", "").strip()
    logger.info(f"💬 От {user.get('first_name')}: {text}")

    if text in ("/start", "/help"):
        await send_message(chat_id,
            "⚠️ *БОТ В ТЕСТОВОМ РЕЖИМЕ*\n\n"
            "Здравствуйте! Это тестовая версия бота Агентства ГОЧС Сахалинской области.\n\n"
            "🔸 Заявки через бота НЕ передаются диспетчерам.\n"
            "🔸 При реальной угрозе звоните *112*.",
            reply_markup=get_main_kb())
        return

    state = user_states.get(chat_id, {})
    step = state.get("step")

    if step == "waiting_location":
        user_states[chat_id]["location"] = text
        user_states[chat_id]["step"] = "waiting_details"
        await send_message(chat_id, "📍 Адрес принят. Опишите ситуацию (что произошло, есть ли пострадавшие):")
        return

    if step == "waiting_details":
        user_states[chat_id]["details"] = text
        user_states[chat_id]["step"] = "confirm"
        preview = (f"⚠️ *ТЕСТ*\n\n📋 *Проверьте данные:*\n"
                   f"Тип: {user_states[chat_id]['type']}\n"
                   f"Место: {user_states[chat_id]['location']}\n"
                   f"Описание: {user_states[chat_id]['details']}\n\nОтправить?")
        await send_message(chat_id, preview, reply_markup=get_confirm_kb())
        return

    await send_message(chat_id, "Используйте меню ниже 👇", reply_markup=get_main_kb())

async def handle_callback(event):
    cb = event.get("callback", {})
    user = cb.get("user", {})
    msg = cb.get("message", {})
    payload = cb.get("payload", "")
    chat_id = str(msg.get("recipient", {}).get("chat_id") or user.get("user_id"))
    logger.info(f"🔘 Кнопка: {payload}")

    if payload == "menu_report":
        await send_message(chat_id,
            "⚠️ *ТЕСТОВЫЙ РЕЖИМ*\n\n"
            "🚨 Если есть угроза жизни — звоните *112*!\n"
            "ЕДДС Сахалинской области: +7 (4242) 42-42-42",
            reply_markup=get_emergency_first_kb())
    elif payload == "call_112":
        await send_message(chat_id, "📞 *Наберите 112*\nЭто единый номер экстренных служб.",
                         reply_markup=get_main_kb())
    elif payload == "report_via_bot":
        user_states[chat_id] = {
            "step": "choose_type",
            "user_id": str(user.get("user_id")),
            "username": f"{user.get('first_name', '')} {user.get('last_name', '')}".strip()
        }
        await send_message(chat_id, "📝 Выберите тип происшествия:", reply_markup=get_types_kb())
    elif payload == "cancel":
        user_states.pop(chat_id, None)
        await send_message(chat_id, "Действие отменено.", reply_markup=get_main_kb())
    elif payload in EMERGENCY_TYPES:
        user_states[chat_id]["step"] = "waiting_location"
        user_states[chat_id]["type"] = EMERGENCY_TYPES[payload]
        await send_message(chat_id, f"Тип: *{EMERGENCY_TYPES[payload]}*\n\nВведите адрес текстом:")
    elif payload == "confirm":
        await send_message(chat_id, "⏳ Сохраняем...")
        ok = save_incident(user_states.get(chat_id, {}))
        user_states.pop(chat_id, None)
        if ok:
            await send_message(chat_id,
                "✅ *Тестовая заявка сохранена!*\n🔸 Диспетчер не получит её.\n🔸 При реальной ЧС звоните *112*.",
                reply_markup=get_main_kb())
        else:
            await send_message(chat_id, "❌ Ошибка. Позвоните *112*.", reply_markup=get_main_kb())
    elif payload == "menu_alerts":
        await send_message(chat_id,
            "⚠️ *ВНИМАНИЕ!*\nПо данным Сахалинского УГМС, сегодня ожидается усиление ветра до 20 м/с.\n"
            "Просьба не выходить на лёд и не парковать авто под деревьями.",
            reply_markup=get_main_kb())
    elif payload == "menu_contacts":
        await send_message(chat_id,
            "📞 *Экстренные службы:*\n112 - Единый\n101 - Пожарные\n102 - Полиция\n103 - Скорая\n"
            "🏢 *Агентство ГОЧС Сахалинской области*\n☎️ +7 (4242) 42-33-12\n📍 г. Южно-Сахалинск, ул. Ленина, 231",
            reply_markup=get_main_kb())

# ========== WEBHOOK СЕРВЕР ==========
async def webhook_handler(request):
    if WEBHOOK_SECRET:
        secret = request.headers.get("X-Max-Bot-Api-Secret", "")
        if secret != WEBHOOK_SECRET:
            logger.warning("⚠️ Неверный secret")
            return web.Response(status=403)
    try:
        data = await request.json()
        asyncio.create_task(handle_event(data))
        return web.Response(text="ok")
    except Exception as e:
        logger.error(f"Ошибка webhook: {e}")
        return web.Response(status=500)

async def health_handler(request):
    return web.Response(text="ok")

async def on_startup(app):
    logger.info("=" * 50)
    logger.info("🚀 Запуск бота @agochs65_bot (Webhook)")
    logger.info("=" * 50)
    s = await get_session()
    try:
        async with s.get(f"{BASE_URL}/me") as resp:
            me = await resp.json()
            logger.info(f"✅ Бот: {me.get('first_name')} (@{me.get('username')})")
    except Exception as e:
        logger.error(f"❌ Ошибка токена: {e}")
        return
    await register_webhook()
    logger.info("👂 Ожидаю сообщений от MAX...")

app = web.Application()
app.router.add_post("/webhook", webhook_handler)
app.router.add_get("/", health_handler)
app.on_startup.append(on_startup)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    logger.info(f"🌐 Сервер на порту {port}")
    web.run_app(app, host="0.0.0.0", port=port)
