import os, time, sqlite3, logging, asyncio, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes

# --- Configuration ---
TOKEN = "8361917661:AAFk276iJeAOw9ucXCVPchBscSlEYmI1HS8" 
# Meeru (6809528328) mariyu mee friend IDs ikkada add cheyandi
ADMIN_IDS = [6809528328, 7156234567] 
DB_PATH = "prediction_bot.db"
QR_PATH = "admin_qr.jpg"

admin_sessions = {}  # Multiple admins ni track chestundi
admin_modes = {}
admin_pass = "09262005" # Default password
SESSION_TIME = 3600

logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# --- Health Check Server (For Render Free Tier) ---
def run_health_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(('0.0.0.0', port), type('H', (BaseHTTPRequestHandler,), {'do_GET': lambda s: (s.send_response(200), s.end_headers(), s.wfile.write(b"Bot Alive"))}))
    server.serve_forever()

# --- Database Setup ---
def db_query(query, params=(), fetch=False):
    conn = sqlite3.connect(DB_PATH); c = conn.cursor()
    c.execute(query, params); d = c.fetchall() if fetch else None
    conn.commit(); conn.close(); return d

def init_db():
    db_query("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, is_vip INTEGER DEFAULT 0)")

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
        [InlineKeyboardButton("💳 Change QR", callback_data='p_qr')],
        [InlineKeyboardButton("🔒 Logout", callback_data='p_logout')]
    ])

# --- Functions ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    db_query("INSERT OR IGNORE INTO users (id, is_vip) VALUES (?, 0)", (uid,))
    
    if uid in ADMIN_IDS:
        if time.time() > admin_sessions.get(uid, 0):
            await update.message.reply_text("🔒 Admin Mode Locked.\nUse: `/login 09262005` to unlock.")
        else:
            await update.message.reply_text("🛠 **ADMIN PANEL**", reply_markup=get_admin_keyboard())
    else:
        await update.message.reply_text("👋 Welcome to Olymp Trade Predictions!\nChoose an option below:", reply_markup=get_user_keyboard())

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query; uid = q.from_user.id; await q.answer()

    # User Button Actions
    if q.data == 'u_free':
        await q.message.reply_text("📊 **Latest Free Prediction:**\n(Please wait for Admin to post a new one)")
    
    elif q.data == 'u_vip':
        user = db_query("SELECT is_vip FROM users WHERE id = ?", (uid,), fetch=True)
        if user and user[0][0] == 1:
            await q.message.reply_text("💎 **VIP ZONE:**\n(Checking for latest VIP signals...)")
        else:
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("📊 Use Free", callback_data='u_free')],
                [InlineKeyboardButton("💳 Buy VIP", callback_data='u_get_vip')]
            ])
            await q.message.reply_text("❌ You are not a VIP user.\nPlease buy VIP or use free predictions.", reply_markup=kb)
            
    elif q.data == 'u_get_vip':
        if os.path.exists(QR_PATH):
            await context.bot.send_photo(chat_id=uid, photo=open(QR_PATH, 'rb'), caption="1. Scan & Pay\n2. Upload Screenshot here 📸")
        else:
            await q.message.reply_text("⚠️ Payment details not updated by admin yet.")

    # Admin Button Actions
    if uid in ADMIN_IDS and time.time() < admin_sessions.get(uid, 0):
        if q.data == 'p_free': admin_modes[uid] = "FREE"; await q.message.reply_text("📸 Send Photo/Message for Free Users.")
        elif q.data == 'p_vip': admin_modes[uid] = "VIP"; await q.message.reply_text("📸 Send Photo/Message for VIP Users.")
        elif q.data == 'p_qr': admin_modes[uid] = "SETQR"; await q.message.reply_text("📸 Send New QR Photo.")
        elif q.data == 'p_logout': admin_sessions[uid] = 0; await q.edit_message_text("Logged out successfully.")

    # Approval System
    if uid in ADMIN_IDS and q.data.startswith(("app_", "dec_")):
        act, target = q.data.split("_")
        if act == "app":
            db_query("UPDATE users SET is_vip = 1 WHERE id = ?", (int(target),))
            await context.bot.send_message(chat_id=target, text="🎊 **VIP ACCESS UNLOCKED!**\nYou can now use VIP Predictions.")
            await q.edit_message_caption("Approved ✅")
        else:
            await context.bot.send_message(chat_id=target, text="❌ Your payment screenshot was declined.")
            await q.edit_message_caption("Declined ❌")

async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    # Admin Upload Logic
    if uid in ADMIN_IDS and time.time() < admin_sessions.get(uid, 0):
        mode = admin_modes.get(uid)
        if mode == "SETQR":
            f = await context.bot.get_file(update.message.photo[-1].file_id)
            await f.download_to_drive(QR_PATH); await update.message.reply_text("✅ QR Code Updated.")
        elif mode in ["FREE", "VIP"]:
            is_vip_target = 1 if mode == "VIP" else 0
            rows = db_query("SELECT id FROM users WHERE is_vip = ?", (is_vip_target,), fetch=True)
            targets = [r[0] for r in rows] if rows else []
            for t in targets:
                try: await context.bot.copy_message(chat_id=t, from_chat_id=uid, message_id=update.message.message_id)
                except: pass
            await update.message.reply_text(f"📢 Broadcast to {mode} users done!")
        admin_modes[uid] = None
    else:
        # User Screenshot Upload
        kb = [[InlineKeyboardButton("Approve ✅", callback_data=f"app_{uid}"), InlineKeyboardButton("Decline ❌", callback_data=f"dec_{uid}")]]
        for admin in ADMIN_IDS:
            try: await context.bot.send_photo(chat_id=admin, photo=update.message.photo[-1].file_id, caption=f"New Payment from {uid}", reply_markup=InlineKeyboardMarkup(kb))
            except: pass
        await update.message.reply_text("⏳ Screenshot sent. Please wait for Admin approval.")

async def login(u, c):
    uid = u.effective_user.id
    if uid in ADMIN_IDS and c.args:
        global admin_pass
        if c.args[0] == admin_pass:
            admin_sessions[uid] = time.time() + SESSION_TIME
            await u.message.reply_text("🔓 Admin Access Granted!")
            await start(u, c)

async def setpass(u, c):
    if u.effective_user.id in ADMIN_IDS and c.args:
        global admin_pass; admin_pass = c.args[0]
        await u.message.reply_text(f"✅ New Password set: {admin_pass}")

async def run_bot():
    init_db(); threading.Thread(target=run_health_server, daemon=True).start()
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("setpass", setpass))
    app.add_handler(CommandHandler("login", login))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    async with app:
        await app.initialize(); await app.start()
        await app.updater.start_polling(drop_pending_updates=True)
        while True: await asyncio.sleep(10)

if __name__ == "__main__":
    asyncio.run(run_bot())
