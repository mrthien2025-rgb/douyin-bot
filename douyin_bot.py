#!/usr/bin/env python3
"""
Bot Telegram tải video Douyin/TikTok không logo
Yêu cầu: pip install python-telegram-bot yt-dlp requests
"""

import os
import re
import logging
import asyncio
import tempfile
from pathlib import Path

from telegram import Update, constants
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)
import yt_dlp

# ─── CẤU HÌNH ────────────────────────────────────────────────────────────────
BOT_TOKEN = "8701813803:AAFNh0w6ZIVoqkZ79Z0UQoJGdPfr8YKLnfA"
MAX_FILE_MB = 50                     # Giới hạn Telegram Bot API (MB)
# ──────────────────────────────────────────────────────────────────────────────

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

DOUYIN_PATTERN = re.compile(
    r"(https?://)?"
    r"(v\.douyin\.com|www\.douyin\.com|douyin\.com"
    r"|vm\.tiktok\.com|www\.tiktok\.com|tiktok\.com)"
    r"[^\s]*",
    re.IGNORECASE,
)


def extract_url(text: str) -> str | None:
    """Tìm link Douyin/TikTok trong tin nhắn."""
    match = DOUYIN_PATTERN.search(text)
    if not match:
        return None
    url = match.group(0)
    if not url.startswith("http"):
        url = "https://" + url
    return url


def download_video(url: str, output_dir: str) -> str:
    """
    Tải video không watermark bằng yt-dlp.
    Trả về đường dẫn file đã tải.
    """
    ydl_opts = {
        # Ưu tiên format không watermark (Douyin cung cấp stream riêng)
        "format": "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best",
        "outtmpl": os.path.join(output_dir, "%(id)s.%(ext)s"),
        "quiet": True,
        "no_warnings": True,
        "merge_output_format": "mp4",
        # Header giả lập trình duyệt để tránh bị chặn
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.douyin.com/",
        },
        # Extractor Douyin hỗ trợ tải video không logo
        "extractor_args": {
            "tiktok": {"webpage_download": ["1"]},
        },
        "postprocessors": [
            {
                "key": "FFmpegVideoConvertor",
                "preferedformat": "mp4",
            }
        ],
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Đảm bảo đuôi .mp4
        if not filename.endswith(".mp4"):
            filename = Path(filename).with_suffix(".mp4")
        return str(filename)


# ─── HANDLERS ────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Xin chào!* Tôi là bot tải video Douyin không logo.\n\n"
        "📌 Cách dùng:\n"
        "Gửi link video Douyin hoặc TikTok, tôi sẽ tải và gửi lại cho bạn.\n\n"
        "✅ Hỗ trợ:\n"
        "• douyin.com\n"
        "• v.douyin.com (link rút gọn)\n"
        "• tiktok.com\n"
        "• vm.tiktok.com",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 *Hướng dẫn sử dụng*\n\n"
        "1. Mở app Douyin/TikTok\n"
        "2. Chọn video → Chia sẻ → Sao chép link\n"
        "3. Dán link vào đây và gửi\n"
        "4. Chờ vài giây, bot sẽ gửi video không logo!\n\n"
        "⚠️ *Lưu ý:*\n"
        "• Video tối đa 50MB\n"
        "• Chỉ hỗ trợ video công khai\n"
        "• Không hỗ trợ live stream",
        parse_mode=constants.ParseMode.MARKDOWN,
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text or ""
    url = extract_url(text)

    if not url:
        await update.message.reply_text(
            "❌ Không tìm thấy link Douyin/TikTok.\n"
            "Vui lòng gửi đúng link video."
        )
        return

    status_msg = await update.message.reply_text("⏳ Đang tải video, vui lòng chờ...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        try:
            loop = asyncio.get_event_loop()
            filepath = await loop.run_in_executor(
                None, download_video, url, tmp_dir
            )

            file_size_mb = os.path.getsize(filepath) / (1024 * 1024)
            if file_size_mb > MAX_FILE_MB:
                await status_msg.edit_text(
                    f"❌ Video quá lớn ({file_size_mb:.1f}MB).\n"
                    f"Giới hạn cho phép: {MAX_FILE_MB}MB."
                )
                return

            await status_msg.edit_text("📤 Đang gửi video...")
            with open(filepath, "rb") as video_file:
                await update.message.reply_video(
                    video=video_file,
                    caption="✅ Video không logo từ Douyin\n🤖 @Douyin85_Bot",
                    supports_streaming=True,
                )
            await status_msg.delete()
            logger.info(f"Đã gửi video thành công: {url}")

        except yt_dlp.utils.DownloadError as e:
            logger.error(f"Lỗi tải video: {e}")
            await status_msg.edit_text(
                "❌ Không thể tải video này.\n\n"
                "Nguyên nhân có thể:\n"
                "• Video đã bị xóa hoặc riêng tư\n"
                "• Link không hợp lệ\n"
                "• Video bị giới hạn khu vực"
            )
        except Exception as e:
            logger.error(f"Lỗi không xác định: {e}")
            await status_msg.edit_text(
                "❌ Đã xảy ra lỗi. Vui lòng thử lại sau."
            )


# ─── MAIN ────────────────────────────────────────────────────────────────────

def main():
    if BOT_TOKEN == "YOUR_BOT_TOKEN_HERE":
        raise ValueError("⚠️  Vui lòng điền BOT_TOKEN vào file trước khi chạy!")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    logger.info("🤖 Bot đang chạy... Nhấn Ctrl+C để dừng.")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
