import os
import time
from pyrogram import Client, filters
import yt_dlp

# --- 1. YOUR CREDENTIALS ---
API_ID = # bot.py - TeraBox Downloader Bot

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ChatAction
import asyncio
from aiohttp import web
import aiohttp
import re

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ.get('BOT_TOKEN')
CHANNEL_USERNAME = "@Velvetabots"
PORT = int(os.environ.get('PORT', 10000))

# TeraBox API endpoints (multiple for fallback)
TERABOX_APIS = [
    "https://terabox-dl.qtcloud.workers.dev/api/get-info",
    "https://teraboxdownloader.online/api/get-info",
    "https://api-terabox.hnn.workers.dev/api/get-info"
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome_text = """
🌟 **Welcome to Velveta TeraBox Downloader!**
🌟

Download files from TeraBox links! 🚀

**How to use:**
1️⃣ Send a TeraBox link 🔗
2️⃣ Wait for processing ⏳
3️⃣ Get your file! 📥

**Supported links:**
• terabox.com
• teraboxapp.com
• 1024terabox.com
• terabox.tech
• mirrobox.com
• nephobox.com
• 4funbox.com

**⚠️ Note:**
• Max file size: 2GB (Telegram limit)
• Large files take time
• Password-protected files not supported

💡 Just send the TeraBox link and I'll do the rest!
"""
    
    keyboard = [[InlineKeyboardButton("📢 Join Update Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

def is_terabox_link(url):
    """Check if URL is a TeraBox link"""
    terabox_domains = [
        'terabox.com',
        'teraboxapp.com',
        '1024terabox.com',
        'terabox.tech',
        'mirrobox.com',
        'nephobox.com',
        '4funbox.com'
    ]
    return any(domain in url.lower() for domain in terabox_domains)

async def get_terabox_info(url):
    """Get file info from TeraBox with fallback APIs"""
    for api_url in TERABOX_APIS:
        try:
            logger.info(f"Trying API: {api_url}")
            
            async with aiohttp.ClientSession() as session:
                data = {'url': url}
                
                async with session.post(api_url, json=data, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        
                        if result.get('ok') or result.get('success'):
                            logger.info(f"✅ API success: {api_url}")
                            return result
                        
        except Exception as e:
            logger.warning(f"API {api_url} failed: {e}")
            continue
    
    return None

async def download_file_with_progress(url, filename, download_msg, file_title):
    """Download file with progress bar"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=1800) as response:  # 30 min timeout
                if response.status != 200:
                    return False
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_update = 0
                
                with open(filename, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 512):  # 512KB chunks
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress every 5MB
                        if downloaded - last_update > 5 * 1024 * 1024:
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                mb_downloaded = downloaded / (1024 * 1024)
                                mb_total = total_size / (1024 * 1024)
                                
                                # Progress bar
                                bar_length = 20
                                filled = int(bar_length * percent / 100)
                                bar = '█' * filled + '░' * (bar_length - filled)
                                
                                progress_text = (
                                    f"⬇️ **Downloading from TeraBox...**\n\n"
                                    f"📁 {file_title[:40]}...\n\n"
                                    f"📊 Progress: {percent:.1f}%\n"
                                    f"{bar}\n"
                                    f"📥 {mb_downloaded:.1f}MB / {mb_total:.1f}MB"
                                )
                                
                                try:
                                    await download_msg.edit_text(progress_text, parse_mode='Markdown')
                                except:
                                    pass
                                
                                last_update = downloaded
                
                return True
                
    except asyncio.TimeoutError:
        logger.error("Download timeout")
        return False
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle TeraBox URL"""
    if not update.message or not update.message.text:
        return
    
    url = update.message.text.strip()
    
    if not is_terabox_link(url):
        await update.message.reply_text(
            "❌ Please send a valid TeraBox link!\n\n"
            "Supported: terabox.com, teraboxapp.com, 1024terabox.com, etc."
        )
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    processing_msg = await update.message.reply_text(
        "🔍 **Processing TeraBox link...**\n⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    try:
        # Get file info
        file_info = await get_terabox_info(url)
        
        if not file_info:
            await processing_msg.edit_text(
                "❌ **Could not process this link**\n\n"
                "**Possible reasons:**\n"
                "• Invalid link\n"
                "• Link expired\n"
                "• Password-protected file\n"
                "• Server is busy\n\n"
                "Please check the link and try again."
            )
            return
        
        # Extract file details
        response_data = file_info.get('response', [])
        if not response_data:
            await processing_msg.edit_text("❌ No file found at this link.")
            return
        
        file_data = response_data[0] if isinstance(response_data, list) else response_data
        
        file_name = file_data.get('filename', 'Unknown')
        file_size = file_data.get('size', 0)
        download_url = file_data.get('download_link') or file_data.get('direct_link')
        
        if not download_url:
            await processing_msg.edit_text("❌ Could not get download link. Link may be expired.")
            return
        
        # Check file size
        file_size_mb = file_size / (1024 * 1024) if file_size else 0
        
        if file_size > 2000 * 1024 * 1024:  # 2GB
            await processing_msg.edit_text(
                f"❌ **File too large!**\n\n"
                f"📁 {file_name}\n"
                f"📦 Size: {file_size_mb:.1f}MB\n\n"
                f"Telegram limit is 2GB (2048MB).\n"
                f"This file is larger than the limit."
            )
            return
        
        # Store data
        context.user_data['file_name'] = file_name
        context.user_data['file_size'] = file_size
        context.user_data['download_url'] = download_url
        
        # Show file info with download button
        keyboard = [[InlineKeyboardButton("📥 Download File", callback_data='download')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        info_text = (
            f"✅ **File Found!**\n\n"
            f"📁 **Name:** {file_name}\n"
            f"📦 **Size:** {file_size_mb:.1f}MB\n\n"
            f"Click the button below to download!"
        )
        
        await processing_msg.edit_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(
            "❌ **An error occurred**\n\n"
            "Please try again or check if the link is valid."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle download button"""
    query = update.callback_query
    await query.answer()
    
    file_name = context.user_data.get('file_name')
    file_size = context.user_data.get('file_size', 0)
    download_url = context.user_data.get('download_url')
    
    if not download_url:
        await query.message.reply_text("❌ Session expired. Please send the link again.")
        return
    
    download_msg = await query.message.reply_text(
        f"⬇️ **Starting download...**\n\n📁 {file_name[:40]}...\n\n⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    filename = None
    
    try:
        # Create downloads directory
        os.makedirs('downloads', exist_ok=True)
        
        # Clean filename
        safe_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.'))[:100]
        filename = f'downloads/{safe_name}'
        
        # Download file
        success = await download_file_with_progress(download_url, filename, download_msg, file_name)
        
        if not success or not os.path.exists(filename):
            await download_msg.edit_text(
                "❌ **Download failed**\n\n"
                "Possible reasons:\n"
                "• Connection timeout\n"
                "• Link expired\n"
                "• Server error\n\n"
                "Please try again."
            )
            return
        
        # Verify file size
        actual_size = os.path.getsize(filename)
        actual_size_mb = actual_size / (1024 * 1024)
        
        if actual_size < 1024:  # Less than 1KB
            await download_msg.edit_text("❌ Download failed - invalid file.")
            os.remove(filename)
            return
        
        # Upload to Telegram
        await download_msg.edit_text(
            f"⬆️ **Uploading to Telegram...**\n\n"
            f"📁 {file_name[:40]}...\n"
            f"📤 Size: {actual_size_mb:.1f}MB\n"
            f"⏳ This may take a while...",
            parse_mode='Markdown'
        )
        
        caption = f"✅ **Downloaded via @Velveta_YT_Downloader_bot**\n\n📁 {file_name}"
        
        # Detect file type and send accordingly
        file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        
        with open(filename, 'rb') as f:
            if file_ext in ['mp4', 'mkv', 'avi', 'mov']:
                sent_msg = await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    caption=caption,
                    parse_mode='Markdown',
                    supports_streaming=True,
                    read_timeout=600,
                    write_timeout=600
                )
            elif file_ext in ['mp3', 'm4a', 'wav', 'flac']:
                sent_msg = await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=f,
                    caption=caption,
                    parse_mode='Markdown',
                    read_timeout=600,
                    write_timeout=600
                )
            elif file_ext in ['jpg', 'jpeg', 'png', 'gif']:
                sent_msg = await context.bot.send_photo(
                    chat_id=query.message.chat_id,
                    photo=f,
                    caption=caption,
                    parse_mode='Markdown',
                    read_timeout=600,
                    write_timeout=600
                )
            else:
                sent_msg = await context.bot.send_document(
                    chat_id=query.message.chat_id,
                    document=f,
                    caption=caption,
                    parse_mode='Markdown',
                    read_timeout=600,
                    write_timeout=600
                )
        
        # Delete download progress message
        await download_msg.delete()
        
        # Send completion message with donation button
        keyboard = [[InlineKeyboardButton("☕ Donate / Support", url="https://t.me/Velvetabots")]]
        await context.bot.send_message(
            chat_id=query.message.chat_id,
            text="✅ **Download Complete!** 🎉\n\nEnjoy your file!",
            reply_to_message_id=sent_msg.message_id,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode='Markdown'
        )
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await download_msg.edit_text(
            f"❌ **Upload failed**\n\n"
            f"Error: {str(e)[:100]}\n\n"
            "The file may be too large or corrupted."
        )
        
    finally:
        # Clean up
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
                logger.info(f"Cleaned up: {filename}")
            except:
                pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}")

async def health_check(request):
    """Health check endpoint"""
    return web.Response(text="TeraBox Downloader Bot Running! 🚀")

async def start_web_server():
    """Start web server"""
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

async def start_bot():
    """Start bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # Start bot
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("TeraBox Downloader Bot Started! 🎉")
    
    while True:
        await asyncio.sleep(1)

async def main():
    """Main function"""
    await asyncio.gather(start_web_server(), start_bot())

if __name__ == '__main__':
    asyncio.run(main())11253846  
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
