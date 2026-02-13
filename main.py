import sys
import os
import asyncio
import time
import logging
import threading
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import UserNotParticipant
import yt_dlp

# --- 1. LOGGING ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# --- 2. CONFIGURATION ---
API_ID = 11253846                   
API_HASH = "8db4eb50f557faa9a5756e64fb74a51a" 
# మీ కొత్త బాట్ టోకెన్ ఇక్కడ ఇవ్వండి
BOT_TOKEN = "8381012379:AAF5VKvjQmLK5qsEP8PNh4MxESUEvr53P6w"

# LINKS
CHANNEL_LINK = "https://t.me/Velvetabots"              
DONATE_LINK = "https://buymeacoffee.com/VelvetaBots"
SUPPORT_LINK = "https://t.me/Velvetasupport" 
BOT_USERNAME = "@VelvetaFbDownloaderBot"
OWNER_ID = 883128927 
# మీ ఛానల్ ID (బాట్ ఇందులో అడ్మిన్ గా ఉండాలి)
FORCE_SUB_CHANNEL = -1001840010906 

# --- 3. WEB SERVER (Keep Alive) ---
web_app = Flask(__name__)

@web_app.route('/')
def home():
    return "✅ Velveta Bot is Online!"

def run_web_server():
    # JustRunMy.app పోర్ట్ ని ఆటోమేటిక్ గా తీసుకుంటుంది
    port = int(os.environ.get("PORT", 8080))
    web_app.run(host="0.0.0.0", port=port)

# --- 4. CLIENT SETUP ---
app = Client(
    "velveta_fb_bot", 
    api_id=API_ID, 
    api_hash=API_HASH, 
    bot_token=BOT_TOKEN, 
    in_memory=True, 
    ipv6=False 
)

user_data_store = {} 
user_pending_links = {}

# --- 5. SUBSCRIPTION CHECK ---
async def get_subscription_status(user_id):
    try:
        member = await app.get_chat_member(FORCE_SUB_CHANNEL, user_id)
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.MEMBER]:
            return True
    except UserNotParticipant:
        return False
    except Exception:
        return True 
    return False

# --- 6. AUTO-CHECK LOOP ---
async def auto_check_subscription(client, warning_msg, user_id, url):
    for _ in range(150): 
        await asyncio.sleep(2)
        try:
            is_sub = await get_subscription_status(user_id)
            if is_sub:
                try: await warning_msg.delete()
                except: pass
                
                temp_msg = await client.send_message(warning_msg.chat.id, "✅ **Joined Successfully! Analyzing Link...**")
                await asyncio.sleep(1)
                await temp_msg.delete()
                await analyze_link(client, warning_msg, url, is_callback=True) 
                return 
        except Exception:
            pass

# --- 7. PROGRESS BAR ---
def humanbytes(size):
    if not size: return ""
    power = 2**10
    n = 0
    power_labels = {0 : '', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return f"{size:.2f} {power_labels[n]}B"

async def progress(current, total, message, start_time, status_text):
    try:
        now = time.time()
        diff = now - start_time
        if round(diff % 5.00) == 0 or current == total:
            percentage = current * 100 / total
            filled_blocks = int(percentage / 10)
            bar = "🟩" * filled_blocks + "⬜" * (10 - filled_blocks)
            speed = current / diff if diff > 0 else 0
            
            text = (
                f"{status_text}\n"
                f"{bar} **{round(percentage, 1)}%**\n"
                f"⚡ **Speed:** {humanbytes(speed)}/s\n"
                f"💾 **Size:** {humanbytes(current)} / {humanbytes(total)}"
            )
            if message.text != text:
                await message.edit_text(text)
    except Exception:
        pass

# --- 8. GROUP MODERATION ---
@app.on_message(filters.group, group=1)
async def group_moderation(client, message):
    if message.service:
        try: await message.delete()
        except: pass
        return

    if not message.text: return
    if message.from_user and message.from_user.id == OWNER_ID: return
    try:
        member = await client.get_chat_member(message.chat.id, message.from_user.id)
        if member.status in [ChatMemberStatus.OWNER, ChatMemberStatus.ADMINISTRATOR]:
            return 
    except:
        pass

    text = message.text.lower()
    allowed = ["youtube.com", "youtu.be", "tiktok.com", "twitter.com", "x.com", "facebook.com", "fb.watch", "fb.com", "instagram.com"]
    if any(domain in text for domain in allowed):
        return 
    else:
        try: await message.delete()
        except: pass 

# --- 9. SHOW QUALITY MENU ---
async def show_quality_menu(client, chat_id, url, title, message_to_edit=None, reply_to_id=None):
    keyboard = [
        [
            InlineKeyboardButton("🚀 4K (Ultra HD)", callback_data="dl_2160"),
            InlineKeyboardButton("🌟 2K (1440p)", callback_data="dl_1440")
        ],
        [
            InlineKeyboardButton("🖥 1080p (Full HD)", callback_data="dl_1080"),
            InlineKeyboardButton("💻 720p (HD)", callback_data="dl_720")
        ],
        [
            InlineKeyboardButton("📺 480p (Clear)", callback_data="dl_480"),
            InlineKeyboardButton("📱 360p (Best Mobile)", callback_data="dl_360")
        ],
        [
            InlineKeyboardButton("📟 240p", callback_data="dl_240"),
            InlineKeyboardButton("📉 144p (Data Saver)", callback_data="confirm_144")
        ],
        [
            InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data="dl_mp3")
        ]
    ]

    text = f"🎬 **{title}**\n\n👇 **Select Quality:**"

    if message_to_edit:
        sent_msg = await message_to_edit.edit_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return sent_msg
    else:
        if reply_to_id:
            sent_msg = await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard), reply_to_message_id=reply_to_id)
        else:
            sent_msg = await client.send_message(chat_id, text, reply_markup=InlineKeyboardMarkup(keyboard))
        return sent_msg

