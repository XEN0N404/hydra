from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import json
import time
import asyncio
import aiohttp

BOT_TOKEN = "8925750287:AAHdk9k_vwTkLbNjhX_c21suZX1Bu9B2LiY"
TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"
ADMIN_ID = 8515396790
GROUP_LINK = "https://t.me/+AJicgAn15Fs0ZTRl"
REQUIRED_CHANNELS = [
    {"id": -1003658885718, "link": "https://t.me/+UhnfKRECh9RlZDY1", "name": "Channel 1"},
    {"id": -1003376910382, "link": "https://t.me/+ctKJSH1nhrEwZjVl", "name": "Channel 2"}
]

APIS = {
    "number": lambda val: f"https://hydraapi.zya.me/api/v1/number.php?number={val}",
    "aadhar": lambda val: f"https://hydraapi.zya.me/api/v1/aadhar.php?aadhaar={val}",
    "pan": lambda val: f"https://admin.gbssystems.com/api/pan.php?q={val}",
    "vi": lambda val: f"https://vi-w2sg1wf7u-xen0n404s-projects.vercel.app/api/lookup?number={val}",
    "family": lambda val: f"https://hydraapi.zya.me/api/v1/family.php?aadhaar={val}",
    "tg": lambda val: f"https://admin.gbssystems.com/api/tg.php?tg_id={val}",
    "pk_num": lambda val: f"https://admin.gbssystems.com/api/pknum.php?pk_num={val}",
    "pk_cnic": lambda val: f"https://admin.gbssystems.com/api/pkcnic.php?pk_cnic={val}"
}

DB = {
    "users": {},
    "total_searches": 0,
    "total_users": set(),
    "private_access": {},
    "vi_limits": {},
    "message_queue": []
}

SESSION = None

async def get_session():
    global SESSION
    if SESSION is None or SESSION.closed:
        SESSION = aiohttp.ClientSession()
    return SESSION

async def api_call(url):
    session = await get_session()
    try:
        async with session.get(url, timeout=30) as response:
            return await response.json()
    except Exception as e:
        return {"error": "API request failed", "details": str(e)}

async def call_telegram(method, data):
    session = await get_session()
    try:
        async with session.post(f"{TELEGRAM_API}/{method}", json=data, timeout=10) as response:
            return await response.json()
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }
    if reply_markup:
        data["reply_markup"] = reply_markup
    return await call_telegram("sendMessage", data)

async def delete_message(chat_id, message_id):
    try:
        await call_telegram("deleteMessage", {
            "chat_id": chat_id,
            "message_id": message_id
        })
    except Exception:
        pass

async def check_channel_membership(user_id):
    session = await get_session()
    for channel in REQUIRED_CHANNELS:
        try:
            async with session.get(f"{TELEGRAM_API}/getChatMember?chat_id={channel['id']}&user_id={user_id}", timeout=10) as response:
                data = await response.json()
                if not data.get("ok") or data.get("result", {}).get("status") in ["left", "kicked"]:
                    return False
        except Exception:
            return False
    return True

def is_admin(user_id):
    return user_id == ADMIN_ID

def has_private_access(user_id):
    if is_admin(user_id):
        return True
    expiry = DB["private_access"].get(user_id)
    if not expiry:
        return False
    if time.time() > expiry:
        del DB["private_access"][user_id]
        return False
    return True

def can_use_vi(user_id):
    if is_admin(user_id) or has_private_access(user_id):
        return True
    count = DB["vi_limits"].get(user_id, 0)
    return count < 1

def format_json(obj):
    json_str = json.dumps(obj, indent=2, ensure_ascii=False)
    return f"```json\n{json_str}\n```"

def build_channel_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": REQUIRED_CHANNELS[0]["name"], "url": REQUIRED_CHANNELS[0]["link"]},
                {"text": REQUIRED_CHANNELS[1]["name"], "url": REQUIRED_CHANNELS[1]["link"]}
            ],
            [{"text": "Verify", "url": GROUP_LINK}]
        ]
    }

def build_admin_keyboard():
    return {
        "inline_keyboard": [
            [
                {"text": "Total Searches", "callback_data": "admin_stats"},
                {"text": "Total Users", "callback_data": "admin_users"}
            ],
            [{"text": "Grant Access", "callback_data": "admin_grant_info"}]
        ]
    }

def build_join_keyboard():
    return {
        "inline_keyboard": [
            [{"text": "Join Group", "url": GROUP_LINK}]
        ]
    }

async def schedule_deletion(chat_id, message_id):
    await asyncio.sleep(60)
    await delete_message(chat_id, message_id)

