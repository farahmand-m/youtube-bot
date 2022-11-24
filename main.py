import enum
import functools
import logging
import mimetypes
import os

from pytimeparse.timeparse import timeparse
from telegram import ParseMode
from telegram.ext import CommandHandler, MessageHandler
from telegram.ext import ConversationHandler
from telegram.ext import Filters
from telegram.ext import Updater

import utils


class States(enum.IntEnum):
    WaitingForURL = 1
    WaitingForRequests = 2


videos = {}


def start(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text='👀 Send me the URL for the video.')
    return States.WaitingForURL


def download(update, context):
    context.bot.send_message(chat_id=update.effective_chat.id, text='📥 Downloading...')
    video, duration, thumbnail = utils.download(update.effective_message.text)
    if video is not None:
        videos[update.effective_chat.id] = video, duration
        text = f"📟 Got it! Now, send me a request.\nVideo Duration: {duration}"
        context.bot.send_photo(chat_id=update.effective_chat.id, photo=thumbnail, caption=text, parse_mode=ParseMode.HTML)
        return States.WaitingForRequests
    else:
        context.bot.send_message(chat_id=update.effective_chat.id, text='💀 Download failed. Try another URL.')


def process(update, context):
    chat_id = update.effective_chat.id
    video, duration = videos[chat_id]
    # Processing User's Input
    tokens = update.effective_message.text.split()
    if update.effective_message.text.startswith('-'):
        pairs = []
        dash, length, *gap = tokens
        length = timeparse(length)
        gap = timeparse(*gap) if gap else 5
        duration = duration.total_seconds()
        start = gap
        while (start + length) < duration:
            end = start + length
            pairs.append((start, end))
            start = end + gap
    else:
        start, *end = tokens
        start = timeparse(start)
        end = timeparse(*end) if end else start + 5
        pairs = [(start, end)]
    for start, end in pairs:
        filepath = utils.cut_out(video, chat_id, start, end)
        context.bot.send_message(chat_id=update.effective_chat.id, text='📤 Uploading...')
        with open(filepath, 'rb') as stream:
            context.bot.send_animation(chat_id=update.effective_chat.id, animation=stream)
    if len(pairs) > 1:
        context.bot.send_message(chat_id=update.effective_chat.id, text="✅ That's about it.")


def delete_current(update, context):
    chat_id = update.effective_chat.id
    video, duration = videos[chat_id]
    try:
        os.remove(video)
    except (OSError, PermissionError):
        pass  # Can't do anything about it.
    context.bot.send_message(chat_id=update.effective_chat.id, text='👀 Removed. Send a new link.')
    return States.WaitingForURL


def list_videos(update, context):
    filenames = []
    for filename in os.listdir('videos'):
        filetype, encoding = mimetypes.guess_type(f'videos/{filename}')
        if filetype is not None and filetype.startswith('video'):
            filenames.append(filename)
    text = "☑ Folder's Contents:\n" + '\n'.join(f'- <code>{filename}</code>' for filename in filenames)
    context.bot.send_message(chat_id=update.effective_chat.id, text=text, parse_mode=ParseMode.HTML)


def clean_videos(update, context):
    for filename in os.listdir('videos'):
        filetype, encoding = mimetypes.guess_type(f'videos/{filename}')
        if filetype is not None and filetype.startswith('video'):
            os.remove(f'videos/{filename}')
    context.bot.send_message(chat_id=update.effective_chat.id, text="☑ All gone!")


def error(update, context, message):
    context.bot.send_message(chat_id=update.effective_chat.id, text=f'❌ {message}')


conversation = ConversationHandler(
    entry_points=[
        CommandHandler('start', start),
    ],
    states={
        States.WaitingForURL: [
            MessageHandler(Filters.entity('url'), download),
            MessageHandler(~Filters.command, functools.partial(error, message='❌ Invalid URL!')),
        ],
        States.WaitingForRequests: [
            CommandHandler('done', delete_current),
            MessageHandler(Filters.text, process),
        ]
    },
    fallbacks=[
        CommandHandler('list', list_videos),
        CommandHandler('clean', clean_videos),
        MessageHandler(Filters.all, functools.partial(error, message='Unknown command!')),
    ],
    allow_reentry=True,
)


fallback = MessageHandler(Filters.all, functools.partial(error, message='Start the bot first!'))


if __name__ == '__main__':
    bot_token = os.environ.get('TOKEN')
    logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
    updater = Updater(bot_token, use_context=True)
    updater.dispatcher.add_handler(conversation)
    updater.dispatcher.add_handler(fallback)
    os.makedirs('videos', exist_ok=True)
    webhook_url = os.environ.get('WEBHOOK')
    if webhook_url is not None:
        updater.start_webhook(listen='0.0.0.0', port=8443, url_path=bot_token, webhook_url=f'{webhook_url}/{bot_token}')
    else:
        updater.start_polling()
    logging.info('Started pooling.')
    updater.idle()
