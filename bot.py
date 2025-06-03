import os
import subprocess
import asyncio
from datetime import datetime, timedelta

from pyrogram import Client, filters
from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
from pyrogram.errors import Forbidden, PeerIdInvalid

from pymongo import MongoClient

import config


# MongoDB setup
mongo_client = MongoClient(config.MONGO_URI)
db = mongo_client["ExecutionBot"]
auth_collection = db["authorized_users"]

app = Client("bot", api_id=config.API_ID, api_hash=config.API_HASH, bot_token=config.BOT_TOKEN)

# -_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

def is_authorized(user_id):
    if user_id in config.BOT_ADMINS:
        return True
    user = auth_collection.find_one({"user_id": user_id})
    if not user:
        return False
    return datetime.utcnow() <= user["expires_at"]

# -_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

@app.on_message(filters.command("auth") & filters.user(config.BOT_ADMINS))
async def auth_user(client, message):
    try:
        await client.delete_messages(message.chat.id, message.id)

        parts = message.text.split()
        if len(parts) < 4:
            m = await client.send_message(
                message.chat.id,
                "Usage: /auth ←id→ ←amount→ ←days→ [note]"
            )
            await asyncio.sleep(10)
            await client.delete_messages(message.chat.id, m.id)
            return

        telegram_id = int(parts[1])
        amount = float(parts[2])
        days = int(parts[3])
        note = " ".join(parts[4:]) if len(parts) > 4 else ""

        expires_at = datetime.utcnow() + timedelta(days=days)
        expires_str = expires_at.strftime("%Y-%m-%d %H:%M:%S UTC")

        existing_user = auth_collection.find_one({"user_id": telegram_id})

        same_data = (
            existing_user and
            existing_user.get("amount") == amount and
            existing_user.get("note", "") == note and
            existing_user.get("expires_at") and
            abs((existing_user["expires_at"] - expires_at).total_seconds()) < 60
        )

        if same_data:
            m = await client.send_message(
                message.chat.id,
                f"No changes made. User ID: {telegram_id}"
            )
            await asyncio.sleep(10)
            await client.delete_messages(message.chat.id, m.id)
            return

        # Update or insert
        auth_collection.update_one(
            {"user_id": telegram_id},
            {"$set": {
                "user_id": telegram_id,
                "amount": amount,
                "expires_at": expires_at,
                "note": note
            }},
            upsert=True
        )

        try:
            await client.send_message(
                telegram_id,
                f"You have been {'updated' if existing_user else 'authorized'}!\n"
                f"Amount: {amount}\n"
                f"Valid until: {expires_str}"
            )
            notify_status = "User notified."
        except (Forbidden, PeerIdInvalid):
            notify_status = "User could not be notified (maybe blocked the bot)."

        if existing_user:
            await client.send_message(
                message.chat.id,
                f"Updated user {telegram_id}.\n"
                f"Amount: {existing_user.get('amount')} → {amount}\n"
                f"Expires: {existing_user.get('expires_at')} → {expires_str}\n"
                f"Note: \"{existing_user.get('note', '')}\" → \"{note}\"\n"
                f"{notify_status}"
            )
        else:
            await client.send_message(
                message.chat.id,
                f"Authorized new user {telegram_id} for {days} days.\n"
                f"Amount: {amount}\n"
                f"Expires: {expires_str}\n"
                f"Note: \"{note or 'N/A'}\"\n"
                f"{notify_status}"
            )

    except Exception as e:
        m = await client.send_message(message.chat.id, f"Error: {e}")
        await asyncio.sleep(10)
        await client.delete_messages(message.chat.id, m.id)

# -_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

@app.on_message(filters.command("deauth") & filters.user(config.BOT_ADMINS))
async def deauth_user(client, message):
    try:
        await client.delete_messages(message.chat.id, message.id)

        parts = message.text.split()
        if len(parts) != 2:
            m = await client.send_message(
                message.chat.id,
                "Usage: /deauth ←id→"
            )
            await asyncio.sleep(10)
            await client.delete_messages(message.chat.id, m.id)
            return

        telegram_id = int(parts[1])
        result = auth_collection.delete_one({"user_id": telegram_id})

        if result.deleted_count == 0:
            m = await client.send_message(
                message.chat.id,
                f"No authorization found for user ID {telegram_id}."
            )
            await asyncio.sleep(10)
            await client.delete_messages(message.chat.id, m.id)
            return

        await client.send_message(
            message.chat.id,
            f"User ID {telegram_id} has been removed from the authorized list."
        )

    except Exception as e:
        m = await client.send_message(message.chat.id, f"Error: {e}")
        await asyncio.sleep(10)
        await client.delete_messages(message.chat.id, m.id)

# -_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

