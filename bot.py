# bot.py - Google Drive Downloader Bot

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
2️⃣ Click Download button 📥
3️⃣ Get your file! ✅

**Supported links:**
• drive.google.com/file/d/...
• drive.google.com/open?id=...
• docs.google.com/...

**Features:**
✅ Works with all public files
✅ Up to 2GB file size
✅ Fast downloads
✅ Progress tracking
✅ All file types supported

**⚠️ Note:**
• File must be public or "Anyone with link"
• Private files won't work
• Max size: 2GB (Telegram limit)

💡 Just send any Google Drive share link!
"""
    
    keyboard = [[InlineKeyboardButton("📢 Join Update Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

def extract_file_id(url):
    """Extract Google Drive file ID from URL"""
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
    """Check if URL is a Google Drive link"""
    gdrive_domains = ['drive.google.com', 'docs.google.com']
    return any(domain in url.lower() for domain in gdrive_domains)

async def get_gdrive_file_info(file_id):
    """Get file info from Google Drive"""
    try:
        # Use Google Drive API v3 (public endpoint)
        api_url = f"https://www.googleapis.com/drive/v3/files/{file_id}?fields=id,name,mimeType,size,webContentLink&key=AIzaSyDRN1d1Gx0p6_aHQQYYZ9Uf5-KVUvE5b9M"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(api_url, timeout=30) as response:
                if response.status == 200:
                    return await response.json()
                elif response.status == 404:
                    return {'error': 'not_found'}
                elif response.status == 403:
                    return {'error': 'permission_denied'}
                else:
                    return None
    except Exception as e:
        logger.error(f"Error getting file info: {e}")
        return None

def get_direct_download_link(file_id):
    """Generate direct download link"""
    return f"https://drive.google.com/uc?export=download&id={file_id}"

async def download_file_with_progress(file_id, filename, download_msg, file_title):
    """Download file with progress bar"""
    try:
        # For large files, we need to handle confirmation
        download_url = get_direct_download_link(file_id)
        
        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, allow_redirects=True, timeout=1800) as response:
                
                # Check if we need confirmation (large files)
                if 'accounts.google.com' in str(response.url):
                    return False
                
                content = await response.text()
                
                # Check for virus scan warning
                if 'Google Drive - Virus scan warning' in content or 'download_warning' in content:
                    # Extract confirmation token
                    match = re.search(r'confirm=([0-9A-Za-z_]+)', content)
                    if match:
                        confirm_token = match.group(1)
                        download_url = f"https://drive.google.com/uc?export=download&id={file_id}&confirm={confirm_token}"
                    else:
                        # Try alternate method
                        download_url = f"https://drive.usercontent.google.com/download?id={file_id}&export=download&confirm=t"
                
            # Now download with the correct URL
            async with session.get(download_url, allow_redirects=True, timeout=1800) as response:
                if response.status != 200:
                    return False
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_update = 0
                
                with open(filename, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 512):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        # Update progress every 3MB
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
                
    except asyncio.TimeoutError:
        logger.error("Download timeout")
        return False
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
            "Example:\n"
            "https://drive.google.com/file/d/xxx/view"
        )
        return
    
    file_id = extract_file_id(url)
    
    if not file_id:
        await update.message.reply_text(
            "❌ Could not extract file ID from the link.\n\n"
            "Please send a valid Google Drive file link."
        )
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    processing_msg = await update.message.reply_text(
        "🔍 **Checking Google Drive file...**\n⏳ Please wait...",
        parse_mode='Markdown'
    )
    
    try:
        # Get file info
        file_info = await get_gdrive_file_info(file_id)
        
        if not file_info:
            await processing_msg.edit_text(
                "❌ **Could not access file**\n\n"
                "Please check:\n"
                "• Link is correct\n"
                "• File is public or 'Anyone with link'\n"
                "• File exists and not deleted"
            )
            return
        
        if file_info.get('error') == 'not_found':
            await processing_msg.edit_text(
                "❌ **File not found**\n\n"
                "The file may have been:\n"
                "• Deleted\n"
                "• Moved\n"
                "• Made private\n\n"
                "Please check the link and try again."
            )
            return
        
        if file_info.get('error') == 'permission_denied':
            await processing_msg.edit_text(
                "❌ **Access denied**\n\n"
                "This file is private.\n\n"
                "To download:\n"
                "• Make file public, or\n"
                "• Set sharing to 'Anyone with link'\n\n"
                "Then try again."
            )
            return
        
        # Extract file details
        file_name = file_info.get('name', 'Unknown')
        file_size = int(file_info.get('size', 0))
        mime_type = file_info.get('mimeType', '')
        
        # Check if it's a Google Docs file
        if 'google-apps' in mime_type:
            await processing_msg.edit_text(
                "❌ **Google Docs/Sheets/Slides not supported**\n\n"
                "This is a Google Workspace file.\n\n"
                "To download:\n"
                "1. Open the file\n"
                "2. File → Download as → Choose format\n"
                "3. Upload to Drive as regular file\n"
                "4. Share and send that link"
            )
            return
        
        file_size_mb = file_size / (1024 * 1024)
        
        # Check file size
        if file_size > 2000 * 1024 * 1024:
            await processing_msg.edit_text(
                f"❌ **File too large**\n\n"
                f"📁 {file_name}\n"
                f"📦 Size: {file_size_mb:.1f}MB\n\n"
                f"Telegram limit: 2GB (2048MB)\n"
                f"This file: {file_size_mb:.1f}MB\n\n"
                f"File is too large to send via Telegram."
            )
            return
        
        # Store data
        context.user_data['file_id'] = file_id
        context.user_data['file_name'] = file_name
        context.user_data['file_size'] = file_size
        
        # Show file info
        keyboard = [[InlineKeyboardButton("📥 Download File", callback_data='download')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        info_text = (
            f"✅ **File Found!**\n\n"
            f"📁 **Name:** {file_name}\n"
            f"📦 **Size:** {file_size_mb:.1f}MB\n\n"
            f"Click button to download!"
        )
        
        await processing_msg.edit_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(
            "❌ **An error occurred**\n\n"
            f"Error: {str(e)[:150]}\n\n"
            "Please try again."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle download button"""
    query = update.callback_query
    await query.answer()
    
    file_id = context.user_data.get('file_id')
    file_name = context.user_data.get('file_name')
    file_size = context.user_data.get('file_size', 0)
    
    if not file_id:
        await query.message.reply_text("❌ Session expired. Please send the link again.")
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
        
        # Download file
        success = await download_file_with_progress(file_id, filename, download_msg, file_name)
        
        if not success or not os.path.exists(filename):
            await download_msg.edit_text(
                "❌ **Download failed**\n\n"
                "This can happen when:\n"
                "• File is too large\n"
                "• Connection timeout\n"
                "• File permissions changed\n\n"
                "Try:\n"
                "• Smaller file\n"
                "• Fresh link\n"
                "• Check file is still public"
            )
            return
        
        actual_size = os.path.getsize(filename)
        actual_size_mb = actual_size / (1024 * 1024)
        
        if actual_size < 100:  # Less than 100 bytes
            await download_msg.edit_text(
                "❌ **Download failed**\n\n"
                "File appears to be corrupted or empty.\n"
                "Please check the file and try again."
            )
            os.remove(filename)
            return
        
        # Upload to Telegram
        await download_msg.edit_text(
            f"⬆️ **Uploading to Telegram...**\n\n"
            f"📁 {file_name[:40]}...\n"
            f"📤 Size: {actual_size_mb:.1f}MB\n"
            f"⏳ Please wait...",
            parse_mode='Markdown'
        )
        
        caption = f"✅ **Downloaded via @Velveta_YT_Downloader_bot**\n\n📁 {file_name}"
        
        # Detect file type
        file_ext = file_name.lower().split('.')[-1] if '.' in file_name else ''
        
        with open(filename, 'rb') as f:
            if file_ext in ['mp4', 'mkv', 'avi', 'mov', 'webm', 'flv']:
                sent_msg = await context.bot.send_video(
                    chat_id=query.message.chat_id,
                    video=f,
                    caption=caption,
                    parse_mode='Markdown',
                    supports_streaming=True,
                    read_timeout=600,
                    write_timeout=600
                )
            elif file_ext in ['mp3', 'm4a', 'wav', 'flac', 'ogg', 'aac']:
                sent_msg = await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=f,
                    caption=caption,
                    parse_mode='Markdown',
                    read_timeout=600,
                    write_timeout=600
                )
            elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp', 'bmp']:
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
        await download_msg.edit_text(
            f"❌ **Upload failed**\n\n"
            f"Error: {str(e)[:150]}\n\n"
            "File may be too large or corrupted."
        )
        
    finally:
        if filename and os.path.exists(filename):
            try:
                os.remove(filename)
                logger.info(f"Cleaned up: {filename}")
            except:
                pass

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")

async def health_check(request):
    return web.Response(text="Google Drive Downloader Bot Running! 🚀")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    app.router.add_get('/health', health_check)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    logger.info(f"Web server started on port {PORT}")

async def start_bot():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    application.add_error_handler(error_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    application.add_handler(CallbackQueryHandler(button_callback))
    
    await application.initialize()
    await application.start()
    await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
    
    logger.info("Google Drive Downloader Bot Started! 🎉")
    
    while True:
        await asyncio.sleep(1)

async def main():
    await asyncio.gather(start_web_server(), start_bot())

if __name__ == '__main__':
    asyncio.run(main())
