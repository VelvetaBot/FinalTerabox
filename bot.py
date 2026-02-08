import os
import time
import asyncio
import threading
import shutil
import subprocess
import sys
import tarfile
import urllib.request
import stat
from flask import Flask
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
from pyrogram.enums import ChatType 
import yt_dlp

# --- 0. ADMIN CONFIGURATION ---
LOG_GROUP_ID = 0  

# --- 1. SETUP ENVIRONMENT ---
def setup_environment():
    base_dir = os.getcwd()
    bin_dir = os.path.join(base_dir, "bin")
    if not os.path.exists(bin_dir): os.makedirs(bin_dir)
    
    # Node.js
    node_exe = os.path.join(bin_dir, "node")
    if not os.path.exists(node_exe):
        print("⬇️ Downloading Node.js v16...")
        try:
            url = "https://nodejs.org/dist/v16.20.0/node-v16.20.0-linux-x64.tar.xz"
            tar_path = "node.tar.xz"
            urllib.request.urlretrieve(url, tar_path)
            with tarfile.open(tar_path) as tar:
                tar.extractall()
            for item in os.listdir():
                if item.startswith("node-v16") and os.path.isdir(item):
                    shutil.move(os.path.join(item, "bin", "node"), node_exe)
                    shutil.rmtree(item)
                    break
            if os.path.exists(tar_path): os.remove(tar_path)
            os.chmod(node_exe, 0o755)
            print("✅ Node.js installed.")
        except Exception as e:
            print(f"⚠️ Node install error: {e}")

    # FFmpeg
    ffmpeg_exe = os.path.join(bin_dir, "ffmpeg")
    if not os.path.exists(ffmpeg_exe):
        print("⬇️ Downloading FFmpeg...")
        try:
            url = "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-amd64-static.tar.xz"
            tar_path = "ffmpeg.tar.xz"
            urllib.request.urlretrieve(url, tar_path)
            with tarfile.open(tar_path) as tar:
                tar.extractall()
            for item in os.listdir():
                if item.startswith("ffmpeg-") and os.path.isdir(item):
                    shutil.move(os.path.join(item, "ffmpeg"), ffmpeg_exe)
                    shutil.rmtree(item)
                    break
            if os.path.exists(tar_path): os.remove(tar_path)
            os.chmod(ffmpeg_exe, 0o755)
            print("✅ FFmpeg installed.")
        except Exception as e:
            print(f"⚠️ FFmpeg install error: {e}")

    os.environ["PATH"] = f"{bin_dir}:{os.environ['PATH']}"
    return bin_dir

BIN_DIR = setup_environment()

# --- 2. CONFIGURATION ---
API_ID = 11253846
API_HASH = "8db4eb50f557faa9a5756e64fb74a51a"
BOT_TOKEN = "8161146581:AAFztbSlsW-qGmDRVivmRxtwwtsGnfM1eZY"

