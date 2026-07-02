import os
import io
import telebot
import uuid
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from PIL import Image

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
DB_NAME = "fileboard.db"

MAX_DOWNLOADS = 500
MAX_MINUTES = 2880   # 48 hours
MAX_TIME_VALUE_MIN = 700
MAX_TIME_VALUE_HOUR = 48

# Bangladesh standard passport photo: 35mm x 45mm @ 300 dpi
PASSPORT_SIZE = (413, 531)

# /resize constraints
RESIZE_MIN_KB = 30
RESIZE_MAX_KB = 2560  # 2.5 MB
RESIZE_MIN_DIMENSION = 1
RESIZE_MAX_DIMENSION = 5000

bot = telebot.TeleBot(BOT_TOKEN)

# ─── Translations ───
TEXT = {
    "bn": {
        "choose_lang": "🌐 আপনার ভাষা সিলেক্ট করুন:",
        "lang_set": "✅ ভাষা বাংলা সেট করা হয়েছে!",
        "welcome_admin": "👋 স্বাগতম Admin!\n\n📁 ফাইল পাঠান — link বানিয়ে দেব।\n📝 /text <লেখা> — লেখাকে text document বানিয়ে link দেব।\n🪪 /passport — ছবি পাসপোর্ট সাইজে বানিয়ে link দেব।\n🖼️ /resize — নিজের মতো height/width/size/format দিয়ে ছবি বানিয়ে link দেব।\n\n📋 /list — সব ফাইল\n👥 /users — সব user দেখুন\n🟢 /active — ২৪ ঘণ্টায় active user\n📊 /stats — Bot statistics\n🔍 /userinfo <id> — User এর সব activity\n❌ /delete <id> — ফাইল মুছুন\n🚫 /block <id> — Block\n✅ /unblock <id> — Unblock\n🔎 /uploader <file_id> — কে আপলোড করেছে\n🌐 /language — ভাষা পরিবর্তন\n❓ /help — সব command এর তালিকা",
        "welcome_user": "📁 এই bot থেকে ফাইল ডাউনলোড করুন।\n📝 /text <লেখা> — লেখাকে text document বানিয়ে link দেব।\n🪪 /passport — ছবি পাসপোর্ট সাইজে বানিয়ে link দেব।\n🖼️ /resize — নিজের মতো height/width/size/format দিয়ে ছবি বানিয়ে link দেব।\n🌐 /language — ভাষা পরিবর্তন করুন",
        "text_usage": "📝 ব্যবহার: /text এর পর আপনার লেখা লিখুন।\nউদাহরণ: /text এখানে আপনার বড় লেখাটি লিখুন...",
        "passport_ask_photo": "🪪 এখন একটা ছবি পাঠান — আমি সেটাকে পাসপোর্ট সাইজে (35mm x 45mm) বানিয়ে দেব।",
        "passport_error": "❌ ছবি process করতে সমস্যা হয়েছে: {error}",
        "passport_low_res": "⚠️ আপনার ছবির resolution কম, তাই বড় করার (upscale) কারণে ছবিটা কিছুটা ঘোলা/blur দেখাতে পারে। ভালো মানের জন্য বেশি resolution এর ছবি পাঠান।",
        "resize_ask_photo": "🖼️ যে ছবিটা resize করতে চান, সেটা পাঠান।",
        "resize_ask_width": "📏 Width কত pixel চান? (১-৫০০০ এর মধ্যে সংখ্যা লিখুন, উদাহরণ: 600)",
        "resize_ask_height": "📐 Height কত pixel চান? (১-৫০০০ এর মধ্যে সংখ্যা লিখুন, উদাহরণ: 800)",
        "resize_ask_format": "🗂️ কোন format এ ছবি চান?",
        "resize_ask_size": "📦 Target size কত KB চান? (সর্বনিম্ন 30 KB, সর্বোচ্চ 2560 KB / 2.5MB)",
        "resize_invalid_dimension": "❌ সঠিক pixel সংখ্যা লিখুন (১ থেকে ৫০০০ এর মধ্যে)।",
        "resize_invalid_size": "❌ সঠিক size লিখুন (৩০ KB থেকে ২৫৬০ KB এর মধ্যে)।",
        "resize_error": "❌ ছবি process করতে সমস্যা হয়েছে: {error}",
        "resize_note": "🖼️ Size: {w}x{h}px | Format: {fmt} | ফাইল সাইজ: ~{size}KB (target ছিল {target}KB)\n",
        "ask_limit": "📌 এই ফাইলে কী ধরনের limit দিতে চান?",
        "btn_download_limit": "⬇️ Download limit দিন",
        "btn_time_limit": "⏰ Time limit দিন",
        "btn_both": "উভয়ই দিন",
        "btn_none": "✅ কোনো limit নেই",
        "ask_download_count": "🔢 কতবার ডাউনলোড করা যাবে? (সর্বোচ্চ {max} বার)",
        "ask_time_unit": "⏰ কোন unit এ সময় দিতে চান?",
        "btn_minutes": "🕐 মিনিট",
        "btn_hours": "🕑 ঘণ্টা",
        "ask_minutes": "🔢 কত মিনিট পর expire হবে? (সর্বোচ্চ {max} মিনিট)",
        "ask_hours": "🔢 কত ঘণ্টা পর expire হবে? (সর্বোচ্চ {max} ঘণ্টা)",
        "invalid_number": "❌ সঠিক সংখ্যা লিখুন।",
        "exceeds_max_download": "❌ সর্বোচ্চ {max} বার পর্যন্ত limit দেওয়া যাবে।",
        "exceeds_max_time": "❌ সর্বোচ্চ {max} পর্যন্ত সময় দেওয়া যাবে।",
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
        "blocked": "🚫 আপনাকে এই bot ব্যবহার থেকে ব্লক করা হয়েছে।",
        "block_usage": "Usage: /block <user_id>",
        "user_blocked": "🚫 User {id} block করা হয়েছে।",
        "unblock_usage": "Usage: /unblock <user_id>",
        "user_unblocked": "✅ User {id} unblock করা হয়েছে।",
        "uploader_usage": "Usage: /uploader <file_id>",
        "uploader_info": "🔍 Uploader তথ্য:\n👤 User ID: {uid}\n📛 Username: @{username}\n📁 File: {filename}\n📅 Uploaded: {date}",
        "uploader_not_found": "❌ এই file_id খুঁজে পাওয়া যায়নি।",
    },
    "en": {
        "choose_lang": "🌐 Choose your language:",
        "lang_set": "✅ Language set to English!",
        "welcome_admin": "👋 Welcome Admin!\n\n📁 Send a file — I'll create a link.\n📝 /text <content> — Turn text into a document and get a link.\n🪪 /passport — Resize a photo to passport size and get a link.\n🖼️ /resize — Set your own height/width/size/format and get a link.\n\n📋 /list — All files\n👥 /users — All users\n🟢 /active — Active users (24h)\n📊 /stats — Bot statistics\n🔍 /userinfo <id> — User's full activity\n❌ /delete <id> — Delete file\n🚫 /block <id> — Block\n✅ /unblock <id> — Unblock\n🔎 /uploader <file_id> — See uploader\n🌐 /language — Change language\n❓ /help — Full command list",
        "welcome_user": "📁 Download files from this bot.\n📝 /text <content> — Turn text into a document and get a link.\n🪪 /passport — Resize a photo to passport size and get a link.\n🖼️ /resize — Set your own height/width/size/format and get a link.\n🌐 /language — Change language",
        "text_usage": "📝 Usage: type /text followed by your text.\nExample: /text Paste your long text here...",
        "passport_ask_photo": "🪪 Now send a photo — I'll resize it to passport size (35mm x 45mm).",
        "passport_error": "❌ Couldn't process the photo: {error}",
        "passport_low_res": "⚠️ Your photo's resolution is low, so upscaling it may make it look a bit blurry. Send a higher-resolution photo for better quality.",
        "resize_ask_photo": "🖼️ Send the photo you want to resize.",
        "resize_ask_width": "📏 What width in pixels? (1-5000, e.g. 600)",
        "resize_ask_height": "📐 What height in pixels? (1-5000, e.g. 800)",
        "resize_ask_format": "🗂️ Which format do you want?",
        "resize_ask_size": "📦 What target size in KB? (min 30 KB, max 2560 KB / 2.5MB)",
        "resize_invalid_dimension": "❌ Please enter a valid pixel value (between 1 and 5000).",
        "resize_invalid_size": "❌ Please enter a valid size (between 30 KB and 2560 KB).",
        "resize_error": "❌ Couldn't process the photo: {error}",
        "resize_note": "🖼️ Size: {w}x{h}px | Format: {fmt} | File size: ~{size}KB (target was {target}KB)\n",
        "ask_limit": "📌 What kind of limit do you want for this file?",
        "btn_download_limit": "⬇️ Download Limit",
        "btn_time_limit": "⏰ Time Limit",
        "btn_both": "Both",
        "btn_none": "✅ No Limit",
        "ask_download_count": "🔢 How many times can it be downloaded? (max {max})",
        "ask_time_unit": "⏰ Which unit do you want to use?",
        "btn_minutes": "🕐 Minutes",
        "btn_hours": "🕑 Hours",
        "ask_minutes": "🔢 How many minutes until expiry? (max {max} minutes)",
        "ask_hours": "🔢 How many hours until expiry? (max {max} hours)",
        "invalid_number": "❌ Please enter a valid number.",
        "exceeds_max_download": "❌ Maximum allowed limit is {max} downloads.",
        "exceeds_max_time": "❌ Maximum allowed time is {max}.",
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
        "blocked": "🚫 You have been blocked from using this bot.",
        "block_usage": "Usage: /block <user_id>",
        "user_blocked": "🚫 User {id} blocked.",
        "unblock_usage": "Usage: /unblock <user_id>",
        "user_unblocked": "✅ User {id} unblocked.",
        "uploader_usage": "Usage: /uploader <file_id>",
        "uploader_info": "🔍 Uploader info:\n👤 User ID: {uid}\n📛 Username: @{username}\n📁 File: {filename}\n📅 Uploaded: {date}",
        "uploader_not_found": "❌ This file_id was not found.",
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
            created_at TEXT NOT NULL,
            uploader_id INTEGER,
            uploader_username TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            language TEXT DEFAULT 'en',
            username TEXT,
            first_name TEXT,
            blocked INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_uid TEXT,
            downloader_id INTEGER,
            downloader_username TEXT,
            downloaded_at TEXT
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

def save_username(user_id, username, first_name=None):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT user_id FROM users WHERE user_id = ?", (user_id,))
    exists = cursor.fetchone()
    if exists:
        conn.execute("UPDATE users SET username = ?, first_name = ?, last_seen = ? WHERE user_id = ?", (username, first_name, now, user_id))
    else:
        conn.execute("INSERT INTO users (user_id, username, first_name, first_seen, last_seen) VALUES (?, ?, ?, ?, ?)", (user_id, username, first_name, now, now))
    conn.commit()
    conn.close()

def is_blocked(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT blocked FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row and row[0] == 1

def block_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO users (user_id, blocked) VALUES (?, 1) ON CONFLICT(user_id) DO UPDATE SET blocked = 1", (user_id,))
    conn.commit()
    conn.close()

def unblock_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE users SET blocked = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def save_file(file_id, file_name, file_type, max_downloads=-1, expires_at=None, uploader_id=None, uploader_username=None):
    uid = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    conn.execute("""
        INSERT INTO files (id, file_id, file_name, file_type, max_downloads, download_count, expires_at, created_at, uploader_id, uploader_username)
        VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)
    """, (uid, file_id, file_name, file_type, max_downloads, expires_at, now, uploader_id, uploader_username))
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
            "download_count": row[5], "expires_at": row[6], "created_at": row[7],
            "uploader_id": row[8], "uploader_username": row[9]
        }
    return None

def increment_download(uid):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("UPDATE files SET download_count = download_count + 1 WHERE id = ?", (uid,))
    conn.commit()
    conn.close()

def log_download(file_uid, downloader_id, downloader_username):
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    conn.execute("INSERT INTO downloads (file_uid, downloader_id, downloader_username, downloaded_at) VALUES (?, ?, ?, ?)",
                 (file_uid, downloader_id, downloader_username, now))
    conn.commit()
    conn.close()

def delete_file(uid):
    conn = sqlite3.connect(DB_NAME)
    conn.execute("DELETE FROM files WHERE id = ?", (uid,))
    conn.commit()
    conn.close()

def list_files():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT id, file_name, max_downloads, download_count, expires_at, uploader_username FROM files ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_all_users(online_only=False):
    conn = sqlite3.connect(DB_NAME)
    if online_only:
        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
        cursor = conn.execute("SELECT user_id, username, blocked, first_seen, last_seen, first_name FROM users WHERE last_seen > ? ORDER BY last_seen DESC", (cutoff,))
    else:
        cursor = conn.execute("SELECT user_id, username, blocked, first_seen, last_seen, first_name FROM users ORDER BY last_seen DESC")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_stats():
    conn = sqlite3.connect(DB_NAME)
    total_users = conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
    blocked_users = conn.execute("SELECT COUNT(*) FROM users WHERE blocked = 1").fetchone()[0]
    total_files = conn.execute("SELECT COUNT(*) FROM files").fetchone()[0]
    total_downloads = conn.execute("SELECT COUNT(*) FROM downloads").fetchone()[0]
    # Active in last 24 hours
    yesterday = (datetime.now() - timedelta(hours=24)).isoformat()
    active_24h = conn.execute("SELECT COUNT(*) FROM users WHERE last_seen > ?", (yesterday,)).fetchone()[0]
    conn.close()
    return {
        "total_users": total_users,
        "blocked_users": blocked_users,
        "total_files": total_files,
        "total_downloads": total_downloads,
        "active_24h": active_24h
    }

def get_user_activity(user_id):
    conn = sqlite3.connect(DB_NAME)
    user_row = conn.execute("SELECT user_id, username, blocked, first_seen, last_seen, language, first_name FROM users WHERE user_id = ?", (user_id,)).fetchone()
    uploads = conn.execute("SELECT id, file_name, created_at, download_count FROM files WHERE uploader_id = ? ORDER BY created_at DESC", (user_id,)).fetchall()
    downloads = conn.execute("SELECT file_uid, downloaded_at FROM downloads WHERE downloader_id = ? ORDER BY downloaded_at DESC", (user_id,)).fetchall()
    conn.close()
    return user_row, uploads, downloads

# Temp storage
pending_files = {}
pending_action = {}
pending_start_uid = {}
pending_passport = {}
pending_resize = {}

def is_owner(user_id):
    return user_id == ADMIN_ID

def is_admin(user_id):
    return True

# ─── Keyboards ───
def language_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🇧🇩 বাংলা", callback_data="setlang_bn"))
    kb.add(InlineKeyboardButton("🇬🇧 English", callback_data="setlang_en"))
    return kb

def time_unit_keyboard(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton(t(user_id, "btn_minutes"), callback_data="timeunit_minutes"))
    kb.add(InlineKeyboardButton(t(user_id, "btn_hours"), callback_data="timeunit_hours"))
    return kb

def ask_limit_type(chat_id, user_id):
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_download_limit"), callback_data="limit_download"))
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_time_limit"), callback_data="limit_time"))
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_both"), callback_data="limit_both"))
    keyboard.add(InlineKeyboardButton(t(user_id, "btn_none"), callback_data="limit_none"))
    bot.send_message(chat_id, t(user_id, "ask_limit"), reply_markup=keyboard)

def make_passport_photo(image_bytes):
    img = Image.open(io.BytesIO(image_bytes))
    img = img.convert("RGB")
    target_w, target_h = PASSPORT_SIZE
    target_ratio = target_w / target_h
    w, h = img.size
    current_ratio = w / h

    if current_ratio > target_ratio:
        # image is relatively wider than target -> crop sides
        new_w = int(h * target_ratio)
        left = (w - new_w) // 2
        img = img.crop((left, 0, left + new_w, h))
    else:
        # image is relatively taller than target -> crop top/bottom
        new_h = int(w / target_ratio)
        top = (h - new_h) // 2
        img = img.crop((0, top, w, top + new_h))

    # after cropping to the right aspect ratio, check if we'd be upscaling
    cropped_w, cropped_h = img.size
    is_upscaled = cropped_w < target_w or cropped_h < target_h

    img = img.resize(PASSPORT_SIZE, Image.LANCZOS)
    output = io.BytesIO()
    img.save(output, format="JPEG", quality=95)
    output.seek(0)
    return output, is_upscaled

def resize_format_keyboard():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("JPG", callback_data="resizefmt_jpg"))
    kb.add(InlineKeyboardButton("PNG", callback_data="resizefmt_png"))
    kb.add(InlineKeyboardButton("WEBP", callback_data="resizefmt_webp"))
    return kb

def compress_image_to_target(img, fmt, target_bytes):
    """Resize-compress img to at most target_bytes. Returns a BytesIO buffer."""
    fmt = fmt.lower()
    pillow_fmt = {"jpg": "JPEG", "png": "PNG", "webp": "WEBP"}[fmt]

    if pillow_fmt in ("JPEG", "WEBP"):
        if pillow_fmt == "JPEG" and img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")
        low, high = 5, 95
        best_buf = None
        while low <= high:
            mid = (low + high) // 2
            buf = io.BytesIO()
            save_kwargs = {"quality": mid}
            if pillow_fmt == "WEBP":
                save_kwargs["method"] = 6
            img.save(buf, format=pillow_fmt, **save_kwargs)
            if buf.tell() <= target_bytes:
                best_buf = buf
                low = mid + 1
            else:
                high = mid - 1
        if best_buf is None:
            # even the lowest quality exceeds target; use lowest quality anyway
            best_buf = io.BytesIO()
            save_kwargs = {"quality": 5}
            if pillow_fmt == "WEBP":
                save_kwargs["method"] = 6
            img.save(best_buf, format=pillow_fmt, **save_kwargs)
        best_buf.seek(0)
        return best_buf
    else:
        # PNG is lossless; shrink via optimize, then palette quantization if still too big
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")
        buf = io.BytesIO()
        img.save(buf, format="PNG", optimize=True)
        if buf.tell() <= target_bytes:
            buf.seek(0)
            return buf
        for colors in (256, 128, 64, 32, 16, 8):
            quantized = img.convert("P", palette=Image.ADAPTIVE, colors=colors)
            buf = io.BytesIO()
            quantized.save(buf, format="PNG", optimize=True)
            if buf.tell() <= target_bytes:
                buf.seek(0)
                return buf
        buf.seek(0)
        return buf  # best effort; may still exceed target for very complex images

# ─── /passport ───
@bot.message_handler(commands=['passport'])
def passport_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    first_name = message.from_user.first_name or ""
    save_username(user_id, username, first_name)

    if is_blocked(user_id):
        bot.reply_to(message, t(user_id, "blocked"))
        return

    pending_passport[user_id] = True
    bot.reply_to(message, t(user_id, "passport_ask_photo"))

def handle_passport_photo(message, user_id):
    try:
        file_info = bot.get_file(message.photo[-1].file_id)
        raw_bytes = bot.download_file(file_info.file_path)
        output, is_upscaled = make_passport_photo(raw_bytes)
    except Exception as e:
        bot.reply_to(message, t(user_id, "passport_error", error=str(e)))
        return

    if is_upscaled:
        bot.send_message(message.chat.id, t(user_id, "passport_low_res"))

    filename = f"passport_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    output.name = filename
    sent = bot.send_document(message.chat.id, output, visible_file_name=filename)

    pending_files[user_id] = {
        "file_id": sent.document.file_id,
        "file_name": filename,
        "file_type": "document"
    }
    ask_limit_type(message.chat.id, user_id)

# ─── /resize ───
@bot.message_handler(commands=['resize'])
def resize_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    first_name = message.from_user.first_name or ""
    save_username(user_id, username, first_name)

    if is_blocked(user_id):
        bot.reply_to(message, t(user_id, "blocked"))
        return

    pending_resize[user_id] = {}
    bot.reply_to(message, t(user_id, "resize_ask_photo"))

def start_resize_dimensions(message, user_id):
    bot.send_message(message.chat.id, t(user_id, "resize_ask_width"))
    bot.register_next_step_handler(message, got_resize_width, user_id)

def got_resize_width(message, user_id):
    if user_id not in pending_resize:
        return
    try:
        width = int(message.text.strip())
        if width < RESIZE_MIN_DIMENSION or width > RESIZE_MAX_DIMENSION:
            raise ValueError
    except ValueError:
        bot.reply_to(message, t(user_id, "resize_invalid_dimension"))
        bot.register_next_step_handler(message, got_resize_width, user_id)
        return
    pending_resize[user_id]["width"] = width
    bot.send_message(message.chat.id, t(user_id, "resize_ask_height"))
    bot.register_next_step_handler(message, got_resize_height, user_id)

def got_resize_height(message, user_id):
    if user_id not in pending_resize:
        return
    try:
        height = int(message.text.strip())
        if height < RESIZE_MIN_DIMENSION or height > RESIZE_MAX_DIMENSION:
            raise ValueError
    except ValueError:
        bot.reply_to(message, t(user_id, "resize_invalid_dimension"))
        bot.register_next_step_handler(message, got_resize_height, user_id)
        return
    pending_resize[user_id]["height"] = height
    bot.send_message(message.chat.id, t(user_id, "resize_ask_format"), reply_markup=resize_format_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("resizefmt_"))
def handle_resize_format(call):
    user_id = call.from_user.id
    if user_id not in pending_resize:
        return
    fmt = call.data.split("_")[1]
    pending_resize[user_id]["format"] = fmt
    bot.edit_message_text(t(user_id, "resize_ask_size"), call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(call.message, got_resize_size, user_id)

def got_resize_size(message, user_id):
    if user_id not in pending_resize:
        return
    try:
        size_kb = float(message.text.strip())
        if size_kb < RESIZE_MIN_KB or size_kb > RESIZE_MAX_KB:
            raise ValueError
    except ValueError:
        bot.reply_to(message, t(user_id, "resize_invalid_size"))
        bot.register_next_step_handler(message, got_resize_size, user_id)
        return
    pending_resize[user_id]["size_kb"] = size_kb
    process_resize(message, user_id)

def process_resize(message, user_id):
    data = pending_resize.pop(user_id, None)
    if not data or "file_id" not in data:
        return
    try:
        file_info = bot.get_file(data["file_id"])
        raw_bytes = bot.download_file(file_info.file_path)
        img = Image.open(io.BytesIO(raw_bytes))
        img = img.resize((data["width"], data["height"]), Image.LANCZOS)
        target_bytes = int(data["size_kb"] * 1024)
        output = compress_image_to_target(img, data["format"], target_bytes)
    except Exception as e:
        bot.reply_to(message, t(user_id, "resize_error", error=str(e)))
        return

    actual_kb = round(len(output.getvalue()) / 1024, 1)
    ext = data["format"]
    filename = f"resized_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    output.name = filename

    bot.send_message(message.chat.id, t(
        user_id, "resize_note",
        w=data["width"], h=data["height"], fmt=ext.upper(),
        size=actual_kb, target=data["size_kb"]
    ))

    sent = bot.send_document(message.chat.id, output, visible_file_name=filename)

    pending_files[user_id] = {
        "file_id": sent.document.file_id,
        "file_name": filename,
        "file_type": "document"
    }
    ask_limit_type(message.chat.id, user_id)

# ─── /start ───
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    first_name = message.from_user.first_name or ""
    save_username(user_id, username, first_name)

    if is_blocked(user_id):
        bot.reply_to(message, t(user_id, "blocked"))
        return

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

    if is_owner(user_id):
        bot.reply_to(message, t(user_id, "welcome_admin"))
    else:
        bot.reply_to(message, t(user_id, "welcome_user"))

# ─── /help (owner only - full command guide) ───
@bot.message_handler(commands=['help'])
def help_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        bot.reply_to(message, t(user_id, "welcome_user"))
        return
    lang = get_user_lang(user_id) or "bn"
    if lang == "bn":
        text = (
            "📖 *সকল Admin Command:*\n\n"
            "📝 /text <লেখা> — লেখাকে .txt ফাইল বানিয়ে download link দেয়\n\n"
            "🪪 /passport — ছবি পাসপোর্ট সাইজে (35x45mm) বানিয়ে download link দেয়\n\n"
            "🖼️ /resize — নিজের মতো height, width, size (30KB-2.5MB), format (jpg/png/webp) দিয়ে ছবি বানায়\n\n"
            "📋 /list — সব আপলোড করা ফাইলের তালিকা (কে আপলোড করেছে, কতবার ডাউনলোড হয়েছে)\n\n"
            "👥 /users — সব user এর তালিকা (কে কবে join করেছে, last active কবে)\n\n"
            "🟢 /active — গত ২৪ ঘণ্টায় যারা bot ব্যবহার করেছে শুধু তাদের তালিকা\n\n"
            "📊 /stats — মোট user, blocked user, মোট file, মোট download, গত ২৪ ঘণ্টায় active user সংখ্যা\n\n"
            "🔍 /userinfo <user_id> — নির্দিষ্ট user এর সব তথ্য: সে কি কি upload করেছে, কি কি download করেছে, কবে join করেছে\n\n"
            "🔎 /uploader <file_id> — একটা নির্দিষ্ট file কে আপলোড করেছে তা দেখুন\n\n"
            "❌ /delete <file_id> — নির্দিষ্ট ফাইল মুছে ফেলুন\n\n"
            "🚫 /block <user_id> — কাউকে bot ব্যবহার থেকে block করুন\n\n"
            "✅ /unblock <user_id> — Block তুলে দিন\n\n"
            "🌐 /language — নিজের ভাষা পরিবর্তন করুন\n\n"
            "💡 User ID পেতে /users বা /list ব্যবহার করুন।"
        )
    else:
        text = (
            "📖 *All Admin Commands:*\n\n"
            "📝 /text <content> — Turn text into a .txt file and get a download link\n\n"
            "🪪 /passport — Resize a photo to passport size (35x45mm) and get a download link\n\n"
            "🖼️ /resize — Set your own height, width, size (30KB-2.5MB), format (jpg/png/webp)\n\n"
            "📋 /list — List of all uploaded files (who uploaded, download count)\n\n"
            "👥 /users — List of all users (join date, last active)\n\n"
            "🟢 /active — Only users active in the last 24 hours\n\n"
            "📊 /stats — Total users, blocked users, total files, total downloads, active users in last 24h\n\n"
            "🔍 /userinfo <user_id> — Full activity of a specific user: uploads, downloads, join date\n\n"
            "🔎 /uploader <file_id> — See who uploaded a specific file\n\n"
            "❌ /delete <file_id> — Delete a specific file\n\n"
            "🚫 /block <user_id> — Block a user from using the bot\n\n"
            "✅ /unblock <user_id> — Unblock a user\n\n"
            "🌐 /language — Change your language\n\n"
            "💡 Use /users or /list to find user IDs."
        )
    bot.reply_to(message, text, parse_mode="Markdown")

# ─── /language ───
@bot.message_handler(commands=['language'])
def language_cmd(message):
    bot.send_message(message.chat.id, TEXT["bn"]["choose_lang"] + "\n" + TEXT["en"]["choose_lang"], reply_markup=language_keyboard())

@bot.callback_query_handler(func=lambda call: call.data.startswith("setlang_"))
def set_language(call):
    user_id = call.from_user.id
    lang = call.data.split("_")[1]
    set_user_lang(user_id, lang)
    bot.edit_message_text(TEXT[lang]["lang_set"], call.message.chat.id, call.message.message_id)

    if user_id in pending_start_uid:
        uid = pending_start_uid.pop(user_id)
        send_file(call.message, uid, user_id_override=user_id)
        return

    if is_owner(user_id):
        bot.send_message(call.message.chat.id, t(user_id, "welcome_admin"))
    else:
        bot.send_message(call.message.chat.id, t(user_id, "welcome_user"))

# ─── /list ───
@bot.message_handler(commands=['list'])
def list_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    files = list_files()
    if not files:
        bot.reply_to(message, t(user_id, "no_files"))
        return
    text = t(user_id, "file_list_title")
    for f in files:
        mx = f[2] if f[2] != -1 else t(user_id, "unlimited")
        exp = f[4] if f[4] else t(user_id, "none")
        uploader = f[5] or "unknown"
        text += f"🔑 {f[0]} — {f[1]}\n👤 @{uploader} | ⬇️ {f[3]}/{mx} | ⏰ {exp}\n\n"
    # Telegram message length limit
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000])
    else:
        bot.reply_to(message, text)

