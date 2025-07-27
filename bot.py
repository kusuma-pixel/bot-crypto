import requests
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import datetime
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, ContextTypes, filters
from io import BytesIO
import logging

# Aktifkan logging
logging.basicConfig(level=logging.INFO)

# ===== KONFIGURASI =====
TOKEN = "8008159425:AAGRTlaTMQI6vfYPlgjzH6Dlq2PMcuUgdW8"

# ===== DAFTAR KOIN =====
COINS = {
    "btc": {"id": "bitcoin", "symbol": "BTCUSDT", "indodax": "btc_idr", "color": "#F7931A"},
    "eth": {"id": "ethereum", "symbol": "ETHUSDT", "indodax": "eth_idr", "color": "#627EEA"},
    "bnb": {"id": "binancecoin", "symbol": "BNBUSDT", "indodax": "bnb_idr", "color": "#F3BA2F"},
    "xrp": {"id": "ripple", "symbol": "XRPUSDT", "indodax": "xrp_idr", "color": "#27A2DB"}
}

# ===== KEYBOARD MENU =====
def get_coin_menu_keyboard():
    keyboard = [
        ["📊 BTC", "📊 ETH"],
        ["📊 BNB", "📊 XRP"],
        ["🔄 Refresh All", "❌ Close Menu"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ===== HANDLER /start =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_msg = """
💰 *Crypto Price Bot* 💰

Pilih coin dari menu keyboard di bawah untuk melihat:
- Harga terkini (USD & IDR)
- Grafik candlestick 7 hari
- Analisis market

🔎 Data dari Binance, CoinGecko, dan Indodax
"""
    await update.message.reply_text(welcome_msg, reply_markup=get_coin_menu_keyboard(), parse_mode='Markdown')

# ===== CLOSE MENU =====
async def close_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("✅ Menu ditutup. Ketik /start untuk membuka kembali.", reply_markup=ReplyKeyboardRemove())

# ===== AMBIL DATA HARGA =====
def get_price_data(coin_code):
    coin_data = COINS[coin_code]
    result = {"coin": coin_code.upper()}

    # Harga dari Binance (USD)
    try:
        binance_url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={coin_data['symbol']}"
        binance_data = requests.get(binance_url, timeout=5).json()
        result.update({
            "price_usd": float(binance_data['lastPrice']),
            "change_usd": float(binance_data['priceChangePercent']),
            "high_usd": float(binance_data['highPrice']),
            "low_usd": float(binance_data['lowPrice']),
            "volume_usd": float(binance_data['volume'])
        })
    except Exception as e:
        logging.warning(f"Binance error: {e}")
        # fallback CoinGecko
        cg_url = f"https://api.coingecko.com/api/v3/coins/{coin_data['id']}"
        cg_data = requests.get(cg_url, timeout=5).json()
        result.update({
            "price_usd": cg_data['market_data']['current_price']['usd'],
            "change_usd": cg_data['market_data']['price_change_percentage_24h'],
            "high_usd": cg_data['market_data']['high_24h']['usd'],
            "low_usd": cg_data['market_data']['low_24h']['usd'],
            "volume_usd": cg_data['market_data']['total_volume']['usd']
        })

    # Harga dari Indodax (IDR)
    try:
        indodax_url = f"https://indodax.com/api/ticker/{coin_data['indodax']}"
        indodax_data = requests.get(indodax_url, timeout=5).json()['ticker']
        result.update({
            "price_idr": float(indodax_data['last']),
            "high_idr": float(indodax_data['high']),
            "low_idr": float(indodax_data['low']),
            "volume_idr": float(indodax_data['vol_idr'])
        })
    except:
        # fallback IDR dari USD
        kurs = 16000
        result.update({
            "price_idr": result['price_usd'] * kurs,
            "high_idr": result['high_usd'] * kurs,
            "low_idr": result['low_usd'] * kurs,
            "volume_idr": result['volume_usd'] * kurs
        })

    return result

# ===== CHART CANDLESTICK 7 HARI =====
def create_indodax_style_chart(coin_code, days=7):
    coin_data = COINS[coin_code]
    try:
        now = datetime.datetime.now()
        from_ts = int((now - datetime.timedelta(days=days)).timestamp())
        to_ts = int(now.timestamp())

        indodax_url = f"https://indodax.com/api/tradingview/history?symbol={coin_data['indodax']}&resolution=D&from={from_ts}&to={to_ts}"
        data = requests.get(indodax_url, timeout=5).json()

        dates = [datetime.datetime.fromtimestamp(t) for t in data['t']]
        opens = data['o']
        highs = data['h']
        lows = data['l']
        closes = data['c']

        # Plot candlestick chart
        fig, ax = plt.subplots(figsize=(10, 5), facecolor='#1e1e2e')
        ax.set_facecolor('#1e1e2e')

        for i in range(len(dates)):
            color = '#2ecc71' if closes[i] >= opens[i] else '#e74c3c'
            # Wick
            ax.plot([dates[i], dates[i]], [lows[i], highs[i]], color=color, linewidth=1)
            # Body
            rect_height = closes[i] - opens[i]
            rect_y = opens[i] if rect_height >= 0 else closes[i]
            ax.add_patch(plt.Rectangle(
                (dates[i] - datetime.timedelta(hours=6), rect_y),
                datetime.timedelta(hours=12),
                abs(rect_height),
                color=color
            ))

        ax.set_title(f"{coin_code.upper()}/IDR Price Chart ({days} Days)", color='white')
        ax.set_xlabel("Date", color='gray')
        ax.set_ylabel("Price (IDR)", color='gray')
        ax.tick_params(colors='gray')
        ax.grid(color='gray', linestyle='--', alpha=0.3)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%d %b'))
        ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))

        plt.tight_layout()
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=120, bbox_inches='tight', facecolor=fig.get_facecolor())
        buf.seek(0)
        plt.close()
        return buf

    except Exception as e:
        logging.warning(f"Gagal buat chart: {e}")
        return None

