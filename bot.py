import os
import time
from pyrogram import Client, filters
import yt_dlp

# --- 1. YOUR CREDENTIALS ---
API_ID = 11253846  
API_HASH = "8db4eb50f557faa9a5756e64fb74a51a"
BOT_TOKEN = "8381012379:AAEbWjkDUBHj9dHGxq-URPmjGdgVpXH7jlY"

app = Client("LocalTeraboxBot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 2. HELPER: FIX LINKS ---
def fix_link(url):
    # Fix common redirect domains
    if "1024tera" in url: url = url.replace("1024tera.com", "terabox.com")
    if "mirrobox" in url: url = url.replace("mirrobox.com", "terabox.com")
    if "teraboxapp" in url: url = url.replace("teraboxapp.com", "terabox.com")
    return url

# --- 3. DOWNLOADER LOGIC ---
def download_video(url, message):
    message.reply_text("⏳ **Stealing Login from Chrome...**\n(Make sure Chrome is CLOSED!)")
    
    clean_url = fix_link(url)
    
    ydl_opts = {
        'outtmpl': 'downloads/%(title)s.%(ext)s',
        'format': 'best',
        'noplaylist': True,
        
        # 🔥 THE SUPER POWER 🔥
        # This tells Python to open your Chrome data and take the login directly.
        'cookiesfrombrowser': ('chrome',), 
        
        'nocheckcertificate': True,
        'ignoreerrors': True,
        'quiet': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=True)
            if not info:
                message.reply_text("❌ **Failed.** Could not find video.")
                return
            
            file_path = ydl.prepare_filename(info)

        message.reply_text("⬆️ **Uploading...**")
        app.send_video(
            chat_id=message.chat.id,
            video=file_path,
            caption=f"✅ **Downloaded!**\n🔗 {clean_url}"
        )
        
        os.remove(file_path)

    except Exception as e:
        error = str(e)
        if "open" in error.lower() or "lock" in error.lower():
            message.reply_text("❌ **Error: Chrome is Open!**\nPlease close Google Chrome completely and try again.")
        elif "cookie" in error.lower():
             message.reply_text("❌ **Cookie Error.**\nMake sure you are logged into Terabox on Chrome.")
        else:
            message.reply_text(f"❌ **Error:** {error}")

# --- 4. BOT COMMANDS ---
@app.on_message(filters.command("start"))
def start(client, message):
    message.reply_text("💻 **Auto-Login Bot Ready!**\n1. Close Chrome.\n2. Send Link.")

@app.on_message(filters.text & filters.private & ~filters.me)
def handle_msg(client, message):
    if "http" in message.text:
        download_video(message.text, message)

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    print("✅ Bot is running...")
    app.run()
