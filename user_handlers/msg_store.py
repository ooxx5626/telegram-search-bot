from telegram import Update
from telegram.ext import MessageHandler, ContextTypes, filters
from database import DBSession, Message, User, Chat

def insert_or_update_user(user_id, fullname, username):
    session = DBSession()
    target_user = session.query(User).get(user_id)
    if not target_user:
        new_user = User(id=user_id, fullname=fullname, username=username)
        session.add(new_user)
        session.commit()
    elif target_user.fullname != fullname or target_user.username != username:
        target_user.fullname = fullname
        target_user.username = username
        session.commit()
    session.close()

def update_chat(chat_id, title):
    session = DBSession()
    target_chat = session.query(Chat).get(chat_id)
    if target_chat and target_chat.title != title:
        target_chat.title = title
        session.commit()
    session.close()

def insert_message(msg_id, msg_link, msg_text, msg_video, msg_photo, msg_audio, msg_voice, msg_type, from_id, from_chat, date):
    new_msg = Message(
        id=msg_id,
        link=msg_link,
        text=msg_text,
        video=msg_video,
        photo=msg_photo,
        audio=msg_audio,
        voice=msg_voice,
        type=msg_type,
        category='',
        from_id=from_id,
        from_chat=from_chat,
        date=date
    )
    session = DBSession()
    session.add(new_msg)
    session.commit()
    session.close()

def update_message(from_chat, msg_id, msg_text):
    session = DBSession()
    session.query(Message) \
        .filter(Message.from_chat == from_chat) \
        .filter(Message.id == msg_id) \
        .update({"text": msg_text})
    session.commit()
    session.close()

async def store_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    session = DBSession()
    chat_ids = [chat.id for chat in session.query(Chat) if chat.enable]
    if update.effective_chat.id not in chat_ids:
        return

    if update.edited_message:
        if (update.edited_message.edit_date - update.edited_message.date).seconds > 120:
            return

        msg_text = update.edited_message.text or update.edited_message.caption or ''
        msg_id = update.edited_message.message_id
        chat_id = update.edited_message.chat.id

        update_message(chat_id, msg_id, msg_text)
        return

    if update.message.via_bot and update.message.via_bot.id == context.bot.id:
        return

    if update.message.sender_chat:
        user_id = from_id = update.message.sender_chat.id
        sender_fullname = update.message.sender_chat.title or ''
        sender_username = update.message.sender_chat.username or ''
    elif update.message.from_user:
        if update.message.from_user.is_bot:
            return
        user_id = from_id = update.message.from_user.id
        sender_fullname = update.message.from_user.full_name or ''
        sender_username = update.message.from_user.username or ''
    else:
        return

    msg_id = update.message.message_id
    msg_link = update.message.link
    chat_id = update.message.chat.id
    chat_title = update.message.chat.title

    msg_photo = msg_video = msg_audio = msg_text = msg_voice = ''
    if update.message.photo:
        photo_sizes = [photo_size_info.file_size for photo_size_info in update.message.photo]
        msg_photo = update.message.photo[photo_sizes.index(max(photo_sizes))].file_id
        msg_text = update.message.caption or ''
        msg_type = 'photo'
    elif update.message.video:
        msg_video = update.message.video.file_id
        msg_text = update.message.caption or ''
        msg_type = 'video'
    elif update.message.audio:
        msg_audio = update.message.audio.file_id
        msg_text = update.message.caption or ''
        msg_type = 'audio'
    elif update.message.voice:
        msg_voice = update.message.voice.file_id
        msg_type = 'voice'
    elif update.message.text:
        msg_text = update.message.text
        msg_type = 'text'
    else:
        msg_type = 'unknown'

    insert_message(msg_id, msg_link, msg_text, msg_video, msg_photo, msg_audio, msg_voice, msg_type, from_id, chat_id, update.message.date)
    insert_or_update_user(user_id, sender_fullname, sender_username)
    update_chat(chat_id, chat_title)

handler = MessageHandler(
    filters.TEXT | filters.VIDEO | filters.PHOTO | filters.AUDIO | filters.VOICE,
    store_message,
)
