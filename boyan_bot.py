import io
import json
import logging
import os
import re
import sqlite3
from zipfile import ZipFile

import imagehash
from PIL import Image
from telegram import Update
from telegram.constants import ChatMemberStatus
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from telegram.ext.filters import ChatType

bot_token = os.environ['APIKEY']

if not os.path.exists("db"):
    os.mkdir("db")
hash_con = sqlite3.connect("db/hash_data.db")
settings_con = sqlite3.connect("db/settings.db")

hash_cur = hash_con.cursor()
settings_cur = settings_con.cursor()

hash_cur.execute("CREATE TABLE IF NOT EXISTS hash_data(hash TEXT PRIMARY KEY, message_id NUMERIC)")
settings_cur.execute("CREATE TABLE IF NOT EXISTS chat_settings(chat_id NUMERIC PRIMARY KEY, settings TEXT)")

get_chat_text = "SELECT settings FROM chat_settings WHERE chat_id = ?;"
add_chat_text = "INSERT INTO chat_settings VALUES(?, ?) ON CONFLICT (chat_id) DO UPDATE SET settings = ?;"

get_hash = "SELECT * FROM hash_data WHERE hash = ?;"
add_hash = "INSERT INTO hash_data VALUES(?, ?) ON CONFLICT (hash) DO NOTHING;"

hash_data = {}
hash_length_data = {}


application = ApplicationBuilder().token(bot_token).build()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="I'm a BAYANIST PUNISHER! \nBEHOLD THE TERROR IN THEIR EYES!")


async def incorrect_import_hash_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="No data has been found. Please, attach result file from hash_importer script")


async def private_import_hash_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="Why do you need this, weirdo?")


async def import_hash_data(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    prev_message_id = update.message.id
    logging.info("IMPORT DATA CALLED")
    admins = await context.bot.get_chat_administrators(chat_id)
    print(admins)
    owner_was_found = bool('false')
    for admin in admins:
        print(f'user id {0}, user message id {1}', [admin.user.id, update.message.from_user.id])
        if admin.status is ChatMemberStatus.OWNER and admin.user.id == update.message.from_user.id:
            owner_was_found = bool('true')
            await context.bot.send_message(chat_id=chat_id, text="Data import has been started...",
                                           reply_to_message_id=prev_message_id)
            new_file = await update.message.document.get_file()
            f = io.BytesIO()
            await new_file.download_to_memory(f)
            with ZipFile(f) as json_data:
                hash_load = json.load(json_data.open('hash_data.json'))
            for k, v in hash_load.items():
                hash_cur.execute(add_hash, [k, v])
            hash_con.commit()
            logging.info("Number of imported records: " + str(len(hash_load)))
            await context.bot.send_message(chat_id=chat_id,
                                           text="Data import has been completed. \nAll bayanists will be punnished with misery!",
                                           reply_to_message_id=prev_message_id)
            break
    if not owner_was_found:
        await context.bot.send_message(chat_id=chat_id, text="Only owner can import data. Fuck off!",
                                       reply_to_message_id=prev_message_id)


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="chat id is " + str(chat_id))


async def set_repl_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_text = update.message.text[10:]
    settings_cur.execute(add_chat_text, [str(update.message.chat_id), reply_text, reply_text])
    settings_con.commit()
    logging.info(str(update.message.chat.id))
    chat_text = settings_cur.execute(get_chat_text, [update.message.chat.id]).fetchone()[0]
    logging.info(chat_text)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Reply is set to " + chat_text)


async def byayan_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    current_msg_id = update.message.message_id
    bayanist_username = update.message.from_user.username
    logging.info('message id is ' + str(current_msg_id))
    chat_id = str(update.message.chat.id)
    logging.info('message received from ' + chat_id)
    if update.message.video is None:
        new_file = await update.message.effective_attachment[-1].get_file()
    else:
        new_file = await update.message.video.thumbnail.get_file()
    f = io.BytesIO()
    await new_file.download_to_memory(f)
    image_hash = imagehash.dhash(Image.open(f))
    hash_key = str(image_hash) + '^' + chat_id
    stored_entity = hash_cur.execute(get_hash, [hash_key]).fetchone()
    if stored_entity is None:
        hash_cur.execute(add_hash, [hash_key, current_msg_id])
        hash_con.commit()
    else:
        try:
            chat_text = settings_cur.execute(get_chat_text, [update.message.chat.id]).fetchone()[0]
        except TypeError:
            chat_text = "Reply has been not set\nPlease use /set_reply to set custom reply message"
        stored_chat_id = stored_entity[0].split('^')[1][4:]
        stored_message_id = stored_entity[1]
        await context.bot.send_message(chat_id=update.effective_chat.id,
                                       text=chat_text + f"\nhttps://t.me/c/{stored_chat_id}/{stored_message_id}",
                                       reply_to_message_id=current_msg_id)


if __name__ == '__main__':
    start_handler = CommandHandler('start', start)
    repl_text_handler = CommandHandler('set_reply', set_repl_text)
    chat_id_handler = CommandHandler('get_chat_id', get_chat_id)
    import_handler_private = CommandHandler('import_hash_data', private_import_hash_data, (~ChatType.GROUPS))

    byayan_handler = MessageHandler(filters.PHOTO | filters.VIDEO, byayan_checker)
    import_handler = MessageHandler(
        filters.ChatType.GROUPS & filters.Document.ZIP & filters.CaptionRegex((re.compile(r'/import_hash_data'))),
        import_hash_data)
    incorrect_import_handler = MessageHandler(
        filters.ChatType.GROUPS & filters.Regex(re.compile(r'/import_hash_data')),
        incorrect_import_hash_data)

    application.add_handler(start_handler)
    application.add_handler(repl_text_handler)
    application.add_handler(chat_id_handler)
    application.add_handler(import_handler_private)
    application.add_handler(import_handler)
    application.add_handler(incorrect_import_handler)
    application.add_handler(byayan_handler)

    application.run_polling()