# ─── /users (owner only) ───
@bot.message_handler(commands=['users'])
def users_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    users = get_all_users()
    if not users:
        bot.reply_to(message, "কোনো user নেই।" if get_user_lang(user_id) == "bn" else "No users found.")
        return
    lang = get_user_lang(user_id) or "bn"
    title = "👥 সব User (মোট {n}):\n\n".format(n=len(users)) if lang == "bn" else "👥 All Users (Total {n}):\n\n".format(n=len(users))
    text = title
    cutoff = datetime.now() - timedelta(hours=24)
    for u in users:
        block_status = "🚫 Blocked" if u[2] == 1 else "✅ Not Blocked"
        last_seen_dt = None
        try:
            last_seen_dt = datetime.fromisoformat(u[4]) if u[4] else None
        except Exception:
            pass
        online_status = "🟢 Online (24h)" if last_seen_dt and last_seen_dt > cutoff else "⚪ Inactive"
        last_seen = u[4][:16] if u[4] else "-"
        joined = u[3][:16] if u[3] else "-"
        name = u[5] or ""
        phone = "-"
        try:
            chat = bot.get_chat(u[0])
            if hasattr(chat, "phone_number") and chat.phone_number:
                phone = chat.phone_number
        except Exception:
            pass
        if lang == "bn":
            text += (
                f"🧑 নাম: {name}\n"
                f"👤 Username: @{u[1] or 'no_username'}\n"
                f"🆔 ID: {u[0]}\n"
                f"📞 ফোন: {phone}\n"
                f"📌 {block_status} | {online_status}\n"
                f"📅 যোগ দিয়েছে: {joined}\n"
                f"🕐 শেষ active: {last_seen}\n\n"
            )
        else:
            text += (
                f"🧑 Name: {name}\n"
                f"👤 Username: @{u[1] or 'no_username'}\n"
                f"🆔 ID: {u[0]}\n"
                f"📞 Phone: {phone}\n"
                f"📌 {block_status} | {online_status}\n"
                f"📅 Joined: {joined}\n"
                f"🕐 Last seen: {last_seen}\n\n"
            )
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000])
    else:
        bot.reply_to(message, text)

