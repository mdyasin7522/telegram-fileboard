import os
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters, ConversationHandler
)
from database import init_db, save_file, get_file, increment_download, delete_file, list_files

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))

WAITING_LIMIT_TYPE, WAITING_DOWNLOAD_COUNT, WAITING_HOURS = range(3)
pending_files = {}

def is_admin(user_id):
    return user_id == ADMIN_ID

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if args:
        await handle_download(update, context, args[0])
        return
    if is_admin(update.effective_user.id):
        await update.message.reply_text(
            "👋 স্বাগতম Admin!\n\n📁 ফাইল পাঠান — link বানিয়ে দেব।\n\n📋 /list\n❌ /delete <id>"
        )
    else:
        await update.message.reply_text("📁 এই bot থেকে ফাইল ডাউনলোড করুন।")

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ permission নেই।")
        return ConversationHandler.END
    msg = update.message
    if msg.document:
        pending_files[update.effective_user.id] = {"file_id": msg.document.file_id, "file_name": msg.document.file_name, "file_type": "document"}
    elif msg.photo:
        pending_files[update.effective_user.id] = {"file_id": msg.photo[-1].file_id, "file_name": "photo.jpg", "file_type": "photo"}
    elif msg.video:
        pending_files[update.effective_user.id] = {"file_id": msg.video.file_id, "file_name": msg.video.file_name or "video.mp4", "file_type": "video"}
    elif msg.audio:
        pending_files[update.effective_user.id] = {"file_id": msg.audio.file_id, "file_name": msg.audio.file_name or "audio.mp3", "file_type": "audio"}
    else:
        return ConversationHandler.END
    keyboard = [
        [InlineKeyboardButton("⬇️ Download limit", callback_data="limit_download")],
        [InlineKeyboardButton("⏰ Time limit", callback_data="limit_time")],
        [InlineKeyboardButton("উভয়ই", callback_data="limit_both")],
        [InlineKeyboardButton("✅ কোনো limit নেই", callback_data="limit_none")],
    ]
    await msg.reply_text("📌 limit টাইপ?", reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_LIMIT_TYPE

async def limit_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    context.user_data["limit_choice"] = choice
    if choice == "limit_none":
        await finalize_upload(query, context, -1, None)
        return ConversationHandler.END
    elif choice in ("limit_download", "limit_both"):
        await query.edit_message_text("🔢 কতবার ডাউনলোড?")
        return WAITING_DOWNLOAD_COUNT
    elif choice == "limit_time":
        await query.edit_message_text("⏰ কত ঘণ্টা?")
        return WAITING_HOURS

async def got_download_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        context.user_data["max_downloads"] = count
    except Exception:
        await update.message.reply_text("❌ সংখ্যা লিখুন।")
        return WAITING_DOWNLOAD_COUNT
    if context.user_data.get("limit_choice") == "limit_both":
        await update.message.reply_text("⏰ কত ঘণ্টা?")
        return WAITING_HOURS
    await finalize_upload(update, context, count, None)
    return ConversationHandler.END

async def got_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hours = float(update.message.text.strip())
        expires_at = (datetime.now() + timedelta(hours=hours)).isoformat()
    except Exception:
        await update.message.reply_text("❌ সংখ্যা লিখুন।")
        return WAITING_HOURS
    await finalize_upload(update, context, context.user_data.get("max_downloads", -1), expires_at)
    return ConversationHandler.END

async def finalize_upload(source, context, max_downloads, expires_at):
    user_id = source.from_user.id
    pf = pending_files.pop(user_id, None)
    if not pf:
        return
    uid = await save_file(pf["file_id"], pf["file_name"], pf["file_type"], max_downloads, expires_at)
    me = await context.bot.get_me()
    link = f"https://t.me/{me.username}?start={uid}"
    limit_text = ""
    if max_downloads > 0:
        limit_text += f"⬇️ {max_downloads} বার\n"
    if expires_at:
        limit_text += f"⏰ {datetime.fromisoformat(expires_at).strftime('%d/%m/%Y %H:%M')}\n"
    if not limit_text:
        limit_text = "♾️ কোনো limit নেই\n"
    text = f"✅ Done!\n\n📁 {pf['file_name']}\n🔑 `{uid}`\n\n{limit_text}\n🔗 {link}"
    if hasattr(source, 'edit_message_text'):
        await source.edit_message_text(text, parse_mode="Markdown")
    else:
        await source.message.reply_text(text, parse_mode="Markdown")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: str):
    file_data = await get_file(uid)
    if not file_data:
        await update.message.reply_text("❌ ফাইল নেই।")
        return
    if file_data["expires_at"] and datetime.now() > datetime.fromisoformat(file_data["expires_at"]):
        await delete_file(uid)
        await update.message.reply_text("⏰ Expired।")
        return
    if file_data["max_downloads"] != -1 and file_data["download_count"] >= file_data["max_downloads"]:
        await update.message.reply_text("❌ Limit শেষ।")
        return
    await increment_download(uid)
    remaining = "♾️" if file_data["max_downloads"] == -1 else file_data["max_downloads"] - file_data["download_count"] - 1
    await update.message.reply_text(f"📥 পাঠানো হচ্ছে...\n🔢 বাকি: {remaining}")
    ftype = file_data["file_type"]
    fid = file_data["file_id"]
    if ftype == "document":
        await update.message.reply_document(fid)
    elif ftype == "photo":
        await update.message.reply_photo(fid)
    elif ftype == "video":
        await update.message.reply_video(fid)
    elif ftype == "audio":
        await update.message.reply_audio(fid)

async def list_files_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    files = await list_files()
    if not files:
        await update.message.reply_text("📭 কোনো ফাইল নেই।")
        return
    text = "📋 *ফাইল তালিকা:*\n\n"
    for f in files:
        mx = f[2] if f[2] != -1 else "♾️"
        text += f"🔑 `{f[0]}` — {f[1]} | {f[3]}/{mx}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /delete <id>")
        return
    await delete_file(context.args[0])
    await update.message.reply_text("✅ মুছে ফেলা হয়েছে।")

async def main():
    await init_db()
    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .updater(None)
        .build()
    )
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO, receive_file)],
        states={
            WAITING_LIMIT_TYPE: [CallbackQueryHandler(limit_type_selected)],
            WAITING_DOWNLOAD_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_download_count)],
            WAITING_HOURS: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_hours)],
        },
        fallbacks=[]
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("list", list_files_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(conv)
    print("✅ Bot চালু!")
    async with app:
        await app.start()
        await app.updater.start_polling()
        await asyncio.sleep(float("inf"))

if __name__ == "__main__":
    asyncio.run(main())
