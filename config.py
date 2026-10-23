import os
import shutil
from pathlib import Path
from dotenv import load_dotenv

# .env faylini yuklash
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OWNER_ID = int(os.getenv("OWNER_ID", "5246830744"))
DOWNLOAD_DIR = BASE_DIR / os.getenv("DOWNLOAD_DIR", "downloads")
MAX_FILE_SIZE_MB = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
DATABASE_PATH = BASE_DIR / "bot.db"

# Yuklab olish papkasi mavjudligini ta'minlash
DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)

# FFmpeg yo'lini aniqlash
FFMPEG_PATH = shutil.which("ffmpeg")
if not FFMPEG_PATH:
    try:
        import imageio_ffmpeg
        FFMPEG_PATH = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        FFMPEG_PATH = "ffmpeg"
