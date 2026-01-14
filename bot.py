import os
import asyncio
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
import yt_dlp

# --- CONFIGURATION ---
API_ID = 11253846  
API_HASH = "8db4eb50f557faa9a5756e64fb74a51a"
BOT_TOKEN = "8381012379:AAEbWjkDUBHj9dHGxq-URPmjGdgVpXH7jlY"

# --- LOGGING ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Client("TeraboxBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- FAKE WEB SERVER (Keep Render Alive) ---
class HealthCheckHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is active")

def start_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthCheckHandler)
    server.serve_forever()

# --- HELPER: RESOLVE URL ---
# This is the secret sauce. It forces the link to resolve before yt-dlp touches it.
async def get_real_link(url):
    try:
        # Simple string replacement first
        if "1024tera" in url or "mirrobox" in url:
            url = url.replace("1024tera.com", "terabox.com").replace("mirrobox.com", "terabox.com")
        return url
    except Exception as e:
        logger.error(f"Link Resolve Error: {e}")
        return url

# --- DOWNLOADER ---
async def download_video(url, message):
    status_msg = await message.reply_text("⏳ **Processing...**\n(Connecting to Terabox servers)")
    
    # 1. Fix the link
    clean_url = await get_real_link(url)
    
    # 2. Configure yt-dlp with specific "Anti-Block" headers
    ydl_opts = {
        'outtmpl': 'downloads/%(id)s.%(ext)s',
        'format': 'best',
        'noplaylist': True,
        # Using Android User-Agent often works better than iPhone for Terabox
        'user_agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Mobile Safari/537.36',
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'quiet': True,
        # This forces IPv4 which is more stable on Render
        'source_address': '0.0.0.0',
    }

    try:
        loop = asyncio.get_event_loop()
        
        # Run download in background
        await status_msg.edit_text("⬇️ **Downloading...**\n(Please wait up to 2 mins)")
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = await loop.run_in_executor(None, lambda: ydl.extract_info(clean_url, download=True))
            if not info:
                raise Exception("No video found")
            file_path = ydl.prepare_filename(info)

        # 3. Upload
        await status_msg.edit_text("⬆️ **Uploading...**")
        
        await message.reply_video(
            video=file_path,
            caption=f"✅ **Downloaded!**\n🔗 {clean_url}",
            supports_streaming=True
        )
        
        # Cleanup
        os.remove(file_path)
        await status_msg.delete()

    except Exception as e:
        error = str(e)
        logger.error(f"Fail: {error}")
        if "Too Many Requests" in error or "403" in error:
            await status_msg.edit_text("❌ **Blocked by Terabox.**\nRender IP is temporarily banned. Try again later.")
        else:
            await status_msg.edit_text(f"❌ **Failed:** {error[:50]}...")

# --- COMMANDS ---
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text("👋 **Simple Terabox Bot**\nSend a link!")

@app.on_message(filters.text & filters.private & ~filters.me)
async def handle_msg(client, message):
    if "http" in message.text:
        await download_video(message.text, message)

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    
    # Start Web Server in background
    threading.Thread(target=start_server, daemon=True).start()
    
    print("Bot Starting...")
    app.run()
