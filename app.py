#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
PUBG YouTube Shorts Bot - PREMIUM VERSIYA
Version: 9.4 - TO'LIQ ISHLAYDI
"""

import os
import sys
import time
import asyncio
import random
import threading
import logging
import subprocess
import traceback
import json
import re
from pathlib import Path
from datetime import datetime
from queue import Queue

# ============================================
# PAKETLAR TEKSHIRUVI
# ============================================

missing = []

try:
    import yt_dlp
except ImportError:
    missing.append("yt-dlp")

try:
    import schedule
except ImportError:
    missing.append("schedule")

try:
    from flask import Flask, jsonify, render_template, request
    from flask_cors import CORS
except ImportError:
    missing.append("flask flask-cors")

try:
    import edge_tts
except ImportError:
    missing.append("edge-tts")

if missing:
    print("❌ Quyidagi paketlar o'rnatilmagan:")
    for m in missing:
        print(f"   pip install {m}")
    print("\nBarini o'rnatish:")
    print(
        "pip install yt-dlp schedule flask flask-cors edge-tts groq google-api-python-client google-auth-httplib2 google-auth-oauthlib python-dotenv")
    sys.exit(1)

try:
    from groq import Groq

    GROQ_AVAILABLE = True
except ImportError:
    GROQ_AVAILABLE = False
    print("⚠️ groq yo'q - fallback mavzular ishlatiladi")

try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaFileUpload

    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("⚠️ google-api yo'q - YouTube upload ishlamaydi")

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    pass

# ============================================
# KONFIGURATSIYA
# ============================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REFRESH_TOKEN = os.getenv("GOOGLE_REFRESH_TOKEN")
BASE_DIR = Path(__file__).parent
OUTPUT_DIR = BASE_DIR / "output"
LOGS_DIR = BASE_DIR / "logs"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

for folder in [OUTPUT_DIR, LOGS_DIR, TEMPLATES_DIR, STATIC_DIR]:
    folder.mkdir(parents=True, exist_ok=True)

# ============================================
# LOGGING - Thread safe
# ============================================

log_lock = threading.Lock()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOGS_DIR / 'bot.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)


# ============================================
# FFMPEG TEKSHIRUVI
# ============================================

def check_ffmpeg():
    try:
        r = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=10
        )
        return r.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


FFMPEG_AVAILABLE = check_ffmpeg()

if not FFMPEG_AVAILABLE:
    logger.warning("⚠️ ffmpeg topilmadi!")
    logger.warning("Windows: https://ffmpeg.org/download.html dan yuklab, PATH ga qo'shing")
    logger.warning("Linux: sudo apt install ffmpeg")

# ============================================
# FLASK APP
# ============================================

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
app.secret_key = os.urandom(24).hex()
CORS(app)

bot_status = {
    "status": "idle",
    "message": "Bot ishga tayyor ✅",
    "mode": "auto",
    "total_videos": 0,
    "last_video_url": None,
    "last_run": None,
    "next_run": "09:00",
    "logs": [],
    "progress": 0,
    "current_topic": "",
    "queue_size": 0,
    "topics_generated": 0,
    "errors": []
}

video_queue = Queue()

# ============================================
# 1. MAVZU YARATISH (AI)
# ============================================

TOPIC_TEMPLATES = [
    "How to {} in PUBG Mobile",
    "Best {} tips for beginners",
    "Secret {} strategy revealed",
    "Pro {} guide 2026",
    "Top 3 {} mistakes to avoid",
    "Master {} like a pro",
    "Ultimate {} tutorial",
    "5 unknown {} tips",
    "Complete {} guide",
    "Insane {} tricks"
]

CONTENT_TYPES = [
    "improve your aim", "landing spots", "weapon attachments",
    "sensitivity settings", "close combat", "sniper shots",
    "vehicle driving", "grenade throws", "loot locations",
    "rotation strategies", "camping spots", "aggressive gameplay",
    "passive gameplay", "squad coordination", "solo vs squad",
    "recoil control", "headshots", "movement techniques",
    "peeking tactics", "M416", "AKM", "SCAR-L", "UZI",
    "Vector", "SKS", "Kar98k", "AWM", "Erangel map",
    "Miramar desert", "Sanhok jungle", "Vikendi snow",
    "Livik island", "compensator usage", "suppressor tips",
    "extended mag", "vertical grip", "thumb grip benefits"
]

used_topics = []
used_topics_max = 100


def generate_unique_topic(max_retries=5):
    """UNIQUE mavzu yaratish"""
    global used_topics

    for attempt in range(max_retries):
        topic = None

        if GROQ_AVAILABLE and GROQ_API_KEY:
            try:
                client = Groq(api_key=GROQ_API_KEY)
                prompts = [
                    "Generate ONE unique PUBG Mobile tips video topic. Return ONLY the topic, nothing else. Be creative and specific.",
                    "Create ONE original PUBG gameplay tutorial topic. Return ONLY topic name. Make it interesting.",
                    "Invent ONE catchy PUBG tips title. Return ONLY title, no explanation. Focus on specific weapons or maps.",
                ]
                completion = client.chat.completions.create(
                    model="mixtral-8x7b-32768",
                    messages=[
                        {"role": "system", "content": "You are a PUBG expert. Generate unique, specific video topics."},
                        {"role": "user", "content": random.choice(prompts)}
                    ],
                    temperature=1.0,
                    max_tokens=50
                )
                topic = completion.choices[0].message.content.strip()
                topic = topic.strip('"').strip("'").strip()
                if len(topic) < 8 or len(topic) > 100:
                    topic = None
            except Exception as e:
                logger.warning(f"Groq xato (urinish {attempt + 1}): {e}")
                topic = None

        if not topic:
            template = random.choice(TOPIC_TEMPLATES)
            content = random.choice(CONTENT_TYPES)
            extras = ["", " in 2026", " pro tips", " complete guide", " for beginners", " advanced"]
            topic = template.format(content) + random.choice(extras)

        if topic not in used_topics:
            used_topics.append(topic)
            if len(used_topics) > used_topics_max:
                used_topics.pop(0)
            bot_status["topics_generated"] += 1
            logger.info(f"🎯 AI yaratgan mavzu: {topic}")
            return topic

    return f"PUBG Mobile Pro Tips #{random.randint(100, 999)}"


# ============================================
# 2. SCRIPT YARATISH (AI)
# ============================================

def generate_unique_script(topic):
    """Mavzuga mos script yaratish"""
    if GROQ_AVAILABLE and GROQ_API_KEY:
        try:
            client = Groq(api_key=GROQ_API_KEY)
            styles = ["energetic", "professional", "funny", "dramatic", "casual", "exciting"]
            style = random.choice(styles)

            completion = client.chat.completions.create(
                model="mixtral-8x7b-32768",
                messages=[
                    {"role": "system",
                     "content": f"You are a professional PUBG YouTuber. Write a {style} 15-second video script about the topic. Make it engaging and call to action. Maximum 30 words."},
                    {"role": "user", "content": f"Write a script about: {topic}"}
                ],
                temperature=0.9,
                max_tokens=100
            )
            script = completion.choices[0].message.content.strip()
            if len(script) > 20:
                logger.info(f"📝 AI script: {script[:50]}...")
                return script
        except Exception as e:
            logger.warning(f"Groq script xato: {e}")

    templates = [
        f"Hey guys! Want to master {topic}? Here's the secret technique pros use! Watch till the end and subscribe!",
        f"This {topic} trick will change your game forever! Pro players don't want you to know this!",
        f"Stop losing in PUBG! Learn {topic} right now and start winning every game!",
        f"Insane {topic} tips revealed! This works every single time in PUBG Mobile!",
        f"Today I'll show you {topic}. This technique works 100% of the time!",
        f"Never seen before {topic} strategy! You won't believe how easy it is!",
    ]
    return random.choice(templates)


# ============================================
# 3. REAL VIDEO YUKLASH (PUBG Mobile gameplay)
# ============================================

def download_pubg_video(topic):
    """
    REAL PUBG Mobile video yuklash
    """
    uid = f"{int(time.time())}_{random.randint(100, 999)}"
    output_template = str(OUTPUT_DIR / f"pubg_{uid}.%(ext)s")

    # PUBG Mobile uchun maxsus qidiruv so'rovlari
    search_queries = [
        f"PUBG Mobile {topic} gameplay",
        f"PUBG Mobile {topic} highlights",
        "PUBG Mobile pro gameplay no commentary",
        "PUBG Mobile best moments 4k",
        "PUBG Mobile squad gameplay",
        "PUBG Mobile solo vs squad",
        "PUBG Mobile chicken dinner gameplay",
        "PUBG Mobile action gameplay",
        "PUBG Mobile ranked match gameplay",
        "PUBG Mobile tournament gameplay",
        "PUBG Mobile Livik gameplay",
        "PUBG Mobile Sanhok gameplay",
        "PUBG Mobile Miramar gameplay",
        "PUBG Mobile Erangel gameplay",
    ]

    # Bir necha marta urinish
    max_attempts = 5
    for attempt in range(max_attempts):
        search = random.choice(search_queries)
        logger.info(f"🔍 Urinish {attempt + 1}/{max_attempts}: {search}")

        ydl_opts = {
            'format': 'best[height<=720][ext=mp4]/best[height<=720]/best',
            'outtmpl': output_template,
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True,
            'socket_timeout': 30,
            'retries': 3,
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Ko'proq video qidirish
                info = ydl.extract_info(f"ytsearch20:{search}", download=False)

                if not info or 'entries' not in info:
                    continue

                # Filtr: 20-300 soniya, PUBG Mobile bilan bog'liq
                candidates = []
                for v in info['entries']:
                    if not v or not isinstance(v, dict):
                        continue

                    dur = v.get('duration') or 0
                    title = v.get('title', '').lower()

                    # Filtr shartlari
                    if 20 < dur < 300:
                        if 'pubg mobile' in title or 'pubg' in title:
                            candidates.append(v)

                if candidates:
                    video = random.choice(candidates)
                    logger.info(f"📥 PUBG video topildi: {video.get('title', 'Unknown')[:100]}")

                    # Yuklash
                    ydl.download([video['webpage_url']])

                    # Yuklangan faylni topish
                    for ext in ['mp4', 'webm', 'mkv']:
                        candidate = OUTPUT_DIR / f"pubg_{uid}.{ext}"
                        if candidate.exists() and candidate.stat().st_size > 500000:  # 500KB dan katta
                            logger.info(f"✅ PUBG video yuklandi: {candidate.name}")
                            return str(candidate)

        except Exception as e:
            logger.error(f"Yuklash xatosi (urinish {attempt + 1}): {e}")
            continue

    logger.warning("⚠️ PUBG video topilmadi, fallback ishlatiladi")
    return None


# ============================================
# 4. FALLBACK VIDEO YARATISH (YANGI QO'SHILDI)
# ============================================

def create_fallback_video(duration=20):
    """Fallback video yaratish"""
    if not FFMPEG_AVAILABLE:
        logger.error("ffmpeg yo'q, fallback video yaratib bo'lmaydi")
        return None

    uid = int(time.time())
    video_path = OUTPUT_DIR / f"fallback_{uid}.mp4"

    # PUBG style ranglar
    colors = ["0x1a1a2e", "0x16213e", "0x0f3460", "0x2c3e50", "0x1e3a5f"]
    color = random.choice(colors)

    cmd = [
        'ffmpeg', '-y',
        '-f', 'lavfi',
        '-i', f'color=c={color}:s=720x1280:d={duration}:r=30',
        '-c:v', 'libx264',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        '-t', str(duration),
        str(video_path)
    ]

    try:
        logger.info("🎨 Fallback video yaratilmoqda...")
        result = subprocess.run(cmd, capture_output=True, timeout=60)

        if result.returncode != 0:
            logger.error(f"FFmpeg xatosi: {result.stderr.decode()[:200]}")
            return None

        if video_path.exists() and video_path.stat().st_size > 1000:
            logger.info(f"✅ Fallback video yaratildi: {video_path.name}")
            return str(video_path)
        else:
            logger.error("Fallback video fayli yaratilmadi yoki juda kichik")
            return None

    except subprocess.TimeoutExpired:
        logger.error("Fallback video yaratish timeout")
        return None
    except Exception as e:
        logger.error(f"Fallback video xatosi: {e}")
        return None


# ============================================
# 5. VIDEOGA EFFEKTLAR QO'SHISH
# ============================================

def add_pubg_effects(video_path):
    """
    PUBG Mobile style effektlar
    - Yorqinlik, kontrast
    - Rang korreksiyasi
    - Vignette (qora ramka)
    - Sharpen (aniqlik)
    """
    if not FFMPEG_AVAILABLE:
        return video_path

    uid = int(time.time())
    effect_path = OUTPUT_DIR / f"effect_{uid}.mp4"

    # PUBG Mobile style effektlar (real o'yin uchun)
    effects = [
        # PUBG Mobile classic (slightly saturated, contrasty)
        "eq=brightness=0.03:contrast=1.3:saturation=1.2,unsharp=3:3:0.5",

        # PUBG Mobile vibrant (ranglar yorqin)
        "eq=brightness=0.02:contrast=1.2:saturation=1.4,curves=vintage",

        # PUBG Mobile cinematic (kino effekti)
        "colorbalance=rs=0.1:gs=0.05:bs=-0.1,eq=contrast=1.4:gamma=1.1",

        # PUBG Mobile action (harakat uchun)
        "eq=contrast=1.5:brightness=0.04:saturation=1.3,unsharp=5:5:1.0",

        # PUBG Mobile warm (issiq ranglar)
        "colorbalance=rs=0.15:gs=0.05:bs=-0.05,eq=contrast=1.2",

        # PUBG Mobile cool (sovuq ranglar - tunda)
        "colorbalance=rs=-0.1:gs=0.05:bs=0.2,eq=contrast=1.3",

        # PUBG Mobile HDR style
        "eq=contrast=1.4:brightness=0.05:saturation=1.2,curves=hdr",
    ]

    selected_effect = random.choice(effects)
    logger.info(f"🎨 Effekt qo'shilmoqda: {selected_effect[:50]}...")

    try:
        effect_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', selected_effect,
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            '-metadata', 'title=PUBG Mobile Gameplay',
            str(effect_path)
        ]

        result = subprocess.run(effect_cmd, capture_output=True, timeout=180, check=True)

        if effect_path.exists() and effect_path.stat().st_size > 1000:
            logger.info(f"✅ PUBG effekt qo'shildi")
            return str(effect_path)
        else:
            logger.warning("Effekt qo'shilgandan keyin fayl topilmadi")
            return video_path

    except Exception as e:
        logger.error(f"Effekt xatosi: {e}")
        return video_path


# ============================================
# 6. VIDEOGA TEXT QO'SHISH (PUBG STYLE)
# ============================================

def add_pubg_text(video_path, script_text):
    """
    PUBG style matn qo'shish
    - Oq rang, qora kontur
    - Pastki qismda
    - PUBG font style
    """
    if not FFMPEG_AVAILABLE:
        return video_path

    uid = int(time.time())
    text_path = OUTPUT_DIR / f"text_{uid}.mp4"

    try:
        # Scriptni qismlarga bo'lish
        words = script_text.split()
        lines = []

        if len(words) <= 8:
            lines = [script_text]
        else:
            part_size = len(words) // 3
            for i in range(0, len(words), part_size):
                lines.append(' '.join(words[i:i + part_size]))

        # PUBG style text filter
        text_filters = []
        y_positions = [1650, 1550, 1450]  # Pastki qism

        for idx, line in enumerate(lines[:3]):
            safe_line = line.replace("'", "\\'").replace('"', '\\"')

            # PUBG style: Oq rang, qora kontur, yarim shaffof fon
            text_filter = (
                f"drawtext=text='{safe_line}':"
                f"fontcolor=white:"
                f"fontsize=45:"
                f"borderw=3:"
                f"bordercolor=black:"
                f"x=(w-text_w)/2:"
                f"y={y_positions[idx]}:"
                f"box=1:"
                f"boxcolor=black@0.5:"
                f"boxborderw=15"
            )
            text_filters.append(text_filter)

        # Matn qo'shish
        text_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', ','.join(text_filters),
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            str(text_path)
        ]

        result = subprocess.run(text_cmd, capture_output=True, timeout=180, check=True)

        if text_path.exists() and text_path.stat().st_size > 1000:
            logger.info(f"✅ PUBG matn qo'shildi")
            return str(text_path)
        else:
            logger.warning("Matn qo'shilgandan keyin fayl topilmadi")
            return video_path

    except Exception as e:
        logger.error(f"Matn qo'shish xatosi: {e}")
        return video_path


# ============================================
# 7. TRANSITION EFFEKTLARI
# ============================================

def add_transitions(video_path, audio_duration):
    """Transition effektlari (fade in/out)"""
    if not FFMPEG_AVAILABLE:
        return video_path

    uid = int(time.time())
    transition_path = OUTPUT_DIR / f"transition_{uid}.mp4"

    try:
        transition_cmd = [
            'ffmpeg', '-y',
            '-i', video_path,
            '-vf', f'fade=t=in:st=0:d=1,fade=t=out:st={audio_duration - 1.5}:d=1.5',
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-crf', '23',
            '-pix_fmt', 'yuv420p',
            str(transition_path)
        ]

        result = subprocess.run(transition_cmd, capture_output=True, timeout=180, check=True)

        if transition_path.exists() and transition_path.stat().st_size > 1000:
            logger.info(f"✅ Transition qo'shildi")
            return str(transition_path)
        else:
            return video_path

    except Exception as e:
        logger.error(f"Transition xatosi: {e}")
        return video_path


# ============================================
# 8. OVOZ YARATISH (TUZATILGAN)
# ============================================

def create_audio_sync(text):
    """Matndan ovoz yaratish (ishlaydigan versiya)"""
    uid = f"{int(time.time())}_{random.randint(1000, 9999)}"
    audio_path = OUTPUT_DIR / f"voice_{uid}.mp3"

    voices = [
        "en-US-JennyNeural",  # Ayol ovozi (eng ishonchli)
        "en-US-ChristopherNeural",  # Erkak ovozi
        "en-US-GuyNeural",  # Erkak ovozi
        "en-GB-RyanNeural",  # Britaniya erkak
        "en-US-AriaNeural",  # Ayol ovozi
    ]

    print("\n🔊 Ovoz yozish boshlandi...")

    max_retries = 3
    for attempt in range(max_retries):
        voice = random.choice(voices)
        try:
            print(f"   • Urinish {attempt + 1}/{max_retries}: {voice}")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                communicate = edge_tts.Communicate(text, voice)
                loop.run_until_complete(communicate.save(str(audio_path)))

                if audio_path.exists() and audio_path.stat().st_size > 500:
                    print(f"   ✅ Ovoz tayyor: {audio_path.name}")
                    return str(audio_path)

            except Exception as e:
                print(f"   ❌ Ovoz xatosi: {e}")
            finally:
                loop.close()
                asyncio.set_event_loop(None)

            time.sleep(1)

        except Exception as e:
            print(f"   ❌ Kutilmagan xato: {e}")
            time.sleep(1)

    print("⚠️ Edge-TTS ishlamadi, sun'iy ovoz yaratilmoqda")
    return create_silent_audio()


def create_silent_audio():
    """Sun'iy ovoz (jim) yaratish"""
    uid = int(time.time())
    audio_path = OUTPUT_DIR / f"silent_{uid}.mp3"

    try:
        cmd = [
            'ffmpeg', '-y',
            '-f', 'lavfi',
            '-i', 'anullsrc=r=44100:cl=stereo',
            '-t', '15',
            '-c:a', 'libmp3lame',
            '-b:a', '128k',
            str(audio_path)
        ]

        result = subprocess.run(cmd, capture_output=True, timeout=10)

        if audio_path.exists() and audio_path.stat().st_size > 100:
            print(f"   ✅ Sun'iy ovoz yaratildi")
            return str(audio_path)
        else:
            print(f"   ❌ Sun'iy ovoz yaratilmadi")
            return None

    except Exception as e:
        print(f"   ❌ Sun'iy ovoz xatosi: {e}")
        return None


