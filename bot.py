import os
import time
import sqlite3
import logging
import asyncio
from http.server import BaseHTTPRequestHandler, HTTPServer
import threading
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- Configuration ---
TOKEN = "8361917661:AAFjCkSYgZZm5BJaxHn8vst1nDDRHhrbeIY" 
ADMIN_ID = 6809528328
DB_PATH = "prediction_bot.db"
QR_PATH = "admin_qr.jpg"

admin_session = {"pass": None, "expiry": 0, "mode": None}
SESSION_TIME = 3600

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Dummy Web Server for Render Health Check ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is alive!")

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server started on port {port}")
    server.serve_forever()

# --- Database Logic ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute(query, params)
        data = cursor.fetchall() if fetch else None
        conn.commit()
        return data
    except Exception as e:
        logger.error(f"Database error: {e}")
    finally:
        conn.close()

def init_db():
    db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0)")

def set_vip_status(uid, status=1):
    db_query("INSERT OR REPLACE INTO users (id, is_vip) VALUES (?, ?)", (uid, status))

def get_users_by_type(is_vip_target):
    rows = db_query("SELECT id FROM users WHERE is_vip = ?", (1 if is_vip_target else 0,), fetch=True)
    return [r[0] for r in rows] if rows else []

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db_query("INSERT OR IGNORE INTO users (id, is_vip) VALUES (?, 0)", (uid,))
    is_logged = time.time() < admin_session["expiry"]
    if uid == ADMIN_ID:
        if not is_logged:
            msg = "👋 Admin! Set password: `/setpass 123`" if not admin_session["pass"] else "🔒 Locked. Login: `/login pass`"
            await update.message.reply_text(msg)
            return
        kb = [[InlineKeyboardButton("📤 Post Free", callback_data='p_free')],
              [InlineKeyboardButton("📤 Post VIP", callback_data='p_vip')],
              [InlineKeyboardButton("💳 Change QR", callback_data='p_qr')],
              [InlineKeyboardButton("🔒 Logout", callback_data='p_logout')]]
        await update.message.reply_text("🛠 **ADMIN PANEL**", reply_markup=InlineKeyboardMarkup(kb))
    else:
        user_data = db_query("SELECT is_vip FROM users WHERE id = ?", (uid,), fetch=True)
        is_user_vip = user_data[0][0] if user_data else 0
        status = "✅ VIP" if is_user_vip else "🆓 FREE"
        await update.message.reply_text(f"Status: {status}\nPredictions will arrive here.")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    uid = q.from_user.id
    await q.answer()
    if q.data == 'buy_vip':
        if os.path.exists(QR_PATH): await context.bot.send_photo(chat_id=uid, photo=open(QR_PATH, 'rb'), caption="Pay and send Screenshot 📸")
        else: await q.message.reply_text("⚠️ QR not set.")
    
    is_logged = time.time() < admin_session["expiry"]
    if uid == ADMIN_ID and is_logged:
        if q.data == 'p_free': admin_session["mode"] = "FREE"; await q.message.reply_text("Send Free Photo.")
        elif q.data == 'p_vip': admin_session["mode"] = "VIP"; await q.message.reply_text("Send VIP Photo.")
        elif q.data == 'p_qr': admin_session["mode"] = "SETQR"; await q.message.reply_text("Send QR Photo.")
        elif q.data == 'p_logout': admin_session["expiry"] = 0; await q.edit_message_text("Logged out.")

    if uid == ADMIN_ID and q.data.startswith(("app_", "dec_")):
        act, target = q.data.split("_")
        if act == "app":
            set_vip_status(int(target), 1)
            await context.bot.send_message(chat_id=target, text="🎊 VIP UNLOCKED!")
            await q.edit_message_caption("Approved ✅")
        else:
            await q.edit_message_caption("Declined ❌")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    is_logged = time.time() < admin_session["expiry"]
    if uid == ADMIN_ID and is_logged:
        mode = admin_session["mode"]
        if mode == "SETQR":
            f = await context.bot.get_file(update.message.photo[-1].file_id)
            await f.download_to_drive(QR_PATH); await update.message.reply_text("✅ QR Updated.")
        elif mode in ["FREE", "VIP"]:
            targets = get_users_by_type(mode == "VIP")
            for t in targets:
                try: await context.bot.copy_message(chat_id=t, from_chat_id=ADMIN_ID, message_id=update.message.message_id)
                except: pass
            await update.message.reply_text("📢 Broadcast Done!")
        admin_session["mode"] = None
        return
    if update.message.photo:
        kb = [[InlineKeyboardButton("Approve ✅", callback_data=f"app_{uid}"), InlineKeyboardButton("Decline ❌", callback_data=f"dec_{uid}")]]
        await context.bot.send_photo(chat_id=ADMIN_ID, photo=update.message.photo[-1].file_id, caption=f"Payment from {uid}", reply_markup=InlineKeyboardMarkup(kb))
        await update.message.reply_text("⏳ Sent for verification.")

async def setpass(u, c):
    if u.effective_user.id == ADMIN_ID and c.args: admin_session["pass"] = c.args[0]; await u.message.reply_text("✅ Pass set.")
async def login(u, c):
    if u.effective_user.id == ADMIN_ID and c.args:
        if c.args[0] == admin_session["pass"]: admin_session["expiry"] = time.time() + SESSION_TIME; await u.message.reply_text("🔓 Unlocked!")

async def run_bot():
    init_db()
    # Start the dummy web server in a separate thread
    threading.Thread(target=run_health_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setpass", setpass))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    
    async with app:
        await app.initialize()
        await app.start()
        logger.info("Bot is running...")
        await app.updater.start_polling(drop_pending_updates=True)
        while True:
            await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except Exception as e:
        logger.error(f"Error: {e}")
