from telegram.ext import Application, CommandHandler, MessageHandler, filters
from threading import Thread
import asyncio
import logging
import os
from user_handlers import bot_help, chat_start, chat_stop, chat_delete, chatid_get, msg_search, msg_store
from user_jobs.commands_set import set_bot_commands
from userbot import run_telethon
from utils import is_userbot_mode, get_text_func

logging.basicConfig(format='%(asctime)s - %(threadName)s - %(levelname)s - %(message)s',
                    level=logging.INFO)

_ = get_text_func()

bot_token = os.getenv('BOT_TOKEN')

# 創建 Application 實例
application = Application.builder().token(bot_token).build()

# 設置機器人命令
application.job_queue.run_once(set_bot_commands, 30)

# 處理用戶操作
application.add_handler(msg_search.handler)
application.add_handler(chat_start.handler)
application.add_handler(chat_stop.handler)
application.add_handler(chat_delete.handler)
application.add_handler(bot_help.handler)
application.add_handler(chatid_get.handler)
# 在非 userbot 模式下保存消息
if not is_userbot_mode():
    application.add_handler(msg_store.handler)

# Telethon 線程函數
def run_telethon_thread():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_telethon())

if __name__ == '__main__':
    # 運行 userbot
    if is_userbot_mode():
        telethon_thread = Thread(target=run_telethon_thread, name='Thread-userbot')
        telethon_thread.start()
        logging.info(_('userbot start...'))
    
    # Webhook / Polling
    mode_env = os.getenv("BOT_MODE")
    if mode_env == "webhook":
        url_path = os.getenv("URL_PATH")
        hook_url = os.getenv("HOOK_URL")
        application.run_webhook(listen='0.0.0.0',
                                port=9968,
                                url_path=url_path,
                                webhook_url=hook_url)
    else:
        application.run_polling()
    logging.info(_('robot start...'))