# ============================================
# 9. PROFESSIONAL MONTAJ
# ============================================

def create_premium_video(video_path, audio_path, script_text, topic):
    """PREMIUM MONTAJ"""
    if not FFMPEG_AVAILABLE:
        logger.error("ffmpeg yo'q!")
        return None

    temp_files = []
    current_video = video_path

    try:
        # Audio uzunligi
        audio_duration_cmd = [
            'ffprobe', '-v', 'error', '-show_entries',
            'format=duration', '-of', 'default=noprint_wrappers=1:nokey=1',
            audio_path
        ]
        audio_duration = float(subprocess.check_output(audio_duration_cmd).decode().strip())

        # 1. TRANSITION EFFEKTLARI
        logger.info("✨ Transition effektlari qo'shilmoqda...")
        transition_video = add_transitions(current_video, audio_duration)
        if transition_video != current_video:
            temp_files.append(transition_video)
            current_video = transition_video

        # 2. PUBG STYLE EFFEKTLAR
        logger.info("🎨 PUBG style effektlar qo'shilmoqda...")
        effect_video = add_pubg_effects(current_video)
        if effect_video != current_video:
            temp_files.append(effect_video)
            current_video = effect_video

        # 3. MATN QO'SHISH
        logger.info("📝 PUBG matn qo'shilmoqda...")
        text_video = add_pubg_text(current_video, script_text)
        if text_video != current_video:
            temp_files.append(text_video)
            current_video = text_video

        # 4. OVOZ QO'SHISH
        uid = int(time.time())
        output_path = OUTPUT_DIR / f"premium_{uid}.mp4"

        merge_cmd = [
            'ffmpeg', '-y',
            '-i', current_video,
            '-i', audio_path,
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-shortest',
            '-movflags', '+faststart',
            str(output_path)
        ]

        subprocess.run(merge_cmd, capture_output=True, timeout=180, check=True)

        # Tozalash
        for f in temp_files:
            if Path(f).exists():
                Path(f).unlink()

        if output_path.exists() and output_path.stat().st_size > 1000:
            logger.info(f"✅ PREMIUM VIDEO TAYYOR: {output_path.name}")
            return str(output_path)

        logger.error("Premium video yaratilmadi")
        return None

    except Exception as e:
        logger.error(f"Premium montaj xatosi: {e}")
        return None


