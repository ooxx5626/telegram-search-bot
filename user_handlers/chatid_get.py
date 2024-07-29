from telegram import Update
from telegram.ext import CommandHandler, ContextTypes
from utils import auto_delete

@auto_delete
async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    sent_message = await context.bot.send_message(
        chat_id=update.effective_chat.id,
        text=str(update.effective_chat.id)
    )
    return sent_message

handler = CommandHandler('chat_id', get_chat_id)