# --- 10. LINK ANALYSIS ---
async def analyze_link(client, message, url, is_callback=False):
    chat_id = message.chat.id
    reply_id = message.id if not is_callback else None
    
    msg = await client.send_message(chat_id, "🔎 **Analyzing Link...**", reply_to_message_id=reply_id)

    try:
        # JustRunMy.app లో cookies.txt లేకపోతే పర్వాలేదు
        cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
        
        opts_info = {
            'quiet': True, 'noprogress': True, 'cookiefile': cookie_file,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        }

        info = await asyncio.to_thread(run_sync_info, opts_info, url)
        
        if 'entries' in info or info.get('_type') == 'playlist':
             btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛠️ Message Support", url=SUPPORT_LINK)]])
             await msg.edit_text("📸 **Album Detected!**\n\nI can only download single Videos! 😅", reply_markup=btn)
             return

        if info.get('is_live'):
            await msg.edit_text("🔴 **Live Stream Detected!**\n\nI cannot download Live streams.")
            return

        title = info.get('title', 'Facebook Video')[:60] + "..."
        await msg.delete()
        
        # Show Menu & Save Data
        sent_menu_msg = await show_quality_menu(client, chat_id, url, title, reply_to_id=reply_id)
        user_data_store[sent_menu_msg.id] = {'url': url, 'title': title, 'reply_to': reply_id, 'chat_id': chat_id}

    except Exception as e:
        await handle_error(msg, str(e))

# --- 11. ERROR HANDLER ---
async def handle_error(message, error_text):
    error_text = error_text.lower()
    custom_msg = "⚠️ **Download Failed!**"
    
    if "login" in error_text or "private" in error_text:
        custom_msg = "🔒 **Private Account!** Access denied."
    elif "not found" in error_text:
        custom_msg = "❌ **Content Not Found!**"
    
    btn = InlineKeyboardMarkup([[InlineKeyboardButton("🛠️ Message Support", url=SUPPORT_LINK)]])
    try: await message.edit_text(f"{custom_msg}\n\nContact support if needed 👇", reply_markup=btn)
    except: pass

# --- 12. CALLBACK HANDLER ---
@app.on_callback_query()
async def callback_handler(client, query):
    data = query.data
    user_id = query.from_user.id
    msg_id = query.message.id 
    
    if data == "check_sub":
        is_sub = await get_subscription_status(user_id)
        if is_sub:
            await query.answer("✅ Verified!")
            try: await query.message.delete() 
            except: pass
            if user_id in user_pending_links:
                await analyze_link(client, query.message, user_pending_links[user_id], is_callback=True)
                del user_pending_links[user_id]
        else:
            await query.answer("⚠️ Not Joined Yet!", show_alert=True)
        return

    # Session Recovery Logic
    stored_data = user_data_store.get(msg_id)
    if not stored_data:
        try:
            original_msg = query.message.reply_to_message
            if original_msg and original_msg.text:
                url_candidate = original_msg.text.strip()
                if "facebook.com" in url_candidate or "fb.watch" in url_candidate:
                    stored_data = {
                        'url': url_candidate, 'title': "Facebook Video",
                        'chat_id': query.message.chat.id, 'reply_to': original_msg.id
                    }
                    user_data_store[msg_id] = stored_data
        except: pass

    if not stored_data:
        await query.answer("❌ Session Expired. Send link again.", show_alert=True)
        return

    if data == "confirm_144":
        await query.message.edit_text(
            "⚠️ **Confirmation Required!**\n\n👀 **Note:** 144p quality is very low.\n🤔 **Do you want to proceed?**",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yes, Sure", callback_data="dl_144"), InlineKeyboardButton("🔙 Back", callback_data="back_to_menu")]])
        )
        return

    if data == "back_to_menu":
        await show_quality_menu(client, stored_data['chat_id'], stored_data['url'], stored_data['title'], message_to_edit=query.message)
        return

    if data.startswith("dl_"):
        url = stored_data['url']
        chat_id = stored_data['chat_id']
        reply_to_id = stored_data['reply_to']
        quality = data.split("_")[1]
        
        await query.message.delete()
        status_msg = await client.send_message(chat_id, "⏳ **Initializing Download...**")
        await process_download_final(client, status_msg, url, quality, chat_id, reply_to_id)