# ============================================
# 10. ODDIY MONTAJ (FALLBACK)
# ============================================

def simple_merge_audio_video(video_path, audio_path):
    """Oddiy montaj"""
    if not FFMPEG_AVAILABLE:
        return None

    uid = int(time.time())
    output_path = OUTPUT_DIR / f"simple_{uid}.mp4"

    cmd = [
        'ffmpeg', '-y',
        '-i', video_path,
        '-i', audio_path,
        '-c:v', 'libx264',
        '-c:a', 'aac',
        '-shortest',
        '-preset', 'ultrafast',
        '-pix_fmt', 'yuv420p',
        str(output_path)
    ]

    try:
        subprocess.run(cmd, capture_output=True, timeout=180)
        return str(output_path) if output_path.exists() else None
    except Exception as e:
        logger.error(f"Oddiy montaj xatosi: {e}")
        return None


# ============================================
# YOUTUBE UPLOAD
# ============================================

def upload_to_youtube(video_path, title, description):
    """YouTube'ga yuklash"""
    if not GOOGLE_AVAILABLE:
        url = f"https://youtube.com/shorts/demo_{int(time.time())}"
        logger.warning(f"Google API yo'q, demo URL: {url}")
        return url

    if not all([GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET, GOOGLE_REFRESH_TOKEN]):
        logger.warning("Google credentials to'liq emas")
        return f"https://youtube.com/shorts/noauth_{int(time.time())}"

    try:
        creds = Credentials(
            token=None,
            refresh_token=GOOGLE_REFRESH_TOKEN,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=GOOGLE_CLIENT_ID,
            client_secret=GOOGLE_CLIENT_SECRET,
            scopes=["https://www.googleapis.com/auth/youtube.upload"]
        )

        try:
            creds.refresh(Request())
            logger.info("✅ Google token yangilandi")
        except Exception as e:
            logger.error(f"Token refresh xato: {e}")
            return f"https://youtube.com/shorts/token_error_{int(time.time())}"

        youtube = build("youtube", "v3", credentials=creds)

        safe_title = title[:90].strip()

        body = {
            "snippet": {
                "title": f"{safe_title} 🔥 PUBG Mobile #Shorts",
                "description": f"{description}\n\n#PUBGMobile #Shorts #Gaming #PUBG #Tips",
                "tags": ["PUBG Mobile", "Shorts", "Gaming", "PUBG", "Tips"],
                "categoryId": "20"
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False
            }
        }

        media = MediaFileUpload(
            str(video_path),
            mimetype='video/mp4',
            chunksize=1024 * 1024,
            resumable=True
        )

        request_obj = youtube.videos().insert(
            part="snippet,status",
            body=body,
            media_body=media
        )

        response = None
        retry = 0
        while response is None:
            try:
                status, response = request_obj.next_chunk()
                if status:
                    pct = int(status.progress() * 100)
                    logger.info(f"YouTube: {pct}% yuklandi")
            except Exception as chunk_e:
                retry += 1
                if retry > 5:
                    logger.error("YouTube chunk xato, to'xtaldi")
                    break
                logger.warning(f"Chunk urinish {retry}: {chunk_e}")
                time.sleep(3)

        if response and 'id' in response:
            url = f"https://www.youtube.com/shorts/{response['id']}"
            logger.info(f"✅ YouTube: {url}")
            return url

        logger.error("YouTube response noto'g'ri")
        return f"https://youtube.com/shorts/upload_failed_{int(time.time())}"

    except Exception as e:
        logger.error(f"YouTube upload xato: {e}")
        return f"https://youtube.com/shorts/error_{int(time.time())}"


