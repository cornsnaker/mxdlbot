import asyncio
import os
import logging
from aiogram import Bot, Dispatcher, Router, F, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from config import BOT_TOKEN, API_ID, API_HASH
import mx_engine

# Setup
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
router = Router()
dp.include_router(router)

# --- QUEUE SYSTEM ---
download_queue = asyncio.Queue()

# --- UTILS ---
def generate_progress_bar(percent):
    filled = int(percent // 10)
    bar = "▓" * filled + "░" * (10 - filled)
    return f"[{bar}] {percent:.1f}%"

# --- HANDLERS ---

@router.message(CommandStart())
async def cmd_start(message: types.Message):
    await message.answer(
        "👋 **Welcome to MX Advanced Bot**\n\n"
        "Send me an MX Player link (Episode or Movie).\n"
        "I support High-Speed Downloads, 1080p selection, and Batch processing.",
        parse_mode="Markdown"
    )

@router.message(F.text.contains("mxplayer.in"))
async def process_link(message: types.Message):
    status_msg = await message.answer("🔍 **Scraping Metadata...**")
    
    try:
        data = await mx_engine.get_metadata(message.text)
        if not data or not data.get('m3u8'):
            await status_msg.edit_text("❌ **Error:** Could not fetch metadata or DRM protected.")
            return

        # Build UI
        caption = (
            f"🎬 **{data['title']}**\n"
        )
        if not data['is_movie']:
            caption += f"📅 **Season:** {data['season']} | **Episode:** {data['episode']}\n"
            caption += f"📝 **Ep Title:** {data.get('episode_title', '')}\n"
        
        # Inline Keyboard
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="📺 1080p", callback_data=f"dl|1080|{message.text}"),
                InlineKeyboardButton(text="📺 720p", callback_data=f"dl|720|{message.text}"),
                InlineKeyboardButton(text="📺 480p", callback_data=f"dl|480|{message.text}")
            ],
            [InlineKeyboardButton(text="❌ Cancel", callback_data="cancel")]
        ])

        if data['image']:
            await message.answer_photo(photo=data['image'], caption=caption, reply_markup=kb, parse_mode="Markdown")
            await status_msg.delete()
        else:
            await status_msg.edit_text(caption, reply_markup=kb, parse_mode="Markdown")

    except Exception as e:
        await status_msg.edit_text(f"⚠️ Critical Error: {str(e)}")

@router.callback_query(F.data.startswith("dl|"))
async def callback_download(call: types.CallbackQuery):
    _, quality, url = call.data.split("|")
    
    await call.message.edit_reply_markup(reply_markup=None) # Remove buttons
    await call.message.answer(f"✅ **Added to Queue**\nDetails: {quality}p Quality")
    
    # Add to Queue
    await download_queue.put({
        "url": url,
        "quality": quality,
        "chat_id": call.message.chat.id,
        "msg_id": call.message.message_id
    })
    await call.answer()

# --- WORKER (The Engine) ---
async def worker():
    print("🚀 Worker started...")
    while True:
        task = await download_queue.get()
        chat_id = task["chat_id"]
        url = task["url"]
        
        # Notify User
        prog_msg = await bot.send_message(chat_id, "⬇️ **Starting Download...**")
        
        try:
            # 1. Scrape (Again, to be safe/fresh)
            meta = await mx_engine.get_metadata(url)
            clean_name = f"{meta['title']}_S{meta['season']}E{meta['episode']}" if not meta['is_movie'] else meta['title']
            clean_name = re.sub(r'[^a-zA-Z0-9]', '_', clean_name) # Sanitize

            # 2. Progress Hook
            last_edit_time = 0
            async def progress_hook(percent, raw_line):
                nonlocal last_edit_time
                # Update every 5 seconds to avoid FloodWait
                if asyncio.get_event_loop().time() - last_edit_time > 5:
                    try:
                        await prog_msg.edit_text(
                            f"⬇️ **Downloading {clean_name}**\n"
                            f"{generate_progress_bar(percent)}\n"
                            f"`{raw_line}`"
                        )
                        last_edit_time = asyncio.get_event_loop().time()
                    except: pass

            # 3. Execute Download
            if meta['m3u8']:
                file_path, success = await mx_engine.run_download(meta['m3u8'], clean_name, progress_hook)
                
                if success and os.path.exists(file_path):
                    await prog_msg.edit_text("⬆️ **Uploading to Telegram...**")
                    
                    # Upload
                    video = FSInputFile(file_path)
                    await bot.send_video(
                        chat_id, 
                        video, 
                        caption=f"✅ **Done:** {meta['title']}", 
                        supports_streaming=True
                    )
                    
                    # Cleanup
                    os.remove(file_path)
                    await prog_msg.delete()
                else:
                    await prog_msg.edit_text("❌ Download Failed. (DRM or Network Error)")
            else:
                await prog_msg.edit_text("❌ M3U8 Link Expired or Not Found.")

        except Exception as e:
            await bot.send_message(chat_id, f"⚠️ Task Failed: {e}")
        
        finally:
            download_queue.task_done()

# --- MAIN ---
async def main():
    # Start worker in background
    asyncio.create_task(worker())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