@app.on_message(filters.command("info"))
async def info_user(client, message):
    try:
        # Instantly delete the command
        await client.delete_messages(message.chat.id, message.id)

        parts = message.text.split()
        from_admin = message.from_user.id in config.BOT_ADMINS

        # Check whose info to fetch
        if len(parts) == 2:
            if not from_admin:
                m = await client.send_message(
                    message.chat.id,
                    "Only admins can check other users' info."
                )
                await asyncio.sleep(10)
                await client.delete_messages(message.chat.id, m.id)
                return
            telegram_id = int(parts[1])
        else:
            telegram_id = message.from_user.id

        status = []
        if telegram_id in config.BOT_ADMINS:
            status.append("Admin ❇️")

        user_data = auth_collection.find_one({"user_id": telegram_id})
        if user_data:
            expires_at = user_data.get("expires_at")
            now = datetime.utcnow()
            expired = expires_at < now if expires_at else True
            remaining_days = (expires_at - now).days if expires_at else 0
            status.append("Authorized ❇️" if not expired else "Expired ❌")

            msg = (
                f"ID: `{telegram_id}`\n"
                f"Status: {', '.join(status)}\n"
                f"Validity: {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC') if expires_at else 'N/A'}\n"
                f"Amount: {user_data.get('amount')}"
            )
        else:
            if not status:
                status.append("Not authorized ❌")
            msg = f"ID: {telegram_id}\nStatus: {', '.join(status)}"

        await client.send_message(message.chat.id, msg)

    except Exception as e:
        m = await client.send_message(message.chat.id, f"Error: {e}")
        await asyncio.sleep(10)
        await client.delete_messages(message.chat.id, m.id)

# -_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

@app.on_message(filters.command("list") & filters.user(config.BOT_ADMINS))
async def list_users(client, message):
    try:
        # Instantly delete the /list command message
        await client.delete_messages(message.chat.id, message.id)

        file_path = "list.txt"

        users = auth_collection.find().sort("expires_at", 1)

        with open(file_path, "w") as f:
            for user in users:
                f.write(f"Telegram ID: {user.get('user_id')}\n")
                f.write(f"Amount: {user.get('amount')}\n")
                expires_at = user.get("expires_at")
                f.write(f"Expires At: {expires_at.strftime('%Y-%m-%d %H:%M:%S UTC') if expires_at else 'N/A'}\n")
                f.write(f"Note: {user.get('note', 'N/A')}\n")
                f.write("\n\n\n\n")

        await client.send_document(
            chat_id=message.chat.id,
            document=file_path,
            caption="📄 List of all authorized users."
        )

        os.remove(file_path)

    except Exception as e:
        m = await client.send_message(message.chat.id, f"❌ Error: {e}")
        await asyncio.sleep(10)
        await client.delete_messages(message.chat.id, m.id)

# -_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_

# ❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌


# from pyrogram import Client, filters
# from pyrogram.types import ReplyKeyboardMarkup, ReplyKeyboardRemove
# from datetime import datetime, timedelta
# import asyncio
# import subprocess

# DEFAULT_TIME = "60"
# # DEFAULT_THREADS = "100"
# # BINARY_PATH = "./runner"  # replace with your binary

# @app.on_message(filters.command("execute2"))
# async def start_execution_flow(client, message):
#     user_id = message.from_user.id
#     await client.delete_messages(message.chat.id, message.id)

#     # Clean up old stored data if any
#     users_collection.delete_one({"user_id": user_id})

#     prompt = await client.send_message(
#         message.chat.id,
#         "🛠️ Send now: `<ip> <port> [time] [threads]`\n\nYou have 60 seconds...",
#     )

#     await asyncio.sleep(60)

#     # If still no input after 60s, notify and remove keyboard
#     if users_collection.find_one({"user_id": user_id}) is None:
#         await prompt.edit_text("⏳ Timeout. Please run /execute2 again.")
#         return


# @app.on_message(filters.text & filters.private)
# async def handle_execution_input(client, message):
#     user_id = message.from_user.id
#     text = message.text.strip()

#     # Handle STOP
#     if text.upper() == "STOP":
#         process = active_attacks.get(user_id)
#         if process:
#             try:
#                 process.terminate()
#                 del active_attacks[user_id]
#                 await client.send_message(
#                     message.chat.id,
#                     "⛔ Execution manually stopped.",
#                     reply_markup=ReplyKeyboardMarkup([["START"]], resize_keyboard=True)
#                 )
#             except Exception as e:
#                 await client.send_message(
#                     message.chat.id,
#                     f"⚠️ Error stopping process: {e}",
#                     reply_markup=ReplyKeyboardMarkup([["START"]], resize_keyboard=True)
#                 )
#         else:
#             await client.send_message(
#                 message.chat.id,
#                 "⚠️ No active process found.",
#                 reply_markup=ReplyKeyboardMarkup([["START"]], resize_keyboard=True)
#             )
#         return

