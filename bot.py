import os
import telebot
import asyncio
import aiosqlite
import uuid
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_NAME = "fileboard.db"

bot = telebot.TeleBot(BOT_TOKEN)

# DB functions
def init_db():
    import sqlite3
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id TEXT PRIMARY KEY,
            file_id TEXT NOT NULL,
            file_name TEXT,
            file_type TEXT,
            max_downloads INTEGER DEFAULT -1,
            download_count INTEGER DEFAULT 0,
            expires_at TEXT DEFAULT NULL,
            created_at TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def save_file(file_id, file_name, file_type, max_downloads=-1, expires_at=None):
    import sqlite3
    uid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        INSERT INTO files (id, file_id, file_name, file_type, max_downloads, download_count, expires_at, created_at)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?)
    """, (uid, file_id, file_name, file_type, max_downloads, expires_at, now))
    conn.commit()
    conn.close()
    return uid

def get_file(uid):
    import sqlite3
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT * FROM files WHERE id = ?", (uid,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "id": row[0], "file_id": row[1], "file_name": row[2],
            "file_type": row[3], "max_downloads": row[4],
            "download_count": row[5], "expires_at": row[6], "created_at": row[7]
        }
    return None

def increment_download(uid):
    import sqlite3
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE files SET download_count = download_count + 1 WHERE id = ?", (uid,))
    conn.commit()
    conn.close()

def delete_file(uid):
    import sqlite3
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM files WHERE id = ?", (uid,))
    conn.commit()
    conn.close()

def list_files():
    import sqlite3
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT id, file_name, max_downloads, download_count, expires_at FROM files ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

# Temp storage
pending_files = {}
pending_action = {}

def is_admin(user_id):
    return True

# /start
@bot.message_handler(commands=['start'])
def start(message):
    args = message.text.split()
    if len(args) > 1:
        uid = args[1]
        send_file(message, uid)
        return
    if is_admin(message.from_user.id):
        bot.reply_to(message,
            "👋 স্বাগতম Admin!\n\n📁 ফাইল পাঠান — link বানিয়ে দেব।\n\n📋 /list\n❌ /delete <id>"
        )
    else:
        bot.reply_to(message, "📁 এই bot থেকে ফাইল ডাউনলোড করুন।")

# /list
@bot.message_handler(commands=['list'])
def list_cmd(message):
    if not is_admin(message.from_user.id):
        return
    files = list_files()
    if not files:
        bot.reply_to(message, "📭 কোনো ফাইল নেই।")
        return
    text = "📋 ফাইল তালিকা:\n\n"
    for f in files:
        mx = f[2] if f[2] != -1 else "♾️"
        text += f"🔑 {f[0]} — {f[1]} | {f[3]}/{mx}\n"
    bot.reply_to(message, text)

# /delete
@bot.message_handler(commands=['delete'])
def delete_cmd(message):
    if not is_admin(message.from_user.id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, "Usage: /delete <id>")
        return
    delete_file(parts[1])
    bot.reply_to(message, "✅ মুছে ফেলা হয়েছে।")

# File receive
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def receive_file(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "❌ permission নেই।")
        return

    if message.document:
        pending_files[message.from_user.id] = {
            "file_id": message.document.file_id,
            "file_name": message.document.file_name,
            "file_type": "document"
        }
    elif message.photo:
        pending_files[message.from_user.id] = {
            "file_id": message.photo[-1].file_id,
            "file_name": "photo.jpg",
            "file_type": "photo"
        }
    elif message.video:
        pending_files[message.from_user.id] = {
            "file_id": message.video.file_id,
            "file_name": "video.mp4",
            "file_type": "video"
        }
    elif message.audio:
        pending_files[message.from_user.id] = {
            "file_id": message.audio.file_id,
            "file_name": message.audio.file_name or "audio.mp3",
            "file_type": "audio"
        }

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("⬇️ Download limit", callback_data="limit_download"))
    keyboard.add(InlineKeyboardButton("⏰ Time limit", callback_data="limit_time"))
    keyboard.add(InlineKeyboardButton("উভয়ই", callback_data="limit_both"))
    keyboard.add(InlineKeyboardButton("✅ কোনো limit নেই", callback_data="limit_none"))
    bot.reply_to(message, "📌 limit টাইপ?", reply_markup=keyboard)

# Callback handler
@bot.callback_query_handler(func=lambda call: call.data.startswith("limit_"))
def handle_limit_type(call):
    user_id = call.from_user.id
    choice = call.data
    pending_action[user_id] = {"choice": choice, "max_downloads": -1}

    if choice == "limit_none":
        finalize(call.message, user_id, -1, None)
    elif choice in ("limit_download", "limit_both"):
        bot.edit_message_text("🔢 কতবার ডাউনলোড করা যাবে? (সংখ্যা লিখুন)", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(call.message, got_download_count, user_id)
    elif choice == "limit_time":
        bot.edit_message_text("⏰ কত ঘণ্টা পর expire হবে? (সংখ্যা লিখুন)", call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(call.message, got_hours, user_id)

def got_download_count(message, user_id):
    try:
        count = int(message.text.strip())
        pending_action[user_id]["max_downloads"] = count
    except:
        bot.reply_to(message, "❌ সংখ্যা লিখুন।")
        return

    if pending_action[user_id]["choice"] == "limit_both":
        msg = bot.reply_to(message, "⏰ কত ঘণ্টা পর expire হবে?")
        bot.register_next_step_handler(msg, got_hours, user_id)
    else:
        finalize(message, user_id, count, None)

def got_hours(message, user_id):
    try:
        hours = float(message.text.strip())
        expires_at = (datetime.now() + timedelta(hours=hours)).isoformat()
    except:
        bot.reply_to(message, "❌ সংখ্যা লিখুন।")
        return
    max_downloads = pending_action.get(user_id, {}).get("max_downloads", -1)
    finalize(message, user_id, max_downloads, expires_at)

def finalize(message, user_id, max_downloads, expires_at):
    pf = pending_files.pop(user_id, None)
    if not pf:
        return
    uid = save_file(pf["file_id"], pf["file_name"], pf["file_type"], max_downloads, expires_at)
    me = bot.get_me()
    link = f"https://t.me/{me.username}?start={uid}"
    limit_text = ""
    if max_downloads > 0:
        limit_text += f"⬇️ {max_downloads} বার\n"
    if expires_at:
        limit_text += f"⏰ {datetime.fromisoformat(expires_at).strftime('%d/%m/%Y %H:%M')}\n"
    if not limit_text:
        limit_text = "♾️ কোনো limit নেই\n"
    text = f"✅ Done!\n\n📁 {pf['file_name']}\n🔑 {uid}\n\n{limit_text}\n🔗 {link}"
    bot.reply_to(message, text)

def send_file(message, uid):
    file_data = get_file(uid)
    if not file_data:
        bot.reply_to(message, "❌ ফাইল নেই।")
        return
    if file_data["expires_at"] and datetime.now() > datetime.fromisoformat(file_data["expires_at"]):
        delete_file(uid)
        bot.reply_to(message, "⏰ Expired।")
        return
    if file_data["max_downloads"] != -1 and file_data["download_count"] >= file_data["max_downloads"]:
        bot.reply_to(message, "❌ Limit শেষ।")
        return
    increment_download(uid)
    remaining = "♾️" if file_data["max_downloads"] == -1 else file_data["max_downloads"] - file_data["download_count"] - 1
    bot.reply_to(message, f"📥 পাঠানো হচ্ছে...\n🔢 বাকি: {remaining}")
    ftype = file_data["file_type"]
    fid = file_data["file_id"]
    if ftype == "document":
        bot.send_document(message.chat.id, fid)
    elif ftype == "photo":
        bot.send_photo(message.chat.id, fid)
    elif ftype == "video":
        bot.send_video(message.chat.id, fid)
    elif ftype == "audio":
        bot.send_audio(message.chat.id, fid)

if __name__ == "__main__":
    init_db()
    print("✅ Bot চালু!")
    bot.infinity_polling()
