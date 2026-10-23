import asyncio
import os
import re
import shutil
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional

import aiohttp
import yt_dlp
from config import DOWNLOAD_DIR, FFMPEG_PATH, MAX_FILE_SIZE_BYTES


class MediaResult:
    """Yuklab olingan media natijasi"""
    def __init__(self, task_dir: Path, files: List[Path], title: str = "", media_type: str = "video"):
        self.task_dir = task_dir
        self.files = files
        self.title = title
        self.media_type = media_type

    def cleanup(self):
        """Vaqtinchalik yuklangan fayllarni o'chirish"""
        try:
            if self.task_dir.exists():
                shutil.rmtree(self.task_dir, ignore_errors=True)
        except Exception as e:
            print(f"Tozalashda xatolik: {e}")


def _extract_and_download(url: str, task_dir: Path) -> Dict[str, Any]:
    """yt-dlp orqali sinxron yuklab olish funksiyasi (thread ichida ishlaydi)"""
    
    ydl_opts: Dict[str, Any] = {
        'outtmpl': str(task_dir / '%(autonumber)02d_%(title).40s_%(id)s.%(ext)s'),
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'max_filesize': MAX_FILE_SIZE_BYTES,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        # Formatni tanlash: Telegram 50MB limiti uchun optimal format
        'format': 'bestvideo[ext=mp4][filesize<=48M]+bestaudio[ext=m4a]/best[ext=mp4][filesize<=48M]/best[filesize<=48M]/best',
        'merge_output_format': 'mp4',
    }

    if FFMPEG_PATH:
        ydl_opts['ffmpeg_location'] = FFMPEG_PATH

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        return info


async def _download_pinterest_image_fallback(url: str, task_dir: Path) -> Optional[Path]:
    """Pinterest statik rasm pinlarini to'g'ridan-to'g'ri yuklab olish uchun zaxira usul"""
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    }
    async with aiohttp.ClientSession(headers=headers) as session:
        # Qisqa pin.it havolasi bo'lsa, yo'naltirish (redirect) orqali to'liq URLni olamiz
        async with session.get(url, allow_redirects=True) as resp:
            if resp.status != 200:
                return None
            html = await resp.text()

        # HTML ichidan yuqori sifatli rasm URLini qidirish
        # 1. og:image tegi
        og_match = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html)
        img_url = None
        if og_match:
            img_url = og_match.group(1)
        else:
            # 2. i.pinimg.com rasm havolasi
            pin_img_match = re.search(r'https://i\.pinimg\.com/(?:originals|\d+x)/[a-zA-Z0-9/_.\-]+\.(?:jpg|png|webp)', html)
            if pin_img_match:
                img_url = pin_img_match.group(0)

        if not img_url:
            return None

        # Rasmni original (eng yuqori sifat) variantiga almashtirish
        for size in ['/736x/', '/474x/', '/236x/', '/564x/']:
            if size in img_url:
                orig_candidate = img_url.replace(size, '/originals/')
                # Tekshirib ko'rish
                try:
                    async with session.get(orig_candidate) as orig_resp:
                        if orig_resp.status == 200:
                            img_path = task_dir / "pinterest_image.jpg"
                            img_path.write_bytes(await orig_resp.read())
                            return img_path
                except Exception:
                    pass

        # Agar originals bo'lmasa, topilgan URLni yuklash
        try:
            async with session.get(img_url) as direct_resp:
                if direct_resp.status == 200:
                    ext = img_url.split('.')[-1].split('?')[0] or 'jpg'
                    img_path = task_dir / f"pinterest_image.{ext}"
                    img_path.write_bytes(await direct_resp.read())
                    return img_path
        except Exception:
            pass

    return None


async def download_media(url: str) -> MediaResult:
    """
    Havola orqali video/rasm yuklab olish.
    TikTok, Instagram, YouTube, Pinterest va boshqa 1000+ saytlarni qo'llab-quvvatlaydi.
    """
    task_id = uuid.uuid4().hex
    task_dir = DOWNLOAD_DIR / task_id
    task_dir.mkdir(parents=True, exist_ok=True)

    try:
        info = None
        ytdl_error = None

        # 1-bosqich: yt-dlp orqali yuklab olishga urinish
        try:
            info = await asyncio.to_thread(_extract_and_download, url, task_dir)
        except Exception as e:
            ytdl_error = e

        # Yuklab olingan fayllarni tekshirish
        downloaded_files = [
            f for f in task_dir.iterdir()
            if f.is_file() and not f.name.endswith(('.temp', '.part', '.ytdl'))
        ]

        # 2-bosqich: Agar Pinterest bo'lsa va video topilmagan bo'lsa (rasm pini)
        is_pinterest = 'pinterest.com' in url or 'pin.it' in url
        if not downloaded_files and is_pinterest:
            fallback_img = await _download_pinterest_image_fallback(url, task_dir)
            if fallback_img and fallback_img.exists():
                downloaded_files.append(fallback_img)

        # 3-bosqich: Agar yt-dlp info qaytargan bo'lsa, lekin fayl saqlanmagan bo'lsa (masalan rasm yoki thumbnail)
        if not downloaded_files and isinstance(info, dict):
            url_candidate = info.get("url") or info.get("thumbnail")
            if url_candidate and any(url_candidate.endswith(ext) for ext in ['.jpg', '.jpeg', '.png', '.webp']):
                async with aiohttp.ClientSession() as session:
                    async with session.get(url_candidate) as resp:
                        if resp.status == 200:
                            img_path = task_dir / "image.jpg"
                            img_path.write_bytes(await resp.read())
                            downloaded_files.append(img_path)

        # Agar hali ham hech qanday fayl bo'lmasa, xatolik beramiz
        if not downloaded_files:
            if ytdl_error:
                raise ytdl_error
            raise FileNotFoundError("Hech qanday media fayl yuklab olinmadi.")

        title = ""
        if isinstance(info, dict):
            title = info.get("title", "") or ""

        # Media turini aniqlash
        all_images = all(f.suffix.lower() in ['.jpg', '.jpeg', '.png', '.webp'] for f in downloaded_files)
        media_type = "photo" if all_images else "video"

        # Fayllarni nomiga qarab saralash (karusel tartibida chiqishi uchun)
        downloaded_files.sort(key=lambda x: x.name)

        return MediaResult(
            task_dir=task_dir,
            files=downloaded_files,
            title=title,
            media_type=media_type
        )

    except Exception:
        # Xatolik yuz bersa, papkani tozalash
        shutil.rmtree(task_dir, ignore_errors=True)
        raise
