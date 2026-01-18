# bot.py - TeraBox Downloader Bot with Direct Method

import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, ContextTypes, filters
from telegram.constants import ChatAction
import asyncio
from aiohttp import web
import aiohttp
import re
import json

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
🌟 **Welcome to Velveta TeraBox Downloader!**
🌟

Download files from TeraBox links! 🚀

**How to use:**
1️⃣ Send a TeraBox link 🔗
2️⃣ Click Download button 📥
3️⃣ Get your file! ✅

**Supported links:**
• terabox.com
• 1024tera.com
• 1024terabox.com
• freeterabox.com
• And more TeraBox domains

**⚠️ Important:**
• Max file size: 2GB
• Large files take time
• Some links may not work

💡 Just send the TeraBox share link!
"""
    
    keyboard = [[InlineKeyboardButton("📢 Join Update Channel", url=f"https://t.me/{CHANNEL_USERNAME[1:]}")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode='Markdown')

def is_terabox_link(url):
    """Check if URL is a TeraBox link"""
    terabox_domains = [
        'terabox.com',
        '1024tera.com',
        'teraboxapp.com',
        '1024terabox.com',
        'terabox.tech',
        'mirrobox.com',
        'nephobox.com',
        '4funbox.com',
        'freeterabox.com',
        'terabox.app',
        'teraboxlink.com'
    ]
    return any(domain in url.lower() for domain in terabox_domains)

def extract_surl(url):
    """Extract surl parameter from TeraBox link"""
    # Try different patterns
    patterns = [
        r'surl=([^&\s]+)',
        r'/s/1([^&\s]+)',
        r'/sharing/link\?surl=([^&\s]+)',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None

async def get_terabox_file_info(url):
    """Get file info using multiple methods"""
    try:
        # Method 1: Try with teraboxvideodownloader API
        async with aiohttp.ClientSession() as session:
            api_url = "https://teraboxvideodownloader.nephobox.com/api/video/info"
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                'Content-Type': 'application/json',
            }
            
            data = {'url': url}
            
            async with session.post(api_url, json=data, headers=headers, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('status') == 'success':
                        return result
        
        # Method 2: Try with another API
        async with aiohttp.ClientSession() as session:
            api_url = "https://ytshorts.savetube.me/api/v1/terabox-downloader"
            
            data = {'url': url}
            
            async with session.post(api_url, json=data, timeout=30) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get('response'):
                        return result
        
        # Method 3: Direct TeraBox API call
        surl = extract_surl(url)
        if surl:
            async with aiohttp.ClientSession() as session:
                # Try to get file list directly from TeraBox
                api_url = f"https://www.terabox.com/share/list?shorturl={surl}&root=1"
                
                headers = {
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                    'Accept': 'application/json',
                }
                
                async with session.get(api_url, headers=headers, timeout=30) as response:
                    if response.status == 200:
                        result = await response.json()
                        if result.get('errno') == 0:
                            return {'direct': True, 'data': result}
        
    except Exception as e:
        logger.error(f"All methods failed: {e}")
    
    return None

async def download_file_with_progress(url, filename, download_msg, file_title):
    """Download file with progress bar"""
    try:
        async with aiohttp.ClientSession() as session:
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
            
            async with session.get(url, headers=headers, timeout=1800) as response:
                if response.status != 200:
                    return False
                
                total_size = int(response.headers.get('content-length', 0))
                downloaded = 0
                last_update = 0
                
                with open(filename, 'wb') as f:
                    async for chunk in response.content.iter_chunked(1024 * 512):
                        f.write(chunk)
                        downloaded += len(chunk)
                        
                        if downloaded - last_update > 5 * 1024 * 1024:
                            if total_size > 0:
                                percent = (downloaded / total_size) * 100
                                mb_downloaded = downloaded / (1024 * 1024)
                                mb_total = total_size / (1024 * 1024)
                                
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
            "Supported: terabox.com, 1024tera.com, etc."
        )
        return
    
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action=ChatAction.TYPING)
    
    processing_msg = await update.message.reply_text(
        "🔍 **Processing TeraBox link...**\n⏳ Please wait, trying multiple methods...",
        parse_mode='Markdown'
    )
    
    try:
        # Get file info
        file_info = await get_terabox_file_info(url)
        
        if not file_info:
            await processing_msg.edit_text(
                "❌ **Could not process this link**\n\n"
                "**This can happen when:**\n"
                "• Link is expired or invalid\n"
                "• File is password-protected\n"
                "• TeraBox servers are blocking requests\n"
                "• Link format is not supported\n\n"
                "**💡 Try:**\n"
                "• Get a fresh share link\n"
                "• Use a public (non-password) link\n"
                "• Try a different file\n\n"
                "**Note:** Due to TeraBox restrictions, some links may not work. "
                "This is a limitation of TeraBox, not the bot."
            )
            return
        
        # Parse response based on method used
        if file_info.get('direct'):
            # Direct TeraBox API response
            data = file_info['data']
            file_list = data.get('list', [])
            
            if not file_list:
                await processing_msg.edit_text("❌ No files found in this link.")
                return
            
            file_data = file_list[0]
            file_name = file_data.get('server_filename', 'Unknown')
            file_size = file_data.get('size', 0)
            download_url = file_data.get('dlink', '')
            
        elif file_info.get('response'):
            # API method response
            response_data = file_info.get('response', [])
            if isinstance(response_data, list) and response_data:
                file_data = response_data[0]
            else:
                file_data = response_data
            
            file_name = file_data.get('filename', file_data.get('file_name', 'Unknown'))
            file_size = file_data.get('size', file_data.get('file_size', 0))
            download_url = file_data.get('download_link', file_data.get('direct_link', ''))
        
        else:
            # Other API format
            data = file_info.get('data', {})
            file_name = data.get('file_name', data.get('title', 'Unknown'))
            file_size = data.get('file_size', data.get('size', 0))
            download_url = data.get('download_url', data.get('video_url', ''))
        
        if not download_url:
            await processing_msg.edit_text(
                "❌ **Download link not available**\n\n"
                "TeraBox is blocking direct downloads for this file.\n"
                "This is a TeraBox restriction, not a bot issue.\n\n"
                "Try another file or link."
            )
            return
        
        # Check file size
        file_size_mb = file_size / (1024 * 1024) if file_size else 0
        
        if file_size > 2000 * 1024 * 1024:
            await processing_msg.edit_text(
                f"❌ **File too large!**\n\n"
                f"📁 {file_name}\n"
                f"📦 Size: {file_size_mb:.1f}MB\n\n"
                f"Telegram limit: 2GB (2048MB)\n"
                f"This file exceeds the limit."
            )
            return
        
        # Store data
        context.user_data['file_name'] = file_name
        context.user_data['file_size'] = file_size
        context.user_data['download_url'] = download_url
        context.user_data['original_url'] = url
        
        # Show file info
        keyboard = [[InlineKeyboardButton("📥 Download File", callback_data='download')]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        size_text = f"{file_size_mb:.1f}MB" if file_size_mb > 0 else "Unknown"
        
        info_text = (
            f"✅ **File Ready!**\n\n"
            f"📁 **Name:** {file_name}\n"
            f"📦 **Size:** {size_text}\n\n"
            f"Click button to download!"
        )
        
        await processing_msg.edit_text(info_text, reply_markup=reply_markup, parse_mode='Markdown')
        
    except Exception as e:
        logger.error(f"Error: {e}")
        await processing_msg.edit_text(
            "❌ **An error occurred**\n\n"
            f"Error: {str(e)[:100]}\n\n"
            "Please try again or use a different link."
        )

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle download button"""
    query = update.callback_query
    await query.answer()
    
    file_name = context.user_data.get('file_name')
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
        os.makedirs('downloads', exist_ok=True)
        
        safe_name = "".join(c for c in file_name if c.isalnum() or c in (' ', '-', '_', '.'))[:100]
        filename = f'downloads/{safe_name}'
        
        success = await download_file_with_progress(download_url, filename, download_msg, file_name)
        
        if not success or not os.path.exists(filename):
            await download_msg.edit_text(
                "❌ **Download failed**\n\n"
                "Possible reasons:\n"
                "• Connection timeout\n"
                "• Link expired\n"
                "• TeraBox is blocking downloads\n\n"
                "Try getting a fresh link from TeraBox."
            )
            return
        
        actual_size = os.path.getsize(filename)
        actual_size_mb = actual_size / (1024 * 1024)
        
        if actual_size < 1024:
            await download_msg.edit_text("❌ Download failed - file is corrupted.")
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
            elif file_ext in ['mp3', 'm4a', 'wav', 'flac', 'ogg']:
                sent_msg = await context.bot.send_audio(
                    chat_id=query.message.chat_id,
                    audio=f,
                    caption=caption,
                    parse_mode='Markdown',
                    read_timeout=600,
                    write_timeout=600
                )
            elif file_ext in ['jpg', 'jpeg', 'png', 'gif', 'webp']:
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
            f"Error: {str(e)[:100]}\n\n"
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
    return web.Response(text="TeraBox Downloader Bot Running! 🚀")

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
    
    logger.info("TeraBox Downloader Bot Started! 🎉")
    
    while True:
        await asyncio.sleep(1)

async def main():
    await asyncio.gather(start_web_server(), start_bot())

if __name__ == '__main__':
    asyncio.run(main())
