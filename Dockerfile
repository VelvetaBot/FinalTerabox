FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY bot.py .
RUN mkdir -p downloads

CMD ["python", "bot.py"]
```

---

## 🚀 Deploy Steps:

1. GitHub లో కొత్త repository create చేయండి: `terabox-downloader-bot`
2. ఈ files add చేయండి:
   - bot.py (artifact నుండి)
   - requirements.txt
   - Dockerfile
3. Koyeb లో deploy చేయండి
4. Environment variable: `BOT_TOKEN`

---

## 🎯 Bot Usage:
```
User: /start
Bot: [Welcome message with instructions]

User: [Sends TeraBox link]
Bot: 🔍 Processing...

Bot: ✅ File Found!
     📁 Movie.mp4
     📦 Size: 450.5MB
     [Download Button]

User: [Clicks Download]
Bot: ⬇️ Downloading... [Progress bar]
Bot: ⬆️ Uploading...
Bot: [Sends file]
Bot: ✅ Download Complete! 🎉