# ============================================
# STATUS YANGILASH
# ============================================

def update_status(message, status="working", progress=None, topic=None):
    with log_lock:
        bot_status["message"] = message
        bot_status["status"] = status
        if progress is not None:
            bot_status["progress"] = progress
        if topic:
            bot_status["current_topic"] = topic
        ts = datetime.now().strftime("%H:%M:%S")
        bot_status["logs"].insert(0, f"[{ts}] {message}")
        bot_status["logs"] = bot_status["logs"][:50]
    logger.info(message)


# ============================================
# ASOSIY JARAYON
# ============================================

def process_video():
    """Premium video yaratish"""
    files_to_clean = []

    try:
        update_status("🔄 Jarayon boshlandi...", status="working", progress=5)

        # 1. MAVZU YARATISH
        update_status("🎯 AI mavzu yaratmoqda...", progress=10)
        topic = generate_unique_topic()
        update_status(f"📌 Mavzu: {topic}", progress=15, topic=topic)
        time.sleep(0.5)

        # 2. SCRIPT YARATISH
        update_status("📝 AI script yozmoqda...", progress=20)
        script = generate_unique_script(topic)
        update_status("✅ Script tayyor", progress=25)
        time.sleep(0.5)

        # 3. OVOZ YARATISH
        update_status("🎙️ Ovoz yozilmoqda...", progress=30)
        audio_path = create_audio_sync(script)
        if not audio_path:
            update_status("⚠️ Ovoz yaratilmadi! Sun'iy ovoz ishlatiladi.", progress=30)
            audio_path = create_silent_audio()
            if not audio_path:
                update_status("❌ Ovoz yaratilmadi!", status="error", progress=0)
                return
        files_to_clean.append(audio_path)
        update_status("✅ Ovoz tayyor", progress=40)
        time.sleep(0.5)

        # 4. REAL VIDEO YUKLASH
        update_status("🔍 PUBG Mobile video qidirilmoqda...", progress=50)
        video_path = download_pubg_video(topic)

        if not video_path:
            update_status("⚠️ PUBG video topilmadi, fallback video yaratilmoqda...", progress=55)
            video_path = create_fallback_video(duration=20)

        if not video_path:
            update_status("❌ Video topilmadi!", status="error", progress=0)
            return

        files_to_clean.append(video_path)
        update_status("✅ Video yuklandi", progress=60)
        time.sleep(0.5)

        # 5. PREMIUM MONTAJ
        update_status("✨ Premium montaj qilinmoqda...", progress=70)

        final_path = create_premium_video(video_path, audio_path, script, topic)

        if not final_path:
            logger.warning("⚠️ Premium montaj ishlamadi, oddiy montaj ishlatilmoqda")
            final_path = simple_merge_audio_video(video_path, audio_path)

        if not final_path:
            update_status("❌ Montaj muvaffaqiyatsiz!", status="error", progress=0)
            return

        files_to_clean.append(final_path)
        update_status("✅ Montaj tayyor", progress=90)
        time.sleep(0.5)

        # 6. YOUTUBE'GA YUKLASH
        update_status("📤 YouTube'ga yuklanmoqda...", progress=95)
        video_url = upload_to_youtube(
            final_path,
            f"{topic} 🔥 PUBG Tips",
            script
        )

        # 7. STATISTIKA
        bot_status["total_videos"] += 1
        bot_status["last_video_url"] = video_url
        bot_status["last_run"] = datetime.now().strftime("%H:%M")

        update_status(f"✅ Video tayyor! {video_url}", status="success", progress=100)

    except Exception as e:
        logger.error(f"Xato: {traceback.format_exc()}")
        update_status(f"❌ Xato: {str(e)[:50]}", status="error")

    finally:
        time.sleep(3)
        for f in files_to_clean:
            try:
                if Path(f).exists():
                    Path(f).unlink()
            except:
                pass
        time.sleep(1)
        update_status("🤖 Bot kutmoqda...", status="idle", progress=0)


