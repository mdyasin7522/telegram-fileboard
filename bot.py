import os
import telebot
import uuid
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_NAME = "fileboard.db"

bot = telebot.TeleBot(BOT_TOKEN)

# ─── Translations ───
TEXT = {
    "bn": {
        "choose_lang": "🌐 আপনার ভাষা সিলেক্ট করুন:",
        "lang_set": "✅ ভাষা বাংলা সেট করা হয়েছে!",
        "welcome_admin": "👋 স্বাগতম!\n\n📁 যেকোনো ফাইল, ছবি, ভিডিও পাঠান — আমি link বানিয়ে দেব।\n\n📋 /list — সব ফাইল দেখুন\n❌ /delete <id> — ফাইল মুছুন\n🌐 /language — ভাষা পরিবর্তন করুন",
        "welcome_user": "📁 এই bot থেকে ফাইল ডাউনলোড করুন।\n🌐 /language — ভাষা পরিবর্তন করুন",
        "ask_limit": "📌 এই ফাইলে কী ধরনের limit দিতে চান?",
        "btn_download_limit": "⬇️ Download limit দিন",
        "btn_time_limit": "⏰ Time limit দিন",
        "btn_both": "উভয়ই দিন",
        "btn_none": "✅ কোনো limit নেই",
        "ask_download_count": "🔢 কতবার ডাউনলোড করা যাবে? (সংখ্যা লিখুন)",
        "ask_hours": "⏰ কত ঘণ্টা পর expire হবে? (সংখ্যা লিখুন)",
        "invalid_number": "❌ সঠিক সংখ্যা লিখুন।",
        "upload_done": "✅ ফাইল upload হয়েছে!",
        "limit_max": "⬇️ সর্বোচ্চ: {n} বার\n",
        "limit_expire": "⏰ Expire: {d}\n",
        "limit_none_text": "♾️ কোনো limit নেই\n",
        "download_link": "🔗 Download link:\n{link}",
        "file_not_found": "❌ ফাইলটি পাওয়া যায়নি বা মুছে ফেলা হয়েছে।",
        "file_expired": "⏰ এই ফাইলের সময় শেষ হয়ে গেছে।",
        "limit_reached": "❌ এই ফাইলের download limit শেষ হয়ে গেছে।",
        "sending": "📥 ফাইল পাঠানো হচ্ছে...\n🔢 বাকি সুযোগ: {n}",
        "no_files": "📭 কোনো ফাইল নেই।",
        "file_list_title": "📋 সব ফাইল:\n\n",
        "delete_usage": "Usage: /delete <file_id>",
        "deleted": "✅ {id} মুছে ফেলা হয়েছে।",
        "unlimited": "♾️",
        "none": "নেই",
    },
    "en": {
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language set to English!",
        "welcome_admin": "👋 Welcome!\n\n📁 Send any file, photo, or video — I'll create a link.\n\n📋 /list — View all files\n❌ /delete <id> — Delete a file\n🌐 /language — Change language",
        "welcome_user": "📁 Download files from this bot.\n🌐 /language — Change language",
        "ask_limit": "📌 What kind of limit do you want for this file?",
        "btn_download_limit": "⬇️ Download Limit",
        "btn_time_limit": "⏰ Time Limit",
        "btn_both": "Both",
        "btn_none": "✅ No Limit",
        "ask_download_count": "🔢 How many times can it be downloaded? (enter a number)",
        "ask_hours": "⏰ How many hours until it expires? (enter a number)",
        "invalid_number": "❌ Please enter a valid number.",
        "upload_done": "✅ File uploaded!",
        "limit_max": "⬇️ Max: {n} times\n",
        "limit_expire": "⏰ Expires: {d}\n",
        "limit_none_text": "♾️ No limit\n",
        "download_link": "🔗 Download link:\n{link}",
        "file_not_found": "❌ File not found or has been deleted.",
        "file_expired": "⏰ This file has expired.",
        "limit_reached": "❌ Download limit reached for this file.",
        "sending": "📥 Sending file...\n🔢 Remaining: {n}",
        "no_files": "📭 No files found.",
        "file_list_title": "📋 All Files:\n\n",
        "delete_usage": "Usage: /delete <file_id>",
        "deleted": "✅ {id} deleted.",
        "unlimited": "♾️",
        "none": "None",
    }
}