# ─── /active (owner only) - shows only users active in last 24h ───
@bot.message_handler(commands=['active'])
def active_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    users = get_all_users(online_only=True)
    lang = get_user_lang(user_id) or "bn"
    if not users:
        bot.reply_to(message, "গত ২৪ ঘণ্টায় কেউ active ছিল না।" if lang == "bn" else "No users active in last 24 hours.")
        return
    title = "🟢 Active User (গত ২৪ ঘণ্টা) - মোট {n}:\n\n".format(n=len(users)) if lang == "bn" else "🟢 Active Users (last 24h) - Total {n}:\n\n".format(n=len(users))
    text = title
    for u in users:
        block_status = "🚫 Blocked" if u[2] == 1 else "✅ Not Blocked"
        last_seen = u[4][:16] if u[4] else "-"
        name = u[5] or ""
        if lang == "bn":
            text += f"🧑 {name} (@{u[1] or 'no_username'})\n🆔 {u[0]} | {block_status}\n🕐 শেষ active: {last_seen}\n\n"
        else:
            text += f"🧑 {name} (@{u[1] or 'no_username'})\n🆔 {u[0]} | {block_status}\n🕐 Last seen: {last_seen}\n\n"
    if len(text) > 4000:
        for i in range(0, len(text), 4000):
            bot.send_message(message.chat.id, text[i:i+4000])
    else:
        bot.reply_to(message, text)

