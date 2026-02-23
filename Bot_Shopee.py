import json
import os
from datetime import datetime
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto, Update
from telegram.error import BadRequest
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
from psycopg2.extras import RealDictCursor

TOKEN = os.environ.get("TELEGRAM_TOKEN")  # simpan token bot di Railway secret
ADMIN_USERNAME = "szavvvv"
DATABASE_URL = os.environ.get("DATABASE_URL")

# ===== LOAD DATA =====
with open("data.json", "r", encoding="utf-8") as f:
    config = json.load(f)

# ===== DATABASE LOG =====
def log_activity(user, action):
    conn = psycopg2.connect(DATABASE_URL)
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO logs (user_id, username, first_name, action, timestamp)
        VALUES (%s, %s, %s, %s, %s)
    """, (user.id, user.username, user.first_name, action, datetime.now()))
    conn.commit()
    cur.close()
    conn.close()

def get_logs(limit=50):
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()
    cur.execute("SELECT * FROM logs ORDER BY timestamp DESC LIMIT %s", (limit,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

# ===== SHOW CATALOG =====
async def show_catalog(update_or_query, edit=False):
    keyboard = [[InlineKeyboardButton(p["name"], callback_data=f"product_{p['id']}")] for p in config["products"]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if edit:
        try:
            with open(config["banner"], "rb") as photo:
                media = InputMediaPhoto(media=photo, caption=config["welcome_text"])
                await update_or_query.message.edit_media(media=media, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise
    else:
        with open(config["banner"], "rb") as photo:
            await update_or_query.message.reply_photo(photo=photo, caption=config["welcome_text"], reply_markup=reply_markup)

# ===== HANDLER =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_activity(update.effective_user, "start")
    await show_catalog(update)

async def auto_pricelist(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    if not message or not message.text or message.from_user.is_bot:
        return
    if "pricelist" in message.text.lower():
        await show_catalog(update)

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    user = query.from_user

    if data.startswith("product_"):
        product_id = data.split("_")[1]
        product = next((p for p in config["products"] if p["id"] == product_id), None)
        if not product: return
        caption = f"🛍 {product['name']}\n\n{product['description']}\n\n💰 Harga: {product['price']}"
        keyboard = [
            [InlineKeyboardButton("🛒 Beli di Shopee", callback_data=f"buy_{product_id}")],
            [InlineKeyboardButton("💬 Tanya via Telegram", url=f"https://t.me/{ADMIN_USERNAME}?text=Halo saya tertarik dengan {product['name']}")],
            [InlineKeyboardButton("⬅️ Kembali", callback_data="back")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        try:
            with open(product["photo"], "rb") as photo:
                media = InputMediaPhoto(media=photo, caption=caption)
                await query.message.edit_media(media=media, reply_markup=reply_markup)
        except BadRequest as e:
            if "Message is not modified" not in str(e):
                raise

    elif data.startswith("buy_"):
        product_id = data.split("_")[1]
        log_activity(user, f"klik_beli_{product_id}")
        product = next((p for p in config["products"] if p["id"] == product_id), None)
        if product:
            await query.message.reply_text(product["link"])

    elif data == "back":
        await show_catalog(query, edit=True)

async def show_logs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logs = get_logs(20)
    if not logs:
        await update.message.reply_text("Belum ada log.")
        return
    msg = "\n".join([f"{l['timestamp']} | {l['first_name']} (@{l['username']}) | {l['action']}" for l in logs])
    await update.message.reply_text(msg)

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.TEXT & (~filters.COMMAND), auto_pricelist))
    app.add_handler(CommandHandler("logs", show_logs))
    print("Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":

    main()
