import math
import re
import html
import os
from database import User, Message, Chat, DBSession
from sqlalchemy import func, or_, and_
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

STAR_PAGE_RE = re.compile(r'\* *(\d+)')
USER_STAR_PAGE_RE = re.compile(r'@(\S+) *\* *(\d+)')

def get_query_matches(query):
    if not query:
        return None, None, 1
    query = query.strip()
    # 使用預編譯的正則表達式
    if match := STAR_PAGE_RE.match(query):
        return None, None, int(match.group(1))
    if match := USER_STAR_PAGE_RE.match(query):
        return match.group(1), None, int(match.group(2))
    # 使用更高效的字符串操作
    parts = query.split()
    user = None
    page = 1
    if parts[-1].isdigit():
        page = int(parts[-1])
        parts = parts[:-1]
    if parts and parts[0].startswith('@'):
        user = parts[0][1:]
        parts = parts[1:]
    keywords = parts if parts else None
    return user, keywords, page


def search_messages(uname, keywords, page, filter_chats):
    with DBSession() as session:
        chat_ids = [chat[0] for chat in filter_chats]
        chat_titles = dict(filter_chats)
        # 基本查詢
        base_query = session.query(Message, User.fullname.label('user_fullname')).\
            join(User, Message.from_id == User.id).\
            filter(Message.from_chat.in_(chat_ids))
        # 用戶名和關鍵詞過濾
        filters = []
        if uname:
            filters.append(func.lower(User.fullname).contains(func.lower(uname)))
        if keywords:
            keyword_filters = [func.lower(Message.text).contains(func.lower(keyword)) for keyword in keywords]
            filters.append(or_(*keyword_filters))
        if filters:
            base_query = base_query.filter(and_(*filters))
        # 計算總數
        count = base_query.count()
        # 獲取分頁數據
        start = (page - 1) * SEARCH_PAGE_SIZE
        messages_data = base_query.order_by(Message.date.desc()).\
            offset(start).limit(SEARCH_PAGE_SIZE).all()
        messages = [{
            'id': message.id,
            'link': message.link,
            'text': f'[{message.type}] {message.text}' if message.type != 'text' else message.text,
            'date': message.date,
            'user': user_fullname,
            'chat': chat_titles[message.from_chat],
            'type': message.type
        } for message, user_fullname in messages_data if message.text]

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