# ─── /stats (owner only) ───
@bot.message_handler(commands=['stats'])
def stats_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    s = get_stats()
    lang = get_user_lang(user_id) or "bn"
    if lang == "bn":
        text = (
            f"📊 *Bot Statistics:*\n\n"
            f"👥 মোট User: {s['total_users']}\n"
            f"🟢 গত ২৪ ঘণ্টায় Active: {s['active_24h']}\n"
            f"🚫 Blocked User: {s['blocked_users']}\n"
            f"📁 মোট File: {s['total_files']}\n"
            f"⬇️ মোট Download: {s['total_downloads']}"
        )
    else:
        text = (
            f"📊 *Bot Statistics:*\n\n"
            f"👥 Total Users: {s['total_users']}\n"
            f"🟢 Active in last 24h: {s['active_24h']}\n"
            f"🚫 Blocked Users: {s['blocked_users']}\n"
            f"📁 Total Files: {s['total_files']}\n"
            f"⬇️ Total Downloads: {s['total_downloads']}"
        )
    bot.reply_to(message, text, parse_mode="Markdown")

# ─── /userinfo (owner only) ───
@bot.message_handler(commands=['userinfo'])
def userinfo_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    try:
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Usage: /userinfo <user_id>")
            return
        target_id = int(parts[1])
        user_row, uploads, downloads = get_user_activity(target_id)
        lang = get_user_lang(user_id) or "bn"

        if not user_row:
            bot.reply_to(message, "❌ User খুঁজে পাওয়া যায়নি।" if lang == "bn" else "❌ User not found.")
            return

        status = "🚫 Blocked" if user_row[2] == 1 else "✅ Active"
        phone = "-"
        try:
            chat = bot.get_chat(target_id)
            if hasattr(chat, "phone_number") and chat.phone_number:
                phone = chat.phone_number
        except Exception:
            pass
        if lang == "bn":
            text = (
                f"🔍 User তথ্য:\n\n"
                f"🧑 নাম: {user_row[6] or '-'}\n"
                f"👤 Username: @{user_row[1] or 'no_username'}\n"
                f"🆔 User ID: {user_row[0]}\n"
                f"📞 ফোন: {phone}\n"
                f"📌 Status: {status}\n"
                f"🌐 ভাষা: {user_row[5]}\n"
                f"📅 প্রথম এসেছে: {user_row[3][:16] if user_row[3] else '-'}\n"
                f"🕐 শেষ active: {user_row[4][:16] if user_row[4] else '-'}\n\n"
                f"📤 Upload করেছে ({len(uploads)}টি):\n"
            )
            if uploads:
                for up in uploads[:10]:
                    text += f"  📁 {up[1]} | ⬇️{up[3]} বার | {up[2][:16]}\n"
            else:
                text += "  কিছু upload করেনি।\n"
            text += f"\n📥 Download করেছে ({len(downloads)}টি):\n"
            if downloads:
                for dl in downloads[:10]:
                    text += f"  🔑 {dl[0]} | {dl[1][:16]}\n"
            else:
                text += "  কিছু download করেনি।\n"
        else:
            text = (
                f"🔍 User Info:\n\n"
                f"🧑 Name: {user_row[6] or '-'}\n"
                f"👤 Username: @{user_row[1] or 'no_username'}\n"
                f"🆔 User ID: {user_row[0]}\n"
                f"📞 Phone: {phone}\n"
                f"📌 Status: {status}\n"
                f"🌐 Language: {user_row[5]}\n"
                f"📅 First seen: {user_row[3][:16] if user_row[3] else '-'}\n"
                f"🕐 Last active: {user_row[4][:16] if user_row[4] else '-'}\n\n"
                f"📤 Uploads ({len(uploads)}):\n"
            )
            if uploads:
                for up in uploads[:10]:
                    text += f"  📁 {up[1]} | ⬇️{up[3]}x | {up[2][:16]}\n"
            else:
                text += "  No uploads.\n"
            text += f"\n📥 Downloads ({len(downloads)}):\n"
            if downloads:
                for dl in downloads[:10]:
                    text += f"  🔑 {dl[0]} | {dl[1][:16]}\n"
            else:
                text += "  No downloads.\n"

        bot.reply_to(message, text)
    except Exception as e:
        bot.reply_to(message, f"❌ Error: {str(e)}")

