import logging
from datetime import datetime, timedelta
import pytz
import os
import threading
import asyncio

from flask import Flask
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Bot
)
from telegram.ext import (
    ApplicationBuilder,
    Defaults,
    ContextTypes,
    CommandHandler,
    CallbackQueryHandler,
    ConversationHandler,
    MessageHandler,
    filters
)

# Reduce logging to errors only
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.ERROR
)

app = Flask(__name__)

@app.route("/")
def index():
    return "Bot is running!"

# States
SELECT_PAIR, SELECT_TIME, SELECT_DIRECTION, CONFIRM = range(4)

PAIRS = [
    "USD/ARS-OTC", "USD/INR-OTC", "USD/MXN-OTC",
    "USD/TRY-OTC", "USD/BRL-OTC", "USD/BDT-OTC",
    "USD/PKR-OTC", "USD/PHP-OTC", "USD/IDR-OTC",
    "USD/COP-OTC", "USD/NGN-OTC", "USD/EGP-OTC",
    "USD/DZD-OTC", "USD/ZAR-OTC", "EUR/USD-OTC",
    "EUR/GBP-OTC", "NZD/CHF-OTC", "NZD/CAD-OTC",
    "NZD/JPY-OTC", "NZD/USD-OTC", "AUD/NZD-OTC",
    "EUR/NZD-OTC", "CAD/CHF-OTC", "CAD/JPY-OTC"
]

def chunk_list(lst, n):
    for i in range(0, len(lst), n):
        yield lst[i:i+n]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = []
    for group in chunk_list(PAIRS, 2):
        kb.append([InlineKeyboardButton(pair, callback_data=pair) for pair in group])
    await update.message.reply_text(
        "<b>Select A Currency Pair For The Signal:</b>",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return SELECT_PAIR

async def pair_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["pair"] = query.data

    now_sp = datetime.now(pytz.timezone("America/Sao_Paulo")) + timedelta(minutes=1)
    times = [(now_sp + timedelta(minutes=i)).strftime("%H:%M") for i in range(5)]
    kb = [[InlineKeyboardButton(t, callback_data=t)] for t in times]

    await query.edit_message_text(
        f"<b>You selected</b>: {query.data}\n"
        "<b>Now choose the time for the signal (Brazil - UTC-03:00):</b>",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return SELECT_TIME

async def time_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data["time"] = query.data

    kb = [[
        InlineKeyboardButton("⬆️ UP 🟢", callback_data="UP"),
        InlineKeyboardButton("⬇️ DOWN 🔴", callback_data="DOWN")
    ]]

    await query.edit_message_text(
        f"<b>Pair</b>: {context.user_data['pair']}\n"
        f"<b>Time</b>: {query.data}\n\n"
        "<b>Choose the direction:</b>",
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return SELECT_DIRECTION

async def direction_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    direction = query.data
    pair = context.user_data["pair"]
    sig_time = context.user_data["time"]
    arrow_emoji = "⬆️ UP 🟢" if direction == "UP" else "⬇️ DOWN 🔴"

    final_text = (
        f"<b>📊 {pair}</b>\n"
        f"<b>⌛ M1 1-MINUTE [ UTC-03:00 ]</b>\n"
        f"<b>⏰ {sig_time}</b>\n"
        f"<b>{arrow_emoji}</b>\n"
        f"<b>📍 NON-MTG</b>\n"
        f"<b>🧔🏻 @QuotexHubSupport</b>"
    )
    context.user_data["signal_text"] = final_text

    kb = [[InlineKeyboardButton("Send to Channel", callback_data="SEND_TO_CHANNEL")]]
    await query.edit_message_text(
        final_text,
        reply_markup=InlineKeyboardMarkup(kb)
    )
    return CONFIRM

async def send_to_channel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    bot: Bot = context.bot
    msg_text = context.user_data["signal_text"]
    link_btn = InlineKeyboardButton(
        "📊 Quotex Registration ",
        url="https://broker-qx.pro/sign-up/?lid=1179650"
    )
    reply_markup = InlineKeyboardMarkup([[link_btn]])
    CHANNEL_ID = -1002291654577  # Update to your channel ID

    await bot.send_message(
        chat_id=CHANNEL_ID,
        text=msg_text,
        reply_markup=reply_markup
    )
    await query.edit_message_text("<b>Signal successfully sent to the channel!</b>")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Cancelled.")
    return ConversationHandler.END

def run_bot():
    """Run the Telegram bot polling in its own thread with a new event loop."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = (
        ApplicationBuilder()
        .token("7579719782:AAFBzWFrvTou9r8EbT93YwyIzirHpOf9YeY")
        .defaults(Defaults(parse_mode="HTML"))
        # If you want the new recommended timeouts:
        # .get_updates_read_timeout(5)
        # .get_updates_write_timeout(5)
        .build()
    )

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            SELECT_PAIR: [CallbackQueryHandler(pair_callback)],
            SELECT_TIME: [CallbackQueryHandler(time_callback)],
            SELECT_DIRECTION: [CallbackQueryHandler(direction_callback)],
            CONFIRM: [CallbackQueryHandler(send_to_channel_callback, pattern="^SEND_TO_CHANNEL$")]
        },
        fallbacks=[MessageHandler(filters.TEXT | filters.COMMAND, cancel)],
        # per_message=True  # If needed
    )
    application.add_handler(conv_handler)

    application.run_polling(
        drop_pending_updates=True
    )

if __name__ == "__main__":
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