# ============================================
# WORKER VA SCHEDULER
# ============================================

def worker():
    while True:
        try:
            if not video_queue.empty():
                func = video_queue.get(timeout=1)
                bot_status["queue_size"] = video_queue.qsize()
                try:
                    func()
                except Exception as e:
                    logger.error(f"Worker xato: {e}")
                finally:
                    video_queue.task_done()
                    bot_status["queue_size"] = video_queue.qsize()
        except:
            pass
        time.sleep(0.5)


def scheduled_job():
    if bot_status["mode"] == "auto":
        logger.info("⏰ Avtomatik video boshlandi")
        video_queue.put(process_video)
        bot_status["queue_size"] = video_queue.qsize()


def run_scheduler():
    import schedule
    schedule.every().day.at("09:00").do(scheduled_job)
    schedule.every().day.at("19:00").do(scheduled_job)

    while True:
        try:
            schedule.run_pending()
            jobs = schedule.get_jobs()
            if jobs:
                nxt = min(jobs, key=lambda j: j.next_run).next_run
                bot_status["next_run"] = nxt.strftime("%H:%M")
        except Exception as e:
            logger.error(f"Scheduler xato: {e}")
        time.sleep(30)


# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/status')
def api_status():
    bot_status["queue_size"] = video_queue.qsize()
    return jsonify(bot_status)