async def handle_start(chat_id, user_id, chat_type):
    DB["total_users"].add(user_id)
    if user_id not in DB["users"]:
        DB["users"][user_id] = {"joined": time.time()}

    if chat_type == "private":
        text = (
            "Welcome to Varcle Bot\n\n"
            "This bot works only in groups.\n\n"
            "To use this bot:\n"
            "1. Join our group\n"
            "2. Join both required channels\n"
            "3. Click Verify to start\n\n"
            "Commands:\n"
            "/num - Number lookup\n"
            "/aadhar - Aadhaar lookup\n"
            "/pan - PAN lookup\n"
            "/vi - VI number lookup (1 free)\n"
            "/family - Family ID lookup\n"
            "/tg - Telegram ID lookup\n"
            "/pk - Pakistan number/CNIC lookup"
        )
        await send_message(chat_id, text, build_channel_keyboard())

async def handle_help(chat_id):
    text = (
        "Available Commands:\n\n"
        "Number Lookup:\n"
        "/num 6296362230\n"
        "/number 9093614290\n\n"
        "Identity Lookup:\n"
        "/aadhar 512798565716\n"
        "/pan CFXPV5799D\n"
        "/family 512798565716\n\n"
        "Telecom Lookup:\n"
        "/vi 7669610720\n\n"
        "Telegram Lookup:\n"
        "/tg 8470406695\n\n"
        "Pakistan Lookup:\n"
        "/pk 03213181823 (number)\n"
        "/pk 3550105681512 (CNIC)\n\n"
        "Note: VI command has 1 free search limit"
    )
    await send_message(chat_id, text)

async def handle_admin_panel(chat_id, user_id):
    if not is_admin(user_id):
        return
    await send_message(chat_id, "Admin Panel", build_admin_keyboard())

async def handle_grant(chat_id, user_id, text):
    if not is_admin(user_id):
        return

    parts = text.split(" ")
    if len(parts) < 3:
        await send_message(chat_id, "Format: /grant <user_id> <hours>")
        return

    try:
        target_id = int(parts[1])
        hours = int(parts[2])
    except ValueError:
        await send_message(chat_id, "Format: /grant <user_id> <hours>")
        return

    DB["private_access"][target_id] = time.time() + hours * 60 * 60
    DB["vi_limits"][target_id] = 0
    await send_message(chat_id, f"Granted private access to user {target_id} for {hours} hours")

async def handle_api_command(chat_id, user_id, command, value, message_id):
    asyncio.create_task(delete_message(chat_id, message_id))

    if not value:
        result = await send_message(chat_id, f"Missing value. Format: /{command} <value>")
        if result.get("ok"):
            msg_id = result.get("result", {}).get("message_id")
            if msg_id:
                asyncio.create_task(schedule_deletion(chat_id, msg_id))
        return

    if command == "vi" and not can_use_vi(user_id):
        result = await send_message(chat_id, "VI search limit reached. Contact admin for more access.")
        if result.get("ok"):
            msg_id = result.get("result", {}).get("message_id")
            if msg_id:
                asyncio.create_task(schedule_deletion(chat_id, msg_id))
        return

    processing_result = await send_message(chat_id, "Searching...")
    processing_msg_id = None
    if processing_result.get("ok"):
        processing_msg_id = processing_result.get("result", {}).get("message_id")

    api_url = None
    if command in ["num", "number"]:
        api_url = APIS["number"](value)
    elif command == "aadhar":
        api_url = APIS["aadhar"](value)
    elif command == "pan":
        api_url = APIS["pan"](value)
    elif command == "vi":
        api_url = APIS["vi"](value)
    elif command == "family":
        api_url = APIS["family"](value)
    elif command in ["tg", "tg_id"]:
        api_url = APIS["tg"](value)
    elif command == "pk":
        if len(value) <= 11:
            api_url = APIS["pk_num"](value)
        else:
            api_url = APIS["pk_cnic"](value)
    elif command == "pk_num":
        api_url = APIS["pk_num"](value)
    elif command == "pk_cnic":
        api_url = APIS["pk_cnic"](value)

    if not api_url:
        return

    result_data = await api_call(api_url)

    DB["total_searches"] += 1
    if command == "vi":
        DB["vi_limits"][user_id] = DB["vi_limits"].get(user_id, 0) + 1

    if processing_msg_id:
        asyncio.create_task(delete_message(chat_id, processing_msg_id))

    output = f"Result for {command}:\n\n{format_json(result_data)}"
    result = await send_message(chat_id, output)

    if result.get("ok"):
        msg_id = result.get("result", {}).get("message_id")
        if msg_id:
            asyncio.create_task(schedule_deletion(chat_id, msg_id))