#     # Handle START
#     if text.upper() == "START":
#         data = users_collection.find_one({"user_id": user_id})
#         if not data:
#             await client.send_message(
#                 message.chat.id,
#                 "⚠️ No saved execution info found. Please run /execute2 again.",
#                 reply_markup=ReplyKeyboardRemove()
#             )
#             return

#         if datetime.utcnow() - data["stored_at"] > timedelta(minutes=50):
#             users_collection.delete_one({"user_id": user_id})
#             await client.send_message(
#                 message.chat.id,
#                 "⌛ Saved input expired. Please run /execute2 again.",
#                 reply_markup=ReplyKeyboardRemove()
#             )
#             return

#         ip = data["ip"]
#         port = data["port"]
#         time_ = data.get("time", DEFAULT_TIME)
#         threads = data.get("threads", DEFAULT_THREADS)

#         await client.send_message(
#             message.chat.id,
#             f"🚀 Execution Started\n"
#             f"📍 IP: {ip}\n"
#             f"🔌 Port: {port}\n"
#             f"⏱️ Duration: {time_}s\n"
#             f"🧵 Threads: {threads}",
#             reply_markup=ReplyKeyboardMarkup([["STOP"]], resize_keyboard=True)
#         )

#         try:
#             process = subprocess.Popen([str(BINARY_PATH), str(ip), str(port), str(time_), str(threads)])
#             active_attacks[user_id] = process
#             process.wait()  # Optional: wait for it to finish

#             # After execution
#             await client.send_message(
#                 message.chat.id,
#                 f"❇️ Execution Finished\n"
#                 f"📍 IP: {ip}\n"
#                 f"🔌 Port: {port}\n"
#                 f"⏱️ Duration: {time_}s\n"
#                 f"🧵 Threads: {threads}",
#                 reply_markup=ReplyKeyboardMarkup([["START"]], resize_keyboard=True)
#             )

#             active_attacks.pop(user_id, None)

#         except Exception as e:
#             await client.send_message(
#                 message.chat.id,
#                 f"❌ Execution failed: {e}",
#                 reply_markup=ReplyKeyboardMarkup([["START"]], resize_keyboard=True)
#             )
#         return

#     # Handle input format: <ip> <port> [time] [threads]
#     parts = text.split()
#     if len(parts) < 2:
#         return  # Not valid input

#     ip = parts[0]
#     port = parts[1]
#     time_ = parts[2] if len(parts) >= 3 else DEFAULT_TIME
#     threads = parts[3] if len(parts) >= 4 else DEFAULT_THREADS

#     # Store in DB
#     users_collection.update_one(
#         {"user_id": user_id},
#         {"$set": {
#             "ip": ip,
#             "port": port,
#             "time": time_,
#             "threads": threads,
#             "stored_at": datetime.utcnow()
#         }},
#         upsert=True
#     )

#     await client.send_message(
#         message.chat.id,
#         f"💾 IP & Port saved!\n"
#         f"📍 IP: {ip}\n"
#         f"🔌 Port: {port}\n"
#         f"⏱️ Time: {time_}s (default)\n"
#         f"🧵 Threads: {threads} (default)\n\n"
#         f"❇️ Press START to execute.",
#         reply_markup=ReplyKeyboardMarkup([["START"]], resize_keyboard=True)
#     )


# ❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌❌

# -_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_-_


@app.on_message(filters.command("execute"))
async def execute_command(client, message):
    try:
        # Instantly delete the command message
        await client.delete_messages(message.chat.id, message.id)

        user_id = message.from_user.id
        if not is_authorized(user_id):
            m = await client.send_message(
                message.chat.id,
                "You are not authorized to use this command."
            )
            await asyncio.sleep(10)
            await client.delete_messages(message.chat.id, m.id)
            return

        parts = message.text.split()
        if len(parts) < 4:
            m = await client.send_message(
                message.chat.id,
                "Usage: /execute ←ip→ ←port→ ←time→ [threads]"
            )
            await asyncio.sleep(10)
            await client.delete_messages(message.chat.id, m.id)
            return

        ip = parts[1]
        port = parts[2]
        time_ = parts[3]
        threads = parts[4] if len(parts) > 4 else str(config.DEFAULT_THREADS)

        # Shared message content
        info_msg = (
            f"IP: {ip}\n"
            f"Port: {port}\n"
            f"Duration: {time_}s\n"
            f"Threads: {threads}"
        )

        # Send start message
        await client.send_message(
            message.chat.id,
            f"🚀 Execution Started\n\n{info_msg}"
        )

        # Run and wait for process to finish
        cmd = [config.BINARY_PATH, ip, port, time_, threads]
        subprocess.run(cmd)

        # Send finish message
        await client.send_message(
            message.chat.id,
            f"❇️ Execution Finished\n\n{info_msg}"
        )

    except Exception as e:
        m = await client.send_message(message.chat.id, f"❌ Execution failed: {e}")
        await asyncio.sleep(10)
        await client.delete_messages(message.chat.id, m.id)







app.run()