# ─── /delete ───
@bot.message_handler(commands=['delete'])
def delete_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, t(user_id, "delete_usage"))
        return
    delete_file(parts[1])
    bot.reply_to(message, t(user_id, "deleted", id=parts[1]))

# ─── /block ───
@bot.message_handler(commands=['block'])
def block_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, t(user_id, "block_usage"))
        return
    target_id = int(parts[1])
    block_user(target_id)
    bot.reply_to(message, t(user_id, "user_blocked", id=target_id))

# ─── /unblock ───
@bot.message_handler(commands=['unblock'])
def unblock_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, t(user_id, "unblock_usage"))
        return
    target_id = int(parts[1])
    unblock_user(target_id)
    bot.reply_to(message, t(user_id, "user_unblocked", id=target_id))

# ─── /uploader ───
@bot.message_handler(commands=['uploader'])
def uploader_cmd(message):
    user_id = message.from_user.id
    if not is_owner(user_id):
        return
    parts = message.text.split()
    if len(parts) < 2:
        bot.reply_to(message, t(user_id, "uploader_usage"))
        return
    file_data = get_file(parts[1])
    if not file_data:
        bot.reply_to(message, t(user_id, "uploader_not_found"))
        return
    bot.reply_to(message, t(user_id, "uploader_info",
        uid=file_data["uploader_id"],
        username=file_data["uploader_username"] or "unknown",
        filename=file_data["file_name"],
        date=file_data["created_at"][:16]
    ))