@app.route('/api/run', methods=['POST'])
def api_run():
    if bot_status["status"] == "working":
        return jsonify({"error": "Bot hozir ishlayapti, kuting!"}), 400
    if not FFMPEG_AVAILABLE:
        return jsonify({"error": "ffmpeg o'rnatilmagan!"}), 500
    video_queue.put(process_video)
    bot_status["queue_size"] = video_queue.qsize()
    return jsonify({"success": True})


@app.route('/api/mode/auto', methods=['POST'])
def set_auto():
    bot_status["mode"] = "auto"
    return jsonify({"success": True})


@app.route('/api/mode/manual', methods=['POST'])
def set_manual():
    bot_status["mode"] = "manual"
    return jsonify({"success": True})


@app.route('/api/topics')
def api_topics():
    topics = []
    for _ in range(10):
        topics.append(generate_unique_topic())
    return jsonify(topics)


@app.route('/api/check')
def api_check():
    return jsonify({
        "ffmpeg": FFMPEG_AVAILABLE,
        "groq": GROQ_AVAILABLE and bool(GROQ_API_KEY),
        "google": GOOGLE_AVAILABLE,
        "edge_tts": True,
        "output_writable": os.access(str(OUTPUT_DIR), os.W_OK)
    })


# ============================================
# HTML TEMPLATE
# ============================================