# --- 3. FORCE UPDATE YT-DLP (PRE-RELEASE) ---
try:
    print("⚙️ Installing yt-dlp Nightly Build...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "--force-reinstall", "--pre", "yt-dlp"])
except:
    pass

# --- 4. FLASK SERVER ---
app_web = Flask(__name__)

@app_web.route('/')
def home(): return "✅ Velveta Pro is Live!"

def run_web():
    port = int(os.environ.get("PORT", 8080))
    app_web.run(host="0.0.0.0", port=port)

threading.Thread(target=run_web, daemon=True).start()

# --- 5. TELEGRAM CLIENT ---
app = Client("velveta_pro", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

# --- 6. HELPER FUNCTIONS ---
def humanbytes(size):
    if not size: return "0 B"
    power = 2**10
    n = 0
    dic_powerN = {0: ' ', 1: 'Ki', 2: 'Mi', 3: 'Gi', 4: 'Ti'}
    while size > power:
        size /= power
        n += 1
    return str(round(size, 2)) + " " + dic_powerN[n] + 'B'

def time_formatter(seconds):
    return f"{int(seconds//3600):02d}:{int((seconds%3600)//60):02d}:{int(seconds%60):02d}"

async def progress_bar(current, total, status_msg, start_time, title, action_name):
    try:
        now = time.time()
        diff = now - start_time
        if round(diff % 5.00) == 0 or current == total:
            percentage = current * 100 / total
            speed = current / diff if diff > 0 else 0
            eta = round((total - current) / speed) if speed > 0 else 0
            bar = "██" * int(percentage / 10) + "░░" * (10 - int(percentage / 10))
            text = f"⬇️ **{action_name}...**\n🎬 **{title}**\n\n📊 **Progress:** {bar} {round(percentage, 2)}%\n⚡ **Speed:** {humanbytes(speed)}/s\n⏳ **ETA:** {time_formatter(eta)}"
            if status_msg.text != text: await status_msg.edit_text(text)
    except: pass

# --- 7. HANDLERS ---
@app.on_message(filters.command("start"))
async def start_msg(client, message):
    if message.chat.type == ChatType.PRIVATE:
        text = (
            "🌟 Welcome to Velveta Downloader (Pro)! 🌟\n"
            "I can download YouTube videos up to 2GB! 🚀\n\n"
            "How to use:\n"
            "1️⃣ Send a YouTube link 🔗\n"
            "2️⃣ Select Quality ✨\n"
            "3️⃣ Wait for the magic! 📥"
        )
        buttons = [[InlineKeyboardButton("📢 Join Update Channel", url="https://t.me/Velvetabots")]]
        await message.reply_text(text, reply_markup=InlineKeyboardMarkup(buttons))

url_store = {}

@app.on_message(filters.text & ~filters.command("start"))
async def handle_link(client, message):
    url = message.text
    if message.chat.type in [ChatType.GROUP, ChatType.SUPERGROUP]:
        if not any(x in url for x in ["youtube.com", "youtu.be", "shorts"]): return
    elif not any(x in url for x in ["youtube.com", "youtu.be", "shorts"]):
        return await message.reply_text("❌ Please send a valid YouTube link.")

    msg = await message.reply_text("🔎 **Fetching Info...**", quote=True)
    
    title = "YouTube Video"
    thumb = None
    
    # ATTEMPT: Android Creator (Requires Nightly - Best for bypassing Sign In)
    try:
        ydl_opts_info = {
            'quiet': True, 
            'check_formats': False,
            'extractor_args': {'youtube': {'player_client': ['android_creator', 'android']}} 
        }
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            try:
                info = await asyncio.to_thread(ydl.extract_info, url, download=False)
                title = info.get('title', 'YouTube Video')
                thumb = info.get('thumbnail', None)
            except: pass
    except Exception as e: print(f"⚠️ Info extraction failed: {e}")

    unique_id = f"{message.chat.id}_{message.id}"
    url_store[unique_id] = {'url': url, 'title': title, 'thumb': thumb, 'msg_id': message.id}

    # BUTTONS MATCHING SCREENSHOT EXACTLY
    buttons = [
        [InlineKeyboardButton("🚀 4K (Ultra HD)", callback_data=f"2160|{unique_id}"), InlineKeyboardButton("🌟 2K (1440p)", callback_data=f"1440|{unique_id}")],
        [InlineKeyboardButton("🖥 1080p (Full HD)", callback_data=f"1080|{unique_id}"), InlineKeyboardButton("💻 720p (HD)", callback_data=f"720|{unique_id}")],
        [InlineKeyboardButton("📺 480p (Clear)", callback_data=f"480|{unique_id}"), InlineKeyboardButton("📱 360p (Best Mobile)", callback_data=f"360|{unique_id}")],
        [InlineKeyboardButton("📟 240p", callback_data=f"240|{unique_id}"), InlineKeyboardButton("📉 144p (Data Saver)", callback_data=f"warn_144|{unique_id}")],
        [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data=f"mp3|{unique_id}")]
    ]
    await msg.edit_text(f"🎬 **{title}**\n\n👇 **Select Quality:**", reply_markup=InlineKeyboardMarkup(buttons))

@app.on_callback_query()
async def callback(client, query):
    data = query.data.split("|")
    action, unique_id = data[0], data[1]
    
    if unique_id not in url_store: return await query.answer("❌ Link Expired.", show_alert=True)
    meta = url_store[unique_id]
    original_msg_id = meta.get('msg_id')

    if action == "warn_144":
        return await query.message.edit_text("⚠️ **Low Quality Warning!**\n📉 144p video may look blurry.\n\n👉 **Continue?**", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("✅ Yes", callback_data=f"144|{unique_id}")], [InlineKeyboardButton("❌ Back", callback_data=f"back|{unique_id}")]]))

    if action == "back":
        buttons = [
            [InlineKeyboardButton("🚀 4K (Ultra HD)", callback_data=f"2160|{unique_id}"), InlineKeyboardButton("🌟 2K (1440p)", callback_data=f"1440|{unique_id}")],
            [InlineKeyboardButton("🖥 1080p (Full HD)", callback_data=f"1080|{unique_id}"), InlineKeyboardButton("💻 720p (HD)", callback_data=f"720|{unique_id}")],
            [InlineKeyboardButton("📺 480p (Clear)", callback_data=f"480|{unique_id}"), InlineKeyboardButton("📱 360p (Best Mobile)", callback_data=f"360|{unique_id}")],
            [InlineKeyboardButton("📟 240p", callback_data=f"240|{unique_id}"), InlineKeyboardButton("📉 144p (Data Saver)", callback_data=f"warn_144|{unique_id}")],
            [InlineKeyboardButton("🎵 Audio Only (MP3)", callback_data=f"mp3|{unique_id}")]
        ]
        return await query.message.edit_text(f"🎬 **{meta['title']}**", reply_markup=InlineKeyboardMarkup(buttons))

    await query.message.delete()
    status_msg = await query.message.reply_text(f"⏳ **Initializing Download...**")
    
    filename = f"vid_{int(time.time())}"
    
    # 1. PRIMARY: Android Creator (Requires Nightly - The strongest bypass)
    opts_primary = {
        'format': 'bestaudio/best' if action == "mp3" else f'bestvideo[height<={action}]+bestaudio/best[height<={action}]/best',
        'outtmpl': f"{filename}.%(ext)s",
        'merge_output_format': 'mp4' if action != 'mp3' else None,
        'quiet': True,
        'cookiefile': None, # No cookies to force anonymous
        'extractor_args': {'youtube': {'player_client': ['android_creator', 'android']}},
        'writethumbnail': True
    }
    if action == 'mp3': opts_primary['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]

    # 2. FALLBACK: TV (Another strong bypass)
    opts_fallback = {
        'format': 'best' if action != 'mp3' else 'bestaudio/best',
        'outtmpl': f"{filename}.%(ext)s",
        'quiet': True,
        'cookiefile': None, 
        'extractor_args': {'youtube': {'player_client': ['tv', 'web_creator']}}, 
        'writethumbnail': True
    }
    if action == 'mp3': opts_fallback['postprocessors'] = [{'key': 'FFmpegExtractAudio','preferredcodec': 'mp3'}]

    final_file = None
    local_thumb = f"{filename}.jpg"
    
    try:
        await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts_primary).download([meta['url']]))
    except Exception as e:
        print(f"⚠️ Primary Failed. Switching to TV Bypass...")
        try:
            await asyncio.to_thread(lambda: yt_dlp.YoutubeDL(opts_fallback).download([meta['url']]))
        except Exception as e2:
            if query.message.chat.id == LOG_GROUP_ID:
                return await status_msg.edit_text(f"❌ **Technical Error:**\n`{e2}`")
            else:
                return await status_msg.edit_text("⚠️ **Bot is currently down for maintenance.**\n(Server is busy, please try again later.)")

    final_file = f"{filename}.mp3" if action == "mp3" else f"{filename}.mp4"
    if not os.path.exists(final_file) and action != 'mp3':
        if os.path.exists(f"{filename}.mkv"): final_file = f"{filename}.mkv"
        elif os.path.exists(f"{filename}.webm"): final_file = f"{filename}.webm"

    if final_file and os.path.exists(final_file):
        # STICKER AD (Caption Only)
        caption = f"✅ **{meta['title']}**\n📍 Quality: {action}\n\n📢 **Ad:** Check out our partner channels!\n\nDownloaded via @VelvetaYTDownloaderBot"
        
        donate_btns = InlineKeyboardMarkup([[InlineKeyboardButton("☕ Donate", url="https://buymeacoffee.com/VelvetaBots")]])
        
        method = app.send_audio if action == 'mp3' else app.send_video
        await method(
            query.message.chat.id, 
            final_file, 
            caption=caption, 
            thumb=local_thumb if os.path.exists(local_thumb) else None,
            reply_markup=donate_btns,
            reply_to_message_id=original_msg_id,
            progress=progress_bar,
            progress_args=(status_msg, time.time(), meta['title'], "Uploading")
        )
        await status_msg.delete()
    else:
        if query.message.chat.id == LOG_GROUP_ID: await status_msg.edit_text("❌ Error: File downloaded but not found.")
        else: await status_msg.edit_text("⚠️ **Bot is currently down for maintenance.**")

    for ext in ["mp4", "mp3", "mkv", "webm", "jpg", "webp"]:
        f = f"{filename}.{ext}"
        if os.path.exists(f): os.remove(f)

# --- 8. RUN BOT ---
if __name__ == "__main__":
    print("🚀 Bot Starting...")
    app.run()
    
