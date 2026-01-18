# bot.py - Google Drive Downloader Bot (API-Free Method)

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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send welcome message"""
    welcome_text = """
🌟 **Welcome to Velveta Google Drive Downloader!**
🌟

Download files from Google Drive links! 🚀

**How to use:**
1️⃣ Send a Google Drive link 🔗
2️⃣ Wait for processing ⏳
3️⃣ Click Download button 📥
4️⃣ Get your file! ✅

**Supported link formats:**
• drive.google.com/file/d/xxx
• drive.google.com/open?id=xxx

**Features:**
✅ All public files
✅ Up to 2GB
✅ Fast & reliable
✅ Progress tracking
✅ All file types

**⚠️ Requirements:**
• File must be public or "Anyone with link"
• File size under 2GB

💡 Just paste your Google Drive link!
"""
    
    keyboard = [[InlineKeyboardButton("📢 Join Update Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

def extract_file_id(url):
    """Extract Google Drive file ID"""
    patterns = [
        r'/file/d/([a-zA-Z0-9_-]+)',
        r'id=([a-zA-Z0-9_-]+)',
        r'/d/([a-zA-Z0-9_-]+)',
        r'open\?id=([a-zA-Z0-9_-]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

def is_gdrive_link(url):
    """Check if URL is Google Drive"""
    return 'drive.google.com' in url.lower() or 'docs.google.com' in url.lower()

async def get_file_info_from_page(file_id):
    """Get file info by scraping the page"""
    try:
        url = f"https://drive.google.com/file/d/{file_id}/view"
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            }
            
            async with session.get(url, headers=headers, timeout=30) as response:
                if response.status != 200:
                    return None
                
                html = await response.text()
                
                # Extract file name
                file_name = 'Unknown'
                name_match = re.search(r'"title":"([^"]+)"', html)
                if name_match:
                    file_name = name_match.group(1)
                
                # Extract file size
                file_size = 0
                size_match = re.search(r'"sizeBytes":"(\d+)"', html)
                if size_match:
                    file_size = int(size_match.group(1))
                
                # Check if file is accessible
                if 'Sorry, you can\'t view or download this file at this time' in html:
                    return {'error': 'quota_exceeded'}
                
                if 'This file is in the owner\'s trash' in html:
                    return {'error': 'in_trash'}
                
                return {
                    'name': file_name,
                    'size': file_size,
                    'id': file_id
                }
                
    except Exception as e:
        logger.error(f"Error scraping page: {e}")
        return None

def get_download_link(file_id):
    """Get direct download link"""
    return f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"

async def download_file_with_progress(file_id, filename, download_msg, file_title):
    """Download file with progress"""
    try:
        download_url = get_download_link(file_id)
        
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with session.get(download_url, headers=headers, allow_redirects=True, timeout=1800) as response:
                if response.status != 200:
                    # Try alternate URL
                    alternate_url = f"https://drive.google.com/uc?export=download&id={file_id}"
                    async with session.get(alternate_url, headers=headers, allow_redirects=True, timeout=1800) as alt_response:
                        if alt_response.status != 200:
                            return False
                        response = alt_response
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_update = 0
                
                with open(filename, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 512):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if downloaded - last_update > 3 * 1024 * 1024:
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                mb_downloaded = downloaded / (1024 * 1024)
                                mb_total = total_size / (1024 * 1024)
                                
                                bar_length = 20
                                filled = int(bar_length * percent / 100)
                                bar = '█' * filled + '░' * (bar_length - filled)
                                
                                progress_text = (
                                    f"⬇️ **Downloading from Google Drive...**\n\n"
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
                
    except Exception as e:
        logger.error(f"Download error: {e}")
        return False

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle Google Drive URL"""
    if not update.message or not update.message.text:
        return
    
    url = update.message.text.strip()
    
    if not is_gdrive_link(url):
        await update.message.reply_text(
            "❌ Please send a valid Google Drive link!\n\n"
            "Examples:\n"
            "• https://drive.google.com/file/d/xxx/view\n"
            "• https://drive.google.com/open?id=xxx"
        )
        return
    
    file_id = extract_file_id(url)
    
    if not file_id:
        await update.message.reply_text(
            "❌ Could not extract file ID!\n\n"
            "Make sure you're sending a file link, not a folder."
        )
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    processing_msg = await update.message.reply_text(
        "🔍 **Checking Google Drive file...**\n⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    try:
        # Get file info
        file_info = await get_file_info_from_page(file_id)
        
        if not file_info:
            await processing_msg.edit_text(
                "❌ **Could not access file**\n\n"
                "**Possible reasons:**\n"
                "• File is private\n"
                "• Link is incorrect\n"
                "• File doesn't exist\n"
                "• Network issue\n\n"
                "**Solution:**\n"
                "• Make file public\n"
                "• Or set to 'Anyone with link'\n"
                "• Check link is correct"
            )
            return
        
        if file_info.get('error') == 'quota_exceeded':
            await processing_msg.edit_text(
                "❌ **Download quota exceeded**\n\n"
                "This file has too many downloads today.\n\n"
                "Google limits downloads for popular files.\n"
                "Try again tomorrow or ask file owner to:\n"
                "• Make a copy of the file\n"
                "• Share the new copy"
            )
            return
        
        if file_info.get('error') == 'in_trash':
            await processing_msg.edit_text(
                "❌ **File is in trash**\n\n"
                "The file owner has deleted this file.\n"
                "It's in their trash folder."
            )
            return
        
        file_name = file_info.get('name', 'Unknown')
        file_size = file_info.get('size', 0)
        file_size_mb = file_size / (1024 * 1024) if file_size else 0
        
        # Check size
        if file_size > 2000 * 1024 * 1024:
            await processing_msg.edit_text(
                f"❌ **File too large**\n\n"
                f"📁 {file_name}\n"
                f"📦 Size: {file_size_mb:.1f}MB\n\n"
                f"Telegram limit: 2GB (2048MB)\n\n"
                f"This file is too large to send."
            )
            return
        
        # Store data
        context.user_data['file_id'] = file_id
        context.user_data['file_name'] = file_name
        context.user_data['file_size'] = file_size
        
        # Show info
        keyboard = [[InlineKeyboardButton("📥 Download File", callback_data='download')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        size_text = f"{file_size_mb:.1f}MB" if file_size_mb > 0 else "Unknown"
        
        info_text = (
            f"✅ **File Found!**\n\n"
            f"📁 **Name:** {file_name}\n"
            f"📦 **Size:** {size_text}\n\n"
            f"Click button to download!"
        )
        
        await processing_msg.edit_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(
            "❌ **An error occurred**\n\n"
            f"Please try again or check if:\n"
            "• Link is correct\n"
            "• File is public\n"
            "• File exists"
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle download"""
    query = update.callback_query
    await query.answer()
    
    file_id = context.user_data.get('file_id')
    file_name = context.user_data.get('file_name')
    
    if not file_id:
        await query.message.reply_text("❌ Session expired. Send link again.")
        return
    
    download_msg = await query.message.reply_text(
        f"⬇️ **Starting download...**\n\n📁 {file_name[:40]}...\n\n⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    filename = None
    
    try:
        os.makedirs('downloads', exist_ok=True)
        
        safe_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.'))[:100]
        filename = f'downloads/{safe_name}'
        
        success = await download_file_with_progress(file_id, filename, download_msg, file_name)
        
        if not success or not os.path.exists(filename):
            await download_msg.edit_text(
                "❌ **Download failed**\n\n"
                "This can happen when:\n"
                "• File has download quota exceeded\n"
                "• File is too large\n"
                "• Connection timeout\n\n"
                "Try:\n"
                "• Tomorrow (quota resets)\n"
                "• Smaller file\n"
                "• Fresh link"
            )
            return
        
        actual_size = os.path.getsize(filename)
        actual_size_mb = actual_size / (1024 * 1024)
        
        if actual_size < 100:
            await download_msg.edit_text("❌ Download failed - file corrupted.")
            os.remove(filename)
            return
        
        await download_msg.edit_text(
            f"⬆️ **Uploading to Telegram...**\n\n"
            f"📁 {file_name[:40]}...\n"
            f"📤 Size: {actual_size_mb:.1f}MB\n"
            f"⏳ Please wait...",
            parse_mode='Markdown'
        )
        
        caption = f"✅ **Downloaded via @Velveta_YT_Downloader_bot**\n\n📁 {file_name}"
        
        file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        
        with open(filename, 'rb') as f:
            if file_ext in ['mp4', 'mkv', 'avi', 'mov', 'webm']:
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
        
        await download_msg.delete()
        
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
        await download_msg.edit_text(f"❌ Upload failed: {str(e)[:100]}")
        
    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
            except:
                pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

async def health_check(request):
    return web.Response(text="Google Drive Downloader Running! 🚀")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Web server: {PORT}")

async def start_bot():
    if not BOT_TOKEN:
        logger.error("No token!")
        return
    
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_error_handler(error_handler)
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    await app.initialize()
    await app.start()
    await app.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("Google Drive Bot Started! 🎉")
    
    while True:
        await asyncio.sleep(1)

async def main():
    await asyncio.gather(start_web_server(), start_bot())

if __name__ == '__main__':
    asyncio.run(main())