# ─── File receive ───
@bot.message_handler(content_types=['document', 'photo', 'video', 'audio'])
def receive_file(message):
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    first_name = message.from_user.first_name or ""
    save_username(user_id, username, first_name)

    if is_blocked(user_id):
        bot.reply_to(message, t(user_id, "blocked"))
        return

    if message.photo and pending_passport.pop(user_id, None):
        handle_passport_photo(message, user_id)
        return

    if message.photo and user_id in pending_resize and "file_id" not in pending_resize[user_id]:
        pending_resize[user_id]["file_id"] = message.photo[-1].file_id
        start_resize_dimensions(message, user_id)
        return

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

    ask_limit_type(message.chat.id, user_id)

# ─── /text (text-to-document) ───
@bot.message_handler(commands=['text'])
def text_cmd(message):
    user_id = message.from_user.id
    username = message.from_user.username or "no_username"
    first_name = message.from_user.first_name or ""
    save_username(user_id, username, first_name)

    if is_blocked(user_id):
        bot.reply_to(message, t(user_id, "blocked"))
        return

    if not is_admin(user_id):
        return

    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        bot.reply_to(message, t(user_id, "text_usage"))
        return

    content = parts[1]
    filename = f"text_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    file_bytes = io.BytesIO(content.encode("utf-8"))
    file_bytes.name = filename

    # Send once so Telegram assigns a file_id we can reuse for downloads
    sent = bot.send_document(message.chat.id, file_bytes, visible_file_name=filename)

    pending_files[user_id] = {
        "file_id": sent.document.file_id,
        "file_name": filename,
        "file_type": "document"
    }

    ask_limit_type(message.chat.id, user_id)