def create_html_template():
    HTML = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PUBG Premium Bot</title>
    <style>
        body{background:#1a1a2e;color:#fff;font-family:Arial;padding:20px}
        .container{max-width:800px;margin:0 auto;background:#16213e;padding:30px;border-radius:20px}
        h1{color:gold;text-align:center}
        .premium-badge{background:linear-gradient(135deg,#667eea,#764ba2);padding:5px 15px;border-radius:20px;display:inline-block;margin-bottom:15px}
        button{padding:10px 20px;margin:5px;border:none;border-radius:5px;cursor:pointer}
        .mode-auto{background:#ffab00}
        .mode-manual{background:#00d25b;color:#fff}
        .active{border:3px solid #fff}
        .run-btn{background:#667eea;color:#fff;font-size:20px;padding:15px;width:100%}
        .status{background:#0f3460;padding:20px;border-radius:10px;margin:20px 0}
        .topic{background:#1a1a2e;padding:10px;border-left:4px solid gold;margin:10px 0}
        .stats{display:grid;grid-template-columns:repeat(5,1fr);gap:10px;margin:20px 0}
        .stat{background:#0f3460;padding:10px;text-align:center}
        .number{font-size:24px;color:gold}
        .logs{background:#0f3460;padding:10px;max-height:200px;overflow-y:auto}
        .log{padding:3px;border-bottom:1px solid #333;font-family:monospace}
        .steps{display:grid;grid-template-columns:repeat(5,1fr);gap:5px;margin:10px 0;font-size:12px}
        .step{background:#1a1a2e;padding:5px;border-radius:5px;text-align:center}
    </style>
</head>
<body>
    <div class="container">
        <h1>🎮 PUBG Premium Bot</h1>
        <div class="premium-badge">✨ REAL PUBG GAMEPLAY ✨</div>

        <div class="steps">
            <div class="step">1️⃣ AI Mavzu</div>
            <div class="step">2️⃣ Real Video</div>
            <div class="step">3️⃣ PUBG Effektlar</div>
            <div class="step">4️⃣ Matn + Ovoz</div>
            <div class="step">5️⃣ YouTube</div>
        </div>

        <div>
            <button class="mode-auto active" id="autoBtn" onclick="setMode('auto')">⏰ Avto</button>
            <button class="mode-manual" id="manualBtn" onclick="setMode('manual')">🖱️ Qo'lda</button>
        </div>

        <button class="run-btn" onclick="runBot()" id="runBtn">🎬 VIDEO YARATISH</button>

        <div class="status">
            <div id="statusMsg">Bot ishga tayyor</div>
            <div class="topic" id="topicBox">Mavzu: --</div>
        </div>

        <div class="stats">
            <div class="stat"><div class="number" id="total">0</div>Jami</div>
            <div class="stat"><div class="number" id="topics">0</div>Mavzu</div>
            <div class="stat"><div class="number" id="last">--:--</div>Oxirgi</div>
            <div class="stat"><div class="number" id="next">09:00</div>Keyingi</div>
            <div class="stat"><div class="number" id="queue">0</div>Navbat</div>
        </div>

        <div id="videoLink"></div>

        <h3>📋 Jarayon loglari</h3>
        <div class="logs" id="logs"></div>
    </div>

    <script>
        function update(){
            fetch('/api/status').then(r=>r.json()).then(d=>{
                document.getElementById('statusMsg').innerHTML=d.message
                if(d.current_topic) document.getElementById('topicBox').innerHTML='Mavzu: '+d.current_topic
                document.getElementById('total').innerHTML=d.total_videos
                document.getElementById('topics').innerHTML=d.topics_generated
                document.getElementById('last').innerHTML=d.last_run||'--:--'
                document.getElementById('next').innerHTML=d.next_run||'09:00'
                document.getElementById('queue').innerHTML=d.queue_size

                let auto=document.getElementById('autoBtn')
                let manual=document.getElementById('manualBtn')
                if(d.mode=='auto'){auto.classList.add('active');manual.classList.remove('active')}
                else{manual.classList.add('active');auto.classList.remove('active')}

                document.getElementById('runBtn').disabled=(d.status=='working')
                if(d.logs) document.getElementById('logs').innerHTML=d.logs.map(l=>'<div class="log">'+l+'</div>').join('')
            })
        }
        function setMode(m){fetch('/api/mode/'+m,{method:'POST'}).then(()=>update())}
        function runBot(){fetch('/api/run',{method:'POST'})}
        setInterval(update,2000)
        update()
    </script>
</body>
</html>'''

    html_path = TEMPLATES_DIR / 'index.html'
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(HTML)
    logger.info(f"✅ HTML template: {html_path}")


# ============================================
# MAIN
# ============================================

def main():
    print("\n" + "=" * 70)
    print("🎮  PUBG AI BOT v9.4 — TO'LIQ ISHLAYDI")
    print("=" * 70)
    print(f"  🌐 Web: http://localhost:5000")
    print(f"  ⏰ Avtomatik: 09:00 va 19:00")
    print(f"\n  ✨ XUSUSIYATLAR:")
    print(f"  ✅ AI mavzu yaratish")
    print(f"  ✅ REAL PUBG Mobile video yuklash")
    print(f"  ✅ Fallback video (agar real video topilmasa)")
    print(f"  ✅ PUBG style effektlar (7 xil)")
    print(f"  ✅ Transition fade in/out")
    print(f"  ✅ PUBG style matn (oq rang, qora kontur)")
    print(f"  ✅ Ovoz tizimi (3 marta urinish + sun'iy ovoz)")
    print("=" * 70 + "\n")

    create_html_template()
    threading.Thread(target=worker, daemon=True).start()
    threading.Thread(target=run_scheduler, daemon=True).start()

    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)


if __name__ == "__main__":
    main()