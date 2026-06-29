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
        uid = args[0]
        await handle_download(update, context, uid)
        return
    if is_admin(update.effective_user.id):
        await update.message.reply_text(
            "👋 স্বাগতম Admin!\n\n"
            "📁 যেকোনো ফাইল, ছবি, ভিডিও পাঠান।\n\n"
            "📋 /list — সব ফাইল দেখুন\n"
            "❌ /delete <id> — ফাইল মুছুন"
        )
    else:
        await update.message.reply_text("📁 এই bot থেকে ফাইল ডাউনলোড করুন।")

async def receive_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        await update.message.reply_text("❌ আপনার permission নেই।")
        return ConversationHandler.END
    msg = update.message
    file_id = file_name = file_type = None
    if msg.document:
        file_id = msg.document.file_id
        file_name = msg.document.file_name
        file_type = "document"
    elif msg.photo:
        file_id = msg.photo[-1].file_id
        file_name = "photo.jpg"
        file_type = "photo"
    elif msg.video:
        file_id = msg.video.file_id
        file_name = msg.video.file_name or "video.mp4"
        file_type = "video"
    elif msg.audio:
        file_id = msg.audio.file_id
        file_name = msg.audio.file_name or "audio.mp3"
        file_type = "audio"
    else:
        return ConversationHandler.END
    pending_files[update.effective_user.id] = {
        "file_id": file_id, "file_name": file_name, "file_type": file_type
    }
    keyboard = [
        [InlineKeyboardButton("⬇️ Download limit দিন", callback_data="limit_download")],
        [InlineKeyboardButton("⏰ Time limit দিন", callback_data="limit_time")],
        [InlineKeyboardButton("উভয়ই দিন", callback_data="limit_both")],
        [InlineKeyboardButton("✅ কোনো limit নেই", callback_data="limit_none")],
    ]
    await msg.reply_text("📌 কী ধরনের limit দিতে চান?",
                         reply_markup=InlineKeyboardMarkup(keyboard))
    return WAITING_LIMIT_TYPE

async def limit_type_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    choice = query.data
    context.user_data["limit_choice"] = choice
    if choice == "limit_none":
        await finalize_upload(query, context, max_downloads=-1, expires_at=None)
        return ConversationHandler.END
    elif choice == "limit_download":
        await query.edit_message_text("🔢 কতবার ডাউনলোড করা যাবে?")
        return WAITING_DOWNLOAD_COUNT
    elif choice == "limit_time":
        await query.edit_message_text("⏰ কত ঘণ্টা পর expire হবে?")
        return WAITING_HOURS
    elif choice == "limit_both":
        await query.edit_message_text("🔢 কতবার ডাউনলোড করা যাবে?")
        return WAITING_DOWNLOAD_COUNT

async def got_download_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        count = int(update.message.text.strip())
        context.user_data["max_downloads"] = count
    except:
        await update.message.reply_text("❌ সংখ্যা লিখুন।")
        return WAITING_DOWNLOAD_COUNT
    if context.user_data.get("limit_choice") == "limit_both":
        await update.message.reply_text("⏰ কত ঘণ্টা পর expire হবে?")
        return WAITING_HOURS
    else:
        await finalize_upload(update, context, max_downloads=count, expires_at=None)
        return ConversationHandler.END

async def got_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        hours = float(update.message.text.strip())
        expires_at = (datetime.now() + timedelta(hours=hours)).isoformat()
    except:
        await update.message.reply_text("❌ সংখ্যা লিখুন।")
        return WAITING_HOURS
    max_downloads = context.user_data.get("max_downloads", -1)
    await finalize_upload(update, context, max_downloads=max_downloads, expires_at=expires_at)
    return ConversationHandler.END

async def finalize_upload(source, context, max_downloads, expires_at):
    user_id = source.from_user.id if hasattr(source, 'from_user') else source.effective_user.id
    pf = pending_files.pop(user_id, None)
    if not pf:
        return
    uid = await save_file(pf["file_id"], pf["file_name"], pf["file_type"], max_downloads, expires_at)
    bot_username = (await context.bot.get_me()).username
    link = f"https://t.me/{bot_username}?start={uid}"
    limit_text = ""
    if max_downloads > 0:
        limit_text += f"⬇️ সর্বোচ্চ: {max_downloads} বার\n"
    if expires_at:
        exp = datetime.fromisoformat(expires_at).strftime("%d/%m/%Y %H:%M")
        limit_text += f"⏰ Expire: {exp}\n"
    if not limit_text:
        limit_text = "♾️ কোনো limit নেই\n"
    msg_text = (
        f"✅ ফাইল upload হয়েছে!\n\n"
        f"📁 {pf['file_name']}\n"
        f"🔑 ID: `{uid}`\n\n"
        f"{limit_text}\n"
        f"🔗 Link:\n{link}"
    )
    if hasattr(source, 'edit_message_text'):
        await source.edit_message_text(msg_text, parse_mode="Markdown")
    else:
        await source.message.reply_text(msg_text, parse_mode="Markdown")

async def handle_download(update: Update, context: ContextTypes.DEFAULT_TYPE, uid: str):
    file_data = await get_file(uid)
    if not file_data:
        await update.message.reply_text("❌ ফাইলটি পাওয়া যায়নি।")
        return
    if file_data["expires_at"]:
        if datetime.now() > datetime.fromisoformat(file_data["expires_at"]):
            await delete_file(uid)
            await update.message.reply_text("⏰ এই ফাইলের সময় শেষ।")
            return
    if file_data["max_downloads"] != -1:
        if file_data["download_count"] >= file_data["max_downloads"]:
            await update.message.reply_text("❌ Download limit শেষ।")
            return
    await increment_download(uid)
    remaining = "♾️"
    if file_data["max_downloads"] != -1:
        remaining = file_data["max_downloads"] - file_data["download_count"] - 1
    await update.message.reply_text(f"📥 ফাইল পাঠানো হচ্ছে...\n🔢 বাকি: {remaining}")
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
    text = "📋 *সব ফাইল:*\n\n"
    for f in files:
        exp = f[4] if f[4] else "নেই"
        mx = f[2] if f[2] != -1 else "♾️"
        text += f"🔑 `{f[0]}` — {f[1]}\n⬇️ {f[3]}/{mx} | ⏰ {exp}\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def delete_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id):
        return
    if not context.args:
        await update.message.reply_text("Usage: /delete <file_id>")
        return
    await delete_file(context.args[0])
    await update.message.reply_text(f"✅ মুছে ফেলা হয়েছে।")

async def main():
    await init_db()
    app = Application.builder().token(BOT_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(
            filters.Document.ALL | filters.PHOTO | filters.VIDEO | filters.AUDIO,
            receive_file
        )],
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
    print("✅ Bot চালু হয়েছে!")
    await app.run_polling()

if __name__ == "__main__":
    asyncio.run(main())