def t(user_id, key, **kwargs):
    lang = get_user_lang(user_id)
    text = TEXT.get(lang, TEXT["en"]).get(key, key)
    return text.format(**kwargs) if kwargs else text

# ─── DB functions ───
def init_db():
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
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'en'
        )
    """)
    conn.commit()
    conn.close()

def get_user_lang(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT language FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None

def set_user_lang(user_id, lang):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO users (user_id, language) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET language = ?", (user_id, lang, lang))
    conn.commit()
    conn.close()

def save_file(file_id, file_name, file_type, max_downloads=-1, expires_at=None):
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
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE files SET download_count = download_count + 1 WHERE id = ?", (uid,))
    conn.commit()
    conn.close()

def delete_file(uid):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM files WHERE id = ?", (uid,))
    conn.commit()
    conn.close()

def list_files():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT id, file_name, max_downloads, download_count, expires_at FROM files ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

# Temp storage
pending_files = {}
pending_action = {}
pending_start_uid = {}  # store uid to download after language selection

def is_admin(user_id):
    return True  # everyone can upload

# ─── Language selection keyboard ───
def language_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🇧🇩 বাংলা", callback_data="setlang_bn"))
    kb.add(InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"))
    return kb

# ─── /start ───
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    args = message.text.split()
    uid = args[1] if len(args) > 1 else None

    lang = get_user_lang(user_id)
    if not lang:
        if uid:
            pending_start_uid[user_id] = uid
        bot.send_message(message.chat.id, TEXT["bn"]["choose_lang"] + "\n" + TEXT["en"]["choose_lang"], reply_markup=language_keyboard())
        return

    if uid:
        send_file(message, uid)
        return

    if is_admin(user_id):
        bot.reply_to(message, t(user_id, "welcome_admin"))
    else:
        bot.reply_to(message, t(user_id, "welcome_user"))

# ─── /language ───
@bot.message_handler(commands=['language'])
def language_cmd(message):
    bot.send_message(message.chat.id, TEXT["bn"]["choose_lang"] + "\n" + TEXT["en"]["choose_lang"], reply_markup=language_keyboard())

# ─── Language callback ───
@bot.callback_query_handler(func=lambda call: call.data.startswith("setlang_"))
def set_language(call):
    user_id = call.from_user.id
    lang = call.data.split("_")[1]
    set_user_lang(user_id, lang)
    bot.edit_message_text(TEXT[lang]["lang_set"], call.message.chat.id, call.message.message_id)

    # If user came from a download link, continue to download
    if user_id in pending_start_uid:
        uid = pending_start_uid.pop(user_id)
        send_file(call.message, uid, user_id_override=user_id)
        return

    if is_admin(user_id):
        bot.send_message(call.message.chat.id, t(user_id, "welcome_admin"))
    else:
        bot.send_message(call.message.chat.id, t(user_id, "welcome_user"))

# ─── /list ───
@bot.message_handler(commands=['list'])
def list_cmd(message):
    user_id = message.from_user.id
    files = list_files()
    if not files:
        bot.reply_to(message, t(user_id, "no_files"))
        return
    text = t(user_id, "file_list_title")
    for f in files:
        mx = f[2] if f[2] != -1 else t(user_id, "unlimited")
        exp = f[4] if f[4] else t(user_id, "none")
        text += f"🔑 {f[0]} — {f[1]}\n⬇️ {f[3]}/{mx} | ⏰ {exp}\n\n"
    bot.reply_to(message, text)

# ─── /delete ───
@bot.message_handler(commands=['delete'])
def delete_cmd(message):
    user_id = message.from_user.id
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, t(user_id, "delete_usage"))
        return
    delete_file(parts[1])
    bot.reply_to(message, t(user_id, "deleted", id=parts[1]))

# ─── File receive ───
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def receive_file(message):
    user_id = message.from_user.id
    if not is_admin(user_id):
        return

    if message.document:
        pending_files[user_id] = {
            "file_id": message.document.file_id,
            "file_name": message.document.file_name,
            "file_type": "document"
        }
    elif message.photo:
        pending_files[user_id] = {
            "file_id": message.photo[-1].file_id,
            "file_name": "photo.jpg",
            "file_type": "photo"
        }
    elif message.video:
        pending_files[user_id] = {
            "file_id": message.video.file_id,
            "file_name": "video.mp4",
            "file_type": "video"
        }
    elif message.audio:
        pending_files[user_id] = {
            "file_id": message.audio.file_id,
            "file_name": message.audio.file_name or "audio.mp3",
            "file_type": "audio"
        }

    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_download_limit"), callback_data="limit_download"))
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_time_limit"), callback_data="limit_time"))
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_both"), callback_data="limit_both"))
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_none"), callback_data="limit_none"))
    bot.reply_to(message, t(user_id, "ask_limit"), reply_markup=keyboard)

# ─── Limit type callback ───
@bot.callback_query_handler(func=lambda call: call.data.startswith("limit_"))
def handle_limit_type(call):
    user_id = call.from_user.id
    choice = call.data
    pending_action[user_id] = {"choice": choice, "max_downloads": -1}

    if choice == "limit_none":
        finalize(call.message, user_id, -1, None)
    elif choice in ("limit_download", "limit_both"):
        bot.edit_message_text(t(user_id, "ask_download_count"), call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(call.message, got_download_count, user_id)
    elif choice == "limit_time":
        bot.edit_message_text(t(user_id, "ask_hours"), call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(call.message, got_hours, user_id)

def got_download_count(message, user_id):
    try:
        count = int(message.text.strip())
        pending_action[user_id]["max_downloads"] = count
    except:
        bot.reply_to(message, t(user_id, "invalid_number"))
        return

    if pending_action[user_id]["choice"] == "limit_both":
        msg = bot.reply_to(message, t(user_id, "ask_hours"))
        bot.register_next_step_handler(msg, got_hours, user_id)
    else:
        finalize(message, user_id, count, None)

def got_hours(message, user_id):
    try:
        hours = float(message.text.strip())
        expires_at = (datetime.now() + timedelta(hours=hours)).isoformat()
    except:
        bot.reply_to(message, t(user_id, "invalid_number"))
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
        limit_text += t(user_id, "limit_max", n=max_downloads)
    if expires_at:
        limit_text += t(user_id, "limit_expire", d=datetime.fromisoformat(expires_at).strftime('%d/%m/%Y %H:%M'))
    if not limit_text:
        limit_text = t(user_id, "limit_none_text")

    text = f"{t(user_id, 'upload_done')}\n\n📁 {pf['file_name']}\n🔑 {uid}\n\n{limit_text}\n{t(user_id, 'download_link', link=link)}"
    bot.reply_to(message, text)

def send_file(message, uid, user_id_override=None):
    user_id = user_id_override or message.from_user.id
    file_data = get_file(uid)
    if not file_data:
        bot.send_message(message.chat.id, t(user_id, "file_not_found"))
        return
    if file_data["expires_at"] and datetime.now() > datetime.fromisoformat(file_data["expires_at"]):
        delete_file(uid)
        bot.send_message(message.chat.id, t(user_id, "file_expired"))
        return
    if file_data["max_downloads"] != -1 and file_data["download_count"] >= file_data["max_downloads"]:
        bot.send_message(message.chat.id, t(user_id, "limit_reached"))
        return
    increment_download(uid)
    remaining = t(user_id, "unlimited") if file_data["max_downloads"] == -1 else file_data["max_downloads"] - file_data["download_count"] - 1
    bot.send_message(message.chat.id, t(user_id, "sending", n=remaining))
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
    print("✅ Bot চালু! Multi-language সহ।")
    bot.infinity_polling()