async def handle_new_member(chat_id, user_id, first_name):
    text = f"Welcome {first_name}\n\nPlease join our required channels and verify to use the bot.\nUse /help to see available commands."
    result = await send_message(chat_id, text, build_channel_keyboard())

    try:
        await send_message(
            user_id,
            "Welcome to Varcle Community\n\nUse the button below to join our main group:",
            build_join_keyboard()
        )
    except Exception:
        pass

    if result.get("ok"):
        msg_id = result.get("result", {}).get("message_id")
        if msg_id:
            asyncio.create_task(schedule_deletion(chat_id, msg_id))

async def handle_join_request(user_id):
    try:
        session = await get_session()
        group_id = GROUP_LINK.split("/")[-1]
        async with session.post(f"{TELEGRAM_API}/approveChatJoinRequest", json={
            "chat_id": f"@{group_id}",
            "user_id": user_id
        }) as response:
            await response.json()
        
        await send_message(
            user_id,
            "Your request has been approved\n\nWelcome to the group. Use /help to see commands.",
            build_join_keyboard()
        )
    except Exception:
        pass

async def handle_callback_query(callback_query):
    callback_id = callback_query.get("id")
    data = callback_query.get("data")
    from_user = callback_query.get("from", {})
    user_id = from_user.get("id")

    session = await get_session()
    async with session.post(f"{TELEGRAM_API}/answerCallbackQuery", json={
        "callback_query_id": callback_id
    }) as response:
        await response.json()

    if not is_admin(user_id):
        return

    if data == "admin_stats":
        await send_message(user_id, f"Total API Searches: {DB['total_searches']}")
    elif data == "admin_users":
        await send_message(user_id, f"Total Unique Users: {len(DB['total_users'])}")
    elif data == "admin_grant_info":
        await send_message(user_id, "Grant Private Access\n\nFormat: /grant <user_id> <hours>\nExample: /grant 8515396654 23\n\nThis grants user 8515396654 access for 23 hours")

async def process_update(update):
    try:
        if "callback_query" in update:
            await handle_callback_query(update["callback_query"])
            return

        if "chat_join_request" in update:
            await handle_join_request(update["chat_join_request"]["from"]["id"])
            return

        message = update.get("message")
        if not message:
            return

        chat_id = message.get("chat", {}).get("id")
        user_id = message.get("from", {}).get("id")
        chat_type = message.get("chat", {}).get("type")
        text = message.get("text", "")
        message_id = message.get("message_id")

        if "new_chat_members" in message:
            for member in message["new_chat_members"]:
                if not member.get("is_bot"):
                    await handle_new_member(chat_id, member["id"], member.get("first_name", "User"))
            return

        if chat_type == "private":
            if text.startswith("/start"):
                await handle_start(chat_id, user_id, chat_type)
                return
            if text.startswith("/help"):
                await handle_help(chat_id)
                return

            if text.startswith("/") and not has_private_access(user_id):
                await send_message(
                    chat_id,
                    "This bot works only in groups.\n\nJoin our group to use all features.",
                    build_join_keyboard()
                )
                return

        if text.startswith("/start"):
            await handle_start(chat_id, user_id, chat_type)
            return
        if text.startswith("/help"):
            await handle_help(chat_id)
            return
        if text.startswith("/admin"):
            await handle_admin_panel(chat_id, user_id)
            return
        if text.startswith("/grant"):
            await handle_grant(chat_id, user_id, text)
            return

        parts = text.split(" ")
        command = parts[0].replace("/", "").lower() if len(parts) > 0 else ""
        value = parts[1] if len(parts) > 1 else None

        valid_commands = ["num", "number", "aadhar", "pan", "vi", "family", "tg", "tg_id", "pk", "pk_num", "pk_cnic"]

        if command in valid_commands:
            if chat_type in ["group", "supergroup"]:
                is_member = await check_channel_membership(user_id)
                if not is_member:
                    result = await send_message(
                        chat_id,
                        "Access Denied\n\nYou must join both channels to use this bot.",
                        build_channel_keyboard()
                    )
                    if result.get("ok"):
                        msg_id = result.get("result", {}).get("message_id")
                        if msg_id:
                            asyncio.create_task(schedule_deletion(chat_id, msg_id))
                    return

            await handle_api_command(chat_id, user_id, command, value, message_id)

    except Exception as e:
        print(f"Process error: {e}")

app = FastAPI()

@app.post("/api/bot")
async def webhook_handler(request: Request):
    try:
        update = await request.json()
        asyncio.create_task(process_update(update))
        return JSONResponse(content={"status": "ok"})
    except Exception:
        return JSONResponse(content={"status": "ok"})

@app.get("/api/bot")
async def health_check():
    return JSONResponse(content={"status": "running"})
