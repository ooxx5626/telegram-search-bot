from telegram import Update
from telegram.ext import ContextTypes, CommandHandler
from utils import auto_delete, get_bot_user_name, get_text_func

_ = get_text_func()

@auto_delete
def get_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    bot_user_name = get_bot_user_name(context.bot)
    help_text = _("`@%s @username keyword1 keyword2... page`   to search, samples: \n\n   `@%s `   all messages, page 1\n\n   `@%s * 2`   all messages, page 2; \n\n   `@%s weather 3`   keyword 'weather', page 3; \n\n   `@%s @Taosky weather 4`    keyword 'weather' from user 'Taosky', page 4\n") % (bot_user_name, bot_user_name, bot_user_name, bot_user_name, bot_user_name)
    sent_message = context.bot.send_message(update.effective_chat.id, text=help_text, disable_notification=True, parse_mode='Markdown')
    return sent_message

handler = CommandHandler('help', get_help)