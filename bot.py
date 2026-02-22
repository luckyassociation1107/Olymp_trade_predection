import os, time, sqlite3, logging, asyncio, threading
from datetime import datetime
import pytz
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- Configuration ---
TOKEN = "8361917661:AAFk276iJeAOw9ucXCVPchBscSlEYmI1HS8" 
ADMIN_IDS = [6809528328] 
DB_PATH = "olymp_prediction_bot.db"
QR_PATH = "olymp_admin_qr.jpg"

admin_sessions = {} 
admin_modes = {}
admin_pass = "09262005"
SESSION_TIME = 3600
IST = pytz.timezone('Asia/Kolkata')

current_predictions = {"FREE": None, "VIP": None} 
payment_info = {"upi": "Not Set"}

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Health Check Server (Fixed for Render HEAD request) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(b"Bot is Online!")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), HealthCheckHandler)
    logger.info(f"Health check server started on port {port}")
    server.serve_forever()

# --- Database ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(query, params); d = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return d

def init_db():
    db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0)")
    db_query("CREATE TABLE IF NOT EXISTS posts (msg_id INTEGER, chat_id INTEGER, date TEXT)")

# --- Auto-Delete Task (Fixed context issue) ---
async def auto_delete_scheduler(app: Application):
    while True:
        try:
            now = datetime.now(IST)
            today_str = now.strftime("%Y-%m-%d")
            
            if now.hour == 0 and now.minute == 0:
                current_predictions["FREE"] = None
                current_predictions["VIP"] = None
            
            old_posts = db_query("SELECT msg_id, chat_id FROM posts WHERE date != ?", (today_str,), fetch=True)
            for msg_id, chat_id in old_posts:
                try: await app.bot.delete_message(chat_id=chat_id, message_id=msg_id)
                except: pass
            db_query("DELETE FROM posts WHERE date != ?", (today_str,))
        except Exception as e:
            logger.error(f"Error in scheduler: {e}")
            
        await asyncio.sleep(60)

# --- Keyboards ---
def get_user_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📊 Free Predictions", callback_data='u_free')],
        [InlineKeyboardButton("💎 VIP Predictions", callback_data='u_vip')],
        [InlineKeyboardButton("💳 Get VIP Access", callback_data='u_get_vip')]
    ])

def get_admin_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("📤 Post Free", callback_data='p_free'), InlineKeyboardButton("📤 Post VIP", callback_data='p_vip')],
        [InlineKeyboardButton("💳 Change QR", callback_data='p_qr'), InlineKeyboardButton("🆔 Set UPI", callback_data='p_upi')],
        [InlineKeyboardButton("🔒 Logout", callback_data='p_logout')]
    ])

# --- Handlers ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db_query("INSERT OR IGNORE INTO users (id, is_vip) VALUES (?, 0)", (uid,))
    await context.bot.set_my_commands([BotCommand("start", "🚀 Open Main Menu")])

    if uid in ADMIN_IDS:
        if time.time() > admin_sessions.get(uid, 0):
            await update.message.reply_text(f"🔒 Admin Mode Locked.\nLogin: `/login {admin_pass}`")
        else:
            await update.message.reply_text("🛠 **ADMIN PANEL**", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("👋 Welcome to Olymp Trade Predictions!", reply_markup=get_user_keyboard())
        
        user_data = db_query("SELECT is_vip FROM users WHERE id = ?", (uid,), fetch=True)
        is_vip = user_data[0][0] if user_data else 0
        p_type = "VIP" if is_vip else "FREE"
        if current_predictions[p_type]:
            await update.message.reply_text(f"📢 Active {p_type} prediction for today:")
            sent = await context.bot.copy_message(chat_id=uid, from_chat_id=ADMIN_IDS[0], message_id=current_predictions[p_type])
            db_query("INSERT INTO posts (msg_id, chat_id, date) VALUES (?, ?, ?)", (sent.message_id, uid, datetime.now(IST).strftime("%Y-%m-%d")))

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id; await q.answer()

    if q.data == 'u_free':
        if current_predictions["FREE"]:
            await context.bot.copy_message(chat_id=uid, from_chat_id=ADMIN_IDS[0], message_id=current_predictions["FREE"])
        else: await q.message.reply_text("📊 No Free predictions yet.")
    
    elif q.data == 'u_vip':
        user = db_query("SELECT is_vip FROM users WHERE id = ?", (uid,), fetch=True)
        if user and user[0][0] == 1:
            if current_predictions["VIP"]:
                await context.bot.copy_message(chat_id=uid, from_chat_id=ADMIN_IDS[0], message_id=current_predictions["VIP"])
            else: await q.message.reply_text("💎 No VIP signals yet.")
        else:
            await q.message.reply_text("❌ Not a VIP user.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("💳 Buy VIP", callback_data='u_get_vip')]]))
            
    elif q.data == 'u_get_vip':
        caption = f"💎 **VIP LIFETIME ACCESS**\n\n🆔 UPI ID: `{payment_info['upi']}`\n\nScan QR and send screenshot 📸"
        if os.path.exists(QR_PATH):
            await context.bot.send_photo(chat_id=uid, photo=open(QR_PATH, 'rb'), caption=caption, parse_mode='Markdown')
        else: await q.message.reply_text(caption, parse_mode='Markdown')

    if uid in ADMIN_IDS and time.time() < admin_sessions.get(uid, 0):
        if q.data == 'p_free': admin_modes[uid] = "FREE"; await q.message.reply_text("📸 Send Free Prediction Photo.")
        elif q.data == 'p_vip': admin_modes[uid] = "VIP"; await q.message.reply_text("📸 Send VIP Prediction Photo.")
        elif q.data == 'p_qr': admin_modes[uid] = "SETQR"; await q.message.reply_text("📸 Send New QR Photo.")
        elif q.data == 'p_upi': admin_modes[uid] = "SETUPI"; await q.message.reply_text("⌨️ Type and send new UPI ID.")
        elif q.data == 'p_logout': admin_sessions[uid] = 0; await q.edit_message_text("Logged out.")

    if uid in ADMIN_IDS and q.data.startswith(("app_", "dec_")):
        act, target = q.data.split("_")
        if act == "app":
            db_query("UPDATE users SET is_vip = 1 WHERE id = ?", (int(target),))
            await context.bot.send_message(chat_id=target, text="🎊 VIP UNLOCKED!")
            await q.edit_message_caption("Approved ✅")
        else: await q.edit_message_caption("Declined ❌")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    text = update.message.text
    photo = update.message.photo

    if uid in ADMIN_IDS and time.time() < admin_sessions.get(uid, 0):
        mode = admin_modes.get(uid)
        if mode == "SETUPI" and text:
            payment_info["upi"] = text
            await update.message.reply_text(f"✅ UPI updated: {text}")
            admin_modes[uid] = None
            return
        if photo:
            today_str = datetime.now(IST).strftime("%Y-%m-%d")
            if mode == "SETQR":
                f = await context.bot.get_file(photo[-1].file_id)
                await f.download_to_drive(QR_PATH); await update.message.reply_text("✅ QR Updated.")
            elif mode in ["FREE", "VIP"]:
                current_predictions[mode] = update.message.message_id
                is_vip = 1 if mode == "VIP" else 0
                targets = [r[0] for r in db_query("SELECT id FROM users WHERE is_vip = ?", (is_vip,), fetch=True)]
                for t in targets:
                    try:
                        sent = await context.bot.copy_message(chat_id=t, from_chat_id=uid, message_id=update.message.message_id)
                        db_query("INSERT INTO posts (msg_id, chat_id, date) VALUES (?, ?, ?)", (sent.message_id, t, today_str))
                    except: pass
                await update.message.reply_text(f"📢 Posted to {mode} users.")
            admin_modes[uid] = None
    elif photo:
        kb = [[InlineKeyboardButton("Approve ✅", callback_data=f"app_{uid}"), InlineKeyboardButton("Decline ❌", callback_data=f"dec_{uid}")]]
        for admin in ADMIN_IDS:
            try: await context.bot.send_photo(chat_id=admin, photo=photo[-1].file_id, caption=f"Payment from {uid}", reply_markup=InlineKeyboardMarkup(kb))
            except: pass
        await update.message.reply_text("⏳ Screenshot sent for approval.")

async def login(u, c):
    uid = u.effective_user.id
    if uid in ADMIN_IDS and c.args and c.args[0] == admin_pass:
        admin_sessions[uid] = time.time() + SESSION_TIME
        await u.message.reply_text("🔓 Admin Mode Unlocked!"); await start(u, c)

async def run_bot():
    init_db()
    threading.Thread(target=run_health_server, daemon=True).start()
    
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO | filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Corrected Background Task & App Lifecycle
    await app.initialize()
    await app.start()
    asyncio.create_task(auto_delete_scheduler(app)) # Fixed context issue here
    
    logger.info("Bot started successfully.")
    await app.updater.start_polling(drop_pending_updates=True)
    
    # Keep the application running
    while True:
        await asyncio.sleep(10)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except (KeyboardInterrupt, SystemExit):
        pass