# ─── Limit type callback ───
@bot.callback_query_handler(func=lambda call: call.data.startswith("limit_"))
def handle_limit_type(call):
    user_id = call.from_user.id
    choice = call.data
    pending_action[user_id] = {"choice": choice, "max_downloads": -1}

    if choice == "limit_none":
        finalize(call.message, user_id, -1, None)
    elif choice in ("limit_download", "limit_both"):
        bot.edit_message_text(t(user_id, "ask_download_count", max=MAX_DOWNLOADS), call.message.chat.id, call.message.message_id)
        bot.register_next_step_handler(call.message, got_download_count, user_id)
    elif choice == "limit_time":
        bot.edit_message_text(t(user_id, "ask_time_unit"), call.message.chat.id, call.message.message_id, reply_markup=time_unit_keyboard(user_id))

@bot.callback_query_handler(func=lambda call: call.data.startswith("timeunit_"))
def handle_time_unit(call):
    user_id = call.from_user.id
    unit = call.data.split("_")[1]
    pending_action.setdefault(user_id, {"choice": "limit_time", "max_downloads": -1})
    pending_action[user_id]["time_unit"] = unit

    if unit == "minutes":
        bot.edit_message_text(t(user_id, "ask_minutes", max=MAX_TIME_VALUE_MIN), call.message.chat.id, call.message.message_id)
    else:
        bot.edit_message_text(t(user_id, "ask_hours", max=MAX_TIME_VALUE_HOUR), call.message.chat.id, call.message.message_id)
    bot.register_next_step_handler(call.message, got_time_value, user_id)

