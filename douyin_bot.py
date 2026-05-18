#!/usr/bin/env python3
"""
Bot Telegram tải video Douyin không logo - dùng API bên thứ 3
"""

import os
import re
import logging
import asyncio
import tempfile

import requests
from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

# ─── CẤU HÌNH ────────────────────────────────────────────────────────────────
BOT_TOKEN = "8701813803:AAFpLhURyfdncYHKbdoTSaWsGD1veNPJueQ"
MAX_FILE_MB = 50
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DOUYIN_PATTERN = re.compile(
    r"https?://(v\.douyin\.com|www\.douyin\.com|vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com)[^\s]*",
    re.IGNORECASE,
)


def extract_url(text: str) -> str | None:
    match = DOUYIN_PATTERN.search(text)
    return match.group(0) if match else None


def get_video_url(url: str) -> tuple[str, str]:
    """
    Lấy link video không watermark qua API công khai.
    Trả về (video_url, title)
    """
    apis = [
        f"https://api.douyin.wtf/api?url={url}",
        f"https://www.tikwm.com/api/?url={url}&hd=1",
    ]

    for api in apis:
        try:
            r = requests.get(api, timeout=15, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
            data = r.json()

            # douyin.wtf format
            if data.get("code") == 0 or data.get("status") == "ok":
                video = (
                    data.get("data", {}).get("play") or
                    data.get("data", {}).get("wmplay") or
                    data.get("data", {}).get("video", {}).get("play_addr", {}).get("url_list", [None])[0]
                )
                title = data.get("data", {}).get("desc", "Video Douyin")
                if video:
                    return video, title

            # tikwm format
            if data.get("code") == 0 and data.get("data"):
                video = data["data"].get("play") or data["data"].get("wmplay")
                title = data["data"].get("title", "Video Douyin")
                if video:
                    return video, title

        except Exception as e:
            logger.error(f"API lỗi ({api}): {e}")
            continue

    raise Exception("Không thể lấy link video từ các API")


def download_file(video_url: str, output_path: str):
    """Tải file video về máy."""
    r = requests.get(video_url, stream=True, timeout=60, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://www.douyin.com/",
    })
    r.raise_for_status()
    with open(output_path, "wb") as f:
        for chunk in r.iter_content(chunk_size=8192):
            f.write(chunk)


# ─── HANDLERS ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Xin chào!* Tôi là bot tải video Douyin không logo.\n\n"
        "📌 Gửi link video Douyin hoặc TikTok, tôi sẽ tải về cho bạn!",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    url = extract_url(text)

    if not url:
        await update.message.reply_text(
            "❌ Không tìm thấy link Douyin/TikTok.\nVui lòng gửi đúng link video."
        )
        return

    status_msg = await update.message.reply_text("⏳ Đang xử lý link...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            loop = asyncio.get_event_loop()

            # Lấy link video
            await status_msg.edit_text("🔍 Đang lấy link video...")
            video_url, title = await loop.run_in_executor(None, get_video_url, url)

            # Tải video
            await status_msg.edit_text("⬇️ Đang tải video...")
            filepath = os.path.join(tmp_dir, "video.mp4")
            await loop.run_in_executor(None, download_file, video_url, filepath)

            # Kiểm tra dung lượng
            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if file_size_mb > MAX_FILE_MB:
                await status_msg.edit_text(
                    f"❌ Video quá lớn ({file_size_mb:.1f}MB). Giới hạn: {MAX_FILE_MB}MB."
                )
                return

            # Gửi video
            await status_msg.edit_text("📤 Đang gửi video...")
            with open(filepath, "rb") as vf:
                await update.message.reply_video(
                    video=vf,
                    caption=f"✅ {title[:200] if title else 'Video Douyin'}\n🤖 @Douyin85_Bot",
                    supports_streaming=True,
                )
            await status_msg.delete()
            logger.info(f"Gửi thành công: {url}")

        except Exception as e:
            logger.error(f"Lỗi: {e}")
            await status_msg.edit_text(
                "❌ Không thể tải video này.\n\n"
                "Có thể do:\n"
                "• Video riêng tư hoặc đã bị xóa\n"
                "• Link không hợp lệ\n"
                "• Thử lại sau vài phút"
            )


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("🤖 Bot đang chạy...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