# ===== TAMPILKAN DATA KOIN =====
async def show_coin_info(update: Update, coin_code):
    try:
        data = get_price_data(coin_code)
        chart = create_indodax_style_chart(coin_code)

        msg = f"""
📈 *{data['coin']} Price Info*

💵 *USD:*
├ Price: ${data['price_usd']:,.2f}
├ Change 24h: {data['change_usd']:+.2f}%
├ High: ${data['high_usd']:,.2f}
└ Low: ${data['low_usd']:,.2f}

💰 *IDR:*
├ Price: Rp {data['price_idr']:,.0f}
├ High: Rp {data['high_idr']:,.0f}
└ Low: Rp {data['low_idr']:,.0f}

📊 Volume 24h: Rp {data['volume_idr']:,.0f}
"""

        if chart:
            await update.message.reply_photo(chart, caption=msg, parse_mode='Markdown', reply_markup=get_coin_menu_keyboard())
        else:
            await update.message.reply_text(msg, parse_mode='Markdown', reply_markup=get_coin_menu_keyboard())

    except Exception as e:
        logging.exception("Gagal tampilkan info")
        await update.message.reply_text("⚠️ Gagal mengambil data. Coba lagi.", reply_markup=get_coin_menu_keyboard())

# ===== REFRESH SEMUA =====
async def refresh_all_prices(update: Update):
    for coin in COINS:
        await show_coin_info(update, coin)

# ===== HANDLE PESAN USER =====
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.lower()
    if "btc" in text:
        await show_coin_info(update, "btc")
    elif "eth" in text:
        await show_coin_info(update, "eth")
    elif "bnb" in text:
        await show_coin_info(update, "bnb")
    elif "xrp" in text:
        await show_coin_info(update, "xrp")
    elif "refresh" in text:
        await refresh_all_prices(update)
    elif "close" in text:
        await close_menu(update, context)
    else:
        await update.message.reply_text("🔎 Silakan pilih coin dari menu atau ketik /start", reply_markup=get_coin_menu_keyboard())

# ===== MAIN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🚀 Bot berjalan...")
    app.run_polling()

if __name__ == "__main__":
    main()
