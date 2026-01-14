import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram import Client, filters
import yt_dlp

# --- CONFIGURATION ---
API_ID = 11253846  
API_HASH = "8db4eb50f557faa9a5756e64fb74a51a"
BOT_TOKEN = "8381012379:AAEbWjkDUBHj9dHGxq-URPmjGdgVpXH7jlY"

# 👇 YOUR KEYS ARE HERE 👇
NDUS_VALUE = "YeshlupteHuisY4ov9_FHr9xLm8rsHTXWztbUhOm"
BROWSERID_VALUE = "WD8gCNQTZ0lOOngyKqUoG8F18mrmzmI7cHqZ8ePWegSZkgTfe5oBJTJf9P8="

# Combine them into one strong cookie
FULL_COOKIE = f"ndus={NDUS_VALUE}; browserid={BROWSERID_VALUE}; lang=en;"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("TeraboxBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- FAKE WEB SERVER ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.wfile.write(b"Bot is active")

def start_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# --- HELPER: RESOLVE URL ---
async def get_real_link(url):
    if "1024tera" in url: url = url.replace("1024tera.com", "terabox.com")
    if "mirrobox" in url: url = url.replace("mirrobox.com", "terabox.com")
    return url

# --- DOWNLOADER ---
async def download_video(url, message):
    status_msg = await message.reply_text("⏳ **Verifying Login...**")
    
    clean_url = await get_real_link(url)
    
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'format': 'best',
        'noplaylist': True,
        # Mimic Windows Chrome
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'quiet': True,
        'source_address': '0.0.0.0',
        'http_headers': {
            'Cookie': FULL_COOKIE,
            'Referer': 'https://www.terabox.com/'
        }
    }

    try:
        loop = asyncio.get_event_loop()
        await status_msg.edit_text("⬇️ **Downloading...**\n(Double-Key Auth Active 🔐)")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(clean_url, download=True))
            if not info: raise Exception("Login Refused")
            file_path = ydl.prepare_filename(info)

        await status_msg.edit_text("⬆️ **Uploading...**")
        await message.reply_video(video=file_path, caption=f"✅ **Done!**\n🔗 {clean_url}")
        
        os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        error = str(e)
        if "Login" in error or "No video" in error:
             await status_msg.edit_text("❌ **Login Failed.**\nRender IP might be banned, or cookies expired.")
        else:
             await status_msg.edit_text(f"❌ **Error:** {error[:50]}...")

@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 **Bot Ready!**\nSend a link.")

@app.on_message(filters.text & filters.private & ~filters.me)
async def handle_msg(client, message):
    if "http" in message.text:
        await download_video(message.text, message)

if __name__ == "__main__":
    if not os.path.exists("downloads"): os.makedirs("downloads")
    threading.Thread(target=start_server, daemon=True).start()
    app.run()