# --- 13. FINAL DOWNLOADER ---
async def process_download_final(client, status_msg, url, quality, chat_id, reply_to_id):
    try:
        filename_base = f"downloads/fb_{chat_id}_{int(time.time())}"
        cookie_file = 'cookies.txt' if os.path.exists('cookies.txt') else None
        
        # Use 'best' to avoid merging errors on generic servers
        fmt = 'bestaudio/best' if quality == "mp3" else 'best'

        opts = {
            'quiet': True, 'noprogress': True, 'cookiefile': cookie_file,
            'format': fmt, 'outtmpl': f'{filename_base}.%(ext)s',
            'writethumbnail': True,
            'postprocessors': [{'key': 'FFmpegThumbnailsConvertor', 'format': 'jpg'}],
        }

        if quality == "mp3":
            opts['postprocessors'].insert(0, {'key': 'FFmpegExtractAudio','preferredcodec': 'mp3','preferredquality': '192'})
        else:
             opts['merge_output_format'] = 'mp4'

        await status_msg.edit_text("⬇️ **Downloading...** ▰▱▱▱")
        start_time = time.time()
        await asyncio.to_thread(run_sync_download, opts, url)
        
        final_path = None
        thumb_path = None
        exts = ['mp3'] if quality == "mp3" else ['mp4', 'mkv', 'webm']
        
        for ext in exts:
            if os.path.exists(f"{filename_base}.{ext}"):
                final_path = f"{filename_base}.{ext}"
                break
        
        if os.path.exists(f"{filename_base}.jpg"): thumb_path = f"{filename_base}.jpg"
        elif os.path.exists(f"{filename_base}.webp"): thumb_path = f"{filename_base}.webp"

        if not final_path: raise Exception("Download failed.")

        await status_msg.edit_text("☁️ **Uploading...** 🚀")
        
        caption_text = f"✅ **Downloaded via {BOT_USERNAME}**"
        donate_btn = InlineKeyboardMarkup([[InlineKeyboardButton("☕ Donate", url=DONATE_LINK)]])

        if quality == "mp3":
            await client.send_audio(
                chat_id, audio=final_path, thumb=thumb_path, caption=caption_text, reply_markup=donate_btn,
                reply_to_message_id=reply_to_id, progress=progress, progress_args=(status_msg, start_time, "☁️ **Uploading Audio...**")
            )
        else:
            await client.send_video(
                chat_id, video=final_path, thumb=thumb_path, caption=caption_text, reply_markup=donate_btn,
                reply_to_message_id=reply_to_id, progress=progress, progress_args=(status_msg, start_time, "☁️ **Uploading Video...**")
            )
        
        await status_msg.delete()
        if final_path: os.remove(final_path)
        if thumb_path: os.remove(thumb_path)

    except Exception as e:
        await handle_error(status_msg, str(e))

# --- 14. HELPERS & START ---
def run_sync_download(opts, url):
    with yt_dlp.YoutubeDL(opts) as ydl: ydl.download([url])

def run_sync_info(opts, url):
    with yt_dlp.YoutubeDL(opts) as ydl: return ydl.extract_info(url, download=False)

@app.on_message(filters.command("start"))
async def start(client, message):
    is_sub = await get_subscription_status(message.from_user.id)
    if not is_sub:
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Update Channel", url=CHANNEL_LINK)],[InlineKeyboardButton("✅ Joined", callback_data="check_sub")]])
        await client.send_message(message.chat.id, "🛑 **Access Denied!**\n\nTo use this bot, you must join our Official Update Channel first. 🔒", reply_markup=btn)
        return

    welcome_text = (
        "🔵 **Welcome to Velveta Facebook Downloader!** 🔵\n\n"
        "I can download Facebook videos and reels! 🚀\n\n"
        "**How to use:**\n"
        "1️⃣ Send a Facebook link 🔗\n"
        "2️⃣ Select Video or Audio ✨\n"
        "3️⃣ Get your file! 📥"
    )
    await client.send_message(message.chat.id, welcome_text)

@app.on_message(filters.text & ~filters.command("start"), group=2)
async def handle_link(client, message):
    url = message.text
    user_id = message.from_user.id
    if "facebook.com" not in url and "fb.watch" not in url and "fb.com" not in url: return 

    is_sub = await get_subscription_status(user_id)
    if not is_sub:
        user_pending_links[user_id] = url
        btn = InlineKeyboardMarkup([[InlineKeyboardButton("📢 Join Update Channel", url=CHANNEL_LINK)],[InlineKeyboardButton("✅ Joined", callback_data="check_sub")]])
        warn_msg = await message.reply_text("🛑 **Access Denied!**\n\nTo download videos, you must join our Official Update Channel first. 🔒\n\n⏳ *Checking verification automatically...*", reply_markup=btn, quote=True)
        asyncio.create_task(auto_check_subscription(client, warn_msg, user_id, url))
        return

    await analyze_link(client, message, url)

if __name__ == '__main__':
    if not os.path.exists('downloads'): os.makedirs('downloads')
    t = threading.Thread(target=run_web_server); t.daemon = True; t.start()
    print("✅ Bot Started!"); app.run()
    
