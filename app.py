import asyncio
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional
from web_server import start_web_server
import aiohttp
from aiogram import Bot, Dispatcher, Router, html
from aiogram.types import Message, BufferedInputFile, BotCommand
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from dotenv import load_dotenv
load_dotenv()
# ------------------- Configuration -------------------
API_TOKEN = os.getenv('BOT_TOKEN')
MAX_CONCURRENT_REQUESTS = 5 
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Using DefaultBotProperties for cleaner HTML parsing
bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)

# ------------------- Improved UID Extraction -------------------
async def extract_uid(session: aiohttp.ClientSession, link: str) -> Optional[str]:
    """Resolves redirects and extracts UID from meta tags or scripts."""
    if not link or not isinstance(link, str):
        return None

    clean_link = link.strip()
    if not clean_link.startswith("http"):
        clean_link = "https://" + clean_link

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Upgrade-Insecure-Requests": "1"
    }

    try:
        # 1. Resolve Redirection (Crucial for /share/ links)
        async with session.get(clean_link, headers=headers, timeout=15, allow_redirects=True) as resp:
            final_url = str(resp.url)
            html = await resp.text()

            # 2. Check if UID is in the final URL (e.g., profile.php?id=...)
            url_match = re.search(r"(?:profile\.php\?id=|facebook\.com/|fb://profile/)(\d+)", final_url)
            if url_match:
                return url_match.group(1)

            # 3. Deep Scan HTML Source
            # We look for various ways FB stores IDs in the background
            patterns = [
                r'"userID":"(\d+)"',
                r'"authorID":"(\d+)"',
                r'"node_id":"(\d+)"',
                r'"entity_id":"(\d+)"',
                r'"delegate_page":\{"id":"(\d+)"\}',
                r'fb://profile/(\d+)',
                r'content="fb://profile/(\d+)"',
                r'"owning_profile_id":"(\d+)"'
            ]

            for p in patterns:
                match = re.search(p, html)
                if match:
                    return match.group(1)

    except Exception as e:
        logger.error(f"Error processing {link}: {e}")

    return None
# ------------------- Beautiful Progress Logic -------------------
async def process_json_data(data: List[Dict], message: Message):
    total = len(data)
    if total == 0: return []

    # Beautiful initial message
    progress_msg = await message.reply(
        "⚡ <b>Initialization...</b>\n"
        "<code>[░░░░░░░░░░░░░░░░░░░░] 0%</code>",
    )
    
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)
    results = []

    async with aiohttp.ClientSession() as session:
        async def task_wrapper(record):
            async with semaphore:
                username_val = record.get('username', '')
                if isinstance(username_val, str) and ("facebook.com" in username_val or "/share/" in username_val):
                    uid = await extract_uid(session, username_val)
                    if uid:
                        record['username'] = uid
                        return record
                    return None
                return record

        tasks = [task_wrapper(item.copy()) for item in data]
        
        for i, completed_task in enumerate(asyncio.as_completed(tasks), 1):
            res = await completed_task
            if res: results.append(res)

            if i % 5 == 0 or i == total:
                percent = int((i / total) * 100)
                filled = int(percent / 5)
                bar = "█" * filled + "░" * (20 - filled)
                
                try:
                    await progress_msg.edit_text(
                        f"🚀 <b>Processing Facebook Data</b>\n"
                        f"<code>[{bar}] {percent}%</code>\n\n"
                        f"📂 <b>Total:</b> {total}\n"
                        f"✅ <b>Extracted:</b> {len(results)}\n"
                        f"⏳ <b>Remaining:</b> {total - i}",
                    )
                except: pass

    await progress_msg.delete()
    return results

# ------------------- Professional Handlers -------------------
@router.message(Command("start"))
async def cmd_start(message: Message):
    welcome_text = (
        "✨ <b>Welcome to FB Data Manager</b> ✨\n\n"
        "I can extract Facebook UIDs from profile links within your JSON files.\n\n"
        "<b>How to use:</b>\n"
        "1️⃣ Upload your <code>.json</code> file.\n"
        "2️⃣ Reply to that file with <i>any text</i>.\n"
        "3️⃣ Wait for the processed file!\n\n"
        "🛡 <i>Status: System Online</i>"
    )
    await message.reply(welcome_text)

@router.message()
async def handle_reply_to_json(message: Message):
    if not message.reply_to_message or not message.reply_to_message.document:
        return

    doc = message.reply_to_message.document
    if not (doc.file_name.lower().endswith(".json") or doc.mime_type == "application/json"):
        return

    local_path = f"file_{message.from_user.id}.json"
    
    try:
        status_note = await message.answer("📥 <b>Downloading and parsing...</b>")
        file_info = await bot.get_file(doc.file_id)
        await bot.download_file(file_info.file_path, local_path)

        with open(local_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)

        if not isinstance(raw_data, list):
            return await message.reply("❌ <b>Format Error:</b> JSON must be a List <code>[]</code>.")

        await status_note.delete()
        processed_data = await process_json_data(raw_data, message)

        # Corrected Timestamp (UTC +6)
        tz_dhaka = timezone(timedelta(hours=6))
        ts = datetime.now(tz_dhaka).strftime("%d_%m_%Y_%H_%M_%S")
        out_filename = f"FB_Converted_{ts}.json"

        output_json = json.dumps(processed_data, indent=2, ensure_ascii=False)
        output_file = BufferedInputFile(output_json.encode('utf-8'), filename=out_filename)

        await message.answer_document(
            output_file, 
            caption=(
                "✅ <b>Extraction Complete!</b>\n\n"
                f"📊 <b>Results:</b> <code>{len(processed_data)}</code> valid records saved.\n"
                "⚠️ <i>Invalid links were automatically filtered out.</i>"
            )
        )
        
    except Exception as e:
        logger.exception(e)
        await message.reply(f"❌ <b>Error:</b>\n<code>{str(e)}</code>")
    finally:
        if os.path.exists(local_path):
            os.remove(local_path)

async def main():
    # Set bot commands
    await bot.set_my_commands([BotCommand(command="start", description="Restart the bot")])
    
    # Run Bot and Web Server concurrently
    await asyncio.gather(
        dp.start_polling(bot),
        start_web_server()
    )

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot stopped.")