def got_download_count(message, user_id):
    try:
        count = int(message.text.strip())
        if count <= 0 or count > MAX_DOWNLOADS:
            bot.reply_to(message, t(user_id, "exceeds_max_download", max=MAX_DOWNLOADS))
            return
        pending_action[user_id]["max_downloads"] = count
    except:
        bot.reply_to(message, t(user_id, "invalid_number"))
        return

    if pending_action[user_id]["choice"] == "limit_both":
        bot.send_message(message.chat.id, t(user_id, "ask_time_unit"), reply_markup=time_unit_keyboard(user_id))
    else:
        finalize(message, user_id, count, None)

def got_time_value(message, user_id):
    unit = pending_action.get(user_id, {}).get("time_unit", "hours")
    try:
        value = float(message.text.strip())
        if unit == "minutes":
            if value <= 0 or value > MAX_TIME_VALUE_MIN:
                bot.reply_to(message, t(user_id, "exceeds_max_time", max=f"{MAX_TIME_VALUE_MIN} minutes"))
                return
            total_minutes = value
        else:
            if value <= 0 or value > MAX_TIME_VALUE_HOUR:
                bot.reply_to(message, t(user_id, "exceeds_max_time", max=f"{MAX_TIME_VALUE_HOUR} hours"))
                return
            total_minutes = value * 60

        if total_minutes > MAX_MINUTES:
            bot.reply_to(message, t(user_id, "exceeds_max_time", max="48 hours"))
            return

        expires_at = (datetime.now() + timedelta(minutes=total_minutes)).isoformat()
    except:
        bot.reply_to(message, t(user_id, "invalid_number"))
        return

    max_downloads = pending_action.get(user_id, {}).get("max_downloads", -1)
    finalize(message, user_id, max_downloads, expires_at)

def finalize(message, user_id, max_downloads, expires_at):
    pf = pending_files.pop(user_id, None)
    if not pf:
        return
    username = "no_username"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        username = row[0]

    uid = save_file(pf["file_id"], pf["file_name"], pf["file_type"], max_downloads, expires_at, uploader_id=user_id, uploader_username=username)
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

    # Share button
    share_text = f"📥 ফাইল ডাউনলোড করুন: {pf['file_name']}" if get_user_lang(user_id) == "bn" else f"📥 Download file: {pf['file_name']}"
    share_btn = "📤 Share করুন" if get_user_lang(user_id) == "bn" else "📤 Share"
    share_url = f"https://t.me/share/url?url={link}&text={share_text}"
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton(share_btn, url=share_url))
    bot.reply_to(message, text, reply_markup=keyboard)

def send_file(message, uid, user_id_override=None):
    user_id = user_id_override or message.from_user.id
    if is_blocked(user_id):
        bot.send_message(message.chat.id, t(user_id, "blocked"))
        return
    file_data = get_file(uid)
    if not file_data:
        bot.send_message(message.chat.id, t(user_id, "file_not_found"))
        return

    # Admin/owner bypasses expiry and download limit checks
    if not is_owner(user_id):
        if file_data["expires_at"] and datetime.now() > datetime.fromisoformat(file_data["expires_at"]):
            delete_file(uid)
            bot.send_message(message.chat.id, t(user_id, "file_expired"))
            return
        if file_data["max_downloads"] != -1 and file_data["download_count"] >= file_data["max_downloads"]:
            bot.send_message(message.chat.id, t(user_id, "limit_reached"))
            return
        increment_download(uid)

    username = "no_username"
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.execute("SELECT username FROM users WHERE user_id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    if row and row[0]:
        username = row[0]
    log_download(uid, user_id, username)

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
    print("✅ Bot চালু! Full analytics সহ।")
    bot.infinity_polling()
