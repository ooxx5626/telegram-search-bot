import math
import re
import html
import os
from database import User, Message, Chat, DBSession
from sqlalchemy import or_, func
from sqlalchemy.orm import aliased
import telegram
from telegram import InlineQueryResultArticle, InputTextMessageContent, InlineQueryResultCachedSticker, Update
from telegram.ext import InlineQueryHandler, ContextTypes
from utils import get_filter_chats, is_userbot_mode, get_text_func
import logging
from functools import reduce

_ = get_text_func()

SEARCH_PAGE_SIZE = 25
CACHE_TIME = int(os.getenv('CACHE_TIME', 300))

def highlight_keywords(text, keywords):
    return reduce(lambda c, k: c.replace(k, f'<a href="">{html.escape(k)}</a>'), keywords, html.escape(text))

pattern = re.compile(r'^(?:\s*@(\S+))?\s*(?:([^*]+)\s*)?(?:\*\s*(\d+))?$')
def get_query_matches(query):
    if not query:
        return None, None, 1

    match = pattern.match(query)
    if match:
        user, keywords, page = match.groups()
        page = int(page) if page else 1
        keywords = keywords.split() if keywords else None
        return user, keywords, page

    # 如果正則表達式不匹配，則使用原來的邏輯
    keywords = query.split()
    user = None
    page = 1

    if keywords and keywords[-1].isdigit():
        page = int(keywords.pop())
    if keywords and keywords[0].startswith('@'):
        user = keywords.pop(0)[1:]
    
    keywords = keywords if keywords else None
    return user, keywords, page



def search_messages(uname, keywords, page, filter_chats):
    messages = []
    start = (page - 1) * SEARCH_PAGE_SIZE
    stop = page * SEARCH_PAGE_SIZE
    with DBSession() as session:
        chat_ids = [chat[0] for chat in filter_chats]
        chat_titles = dict(filter_chats)
        # 創建一個 User 別名來進行 JOIN
        UserAlias = aliased(User)
        query = session.query(Message, UserAlias)
        # 基本過濾
        query = query.filter(Message.from_chat.in_(chat_ids))
        # JOIN User 表
        query = query.join(UserAlias, Message.from_id == UserAlias.id)
        # 用戶名過濾
        if uname:
            query = query.filter(func.lower(UserAlias.fullname).contains(uname.lower()))
        # 關鍵詞過濾
        if keywords:
            keyword_filters = [func.lower(Message.text).contains(keyword.lower()) for keyword in keywords]
            query = query.filter(or_(*keyword_filters))
        # 計算總數
        count = query.count()
        # 獲取分頁數據
        messages_data = query.order_by(Message.date.desc()).slice(start, stop).all()
        for message, user in messages_data:
            msg_text = f'[{message.type}] {message.text}' if message.type != 'text' else message.text
            if msg_text:
                messages.append({
                    'id': message.id,
                    'link': message.link,
                    'text': msg_text,
                    'date': message.date,
                    'user': user.fullname,
                    'chat': chat_titles[message.from_chat],
                    'type': message.type
                })


    return messages, count

async def inline_caps(update: Update, context: ContextTypes.DEFAULT_TYPE):
    from_user_id = update.inline_query.from_user.id
    session = DBSession()
    chats = session.query(Chat)
    filter_chats = get_filter_chats(from_user_id) if is_userbot_mode() else []

    if not filter_chats:
        for chat in chats:
            if chat.enable:
                try:
                    chat_member = await context.bot.get_chat_member(chat_id=chat.id, user_id=from_user_id)
                    if chat_member.status not in ['left', 'kicked']:
                        filter_chats.append((chat.id, chat.title))
                except (telegram.error.BadRequest, telegram.error.Unauthorized):
                    continue

    query = update.inline_query.query
    user, keywords, page = get_query_matches(query)
    if not filter_chats:
        results = [InlineQueryResultCachedSticker(
            id=f'unauthorized_sticker_{i}',
            sticker_file_id='CAACAgUAAxkDAAEFBIhjffVfXIFyngE4vR2Zg_uDkDS41gACMAsAAoB48FdrYCP5TE3CEh4E'
        ) for i in range(20)]
        await context.bot.answer_inline_query(update.inline_query.id, results, cache_time=CACHE_TIME, is_personal=True)
        return

    messages, count = search_messages(user, keywords, page, filter_chats)

    if count == 0:
        results = [
            InlineQueryResultArticle(
                id='empty',
                title=_('No results found'),
                description=_('Attention! Do not click any buttons, otherwise an empty message will be sent'),
                input_message_content=InputTextMessageContent('⁤')
            )
        ]
    else:
        results = [
            InlineQueryResultArticle(
                id='info',
                title=f'Total:{count}. Page {page} of {math.ceil(count / SEARCH_PAGE_SIZE)}',
                description=_('Attention! This is just a prompt message, do not click on it, otherwise a /help message will be sent'),
                input_message_content=InputTextMessageContent(f'/help@{context.bot.username}')
            )
        ]

    for index, message in enumerate(messages):
        results.append(
            InlineQueryResultArticle(
                id=f'{message["id"]}_{index}',
                title=message['text'][:100],
                description=message['date'].strftime("%Y-%m-%d").ljust(40) + f"{message['user']}@{message['chat']}",
                input_message_content=InputTextMessageContent(
                    f'keywords:{",".join(keywords)}\\n「{highlight_keywords(message["text"], keywords)}」<a href="{message["link"]}">Via {message["user"]}</a>',
                    parse_mode='html'
                )
            )
        )
    await context.bot.answer_inline_query(update.inline_query.id, results, cache_time=CACHE_TIME, is_personal=True)

handler = InlineQueryHandler(inline_caps)
