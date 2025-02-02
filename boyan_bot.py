import io
import logging
import os
import sqlite3

import imagehash
from PIL import Image
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters
from telegram.ext.filters import ChatType

bot_token = os.environ['APIKEY']

if not os.path.exists("db"):
    os.mkdir("db")
hash_con = sqlite3.connect("db/hash_data.db")
settings_con = sqlite3.connect("db/settings.db")
user_con = sqlite3.connect("db/user_names.db")

hash_cur = hash_con.cursor()
settings_cur = settings_con.cursor()
user_cur = user_con.cursor()

hash_cur.execute(
    "CREATE TABLE IF NOT EXISTS hash_data(message_id NUMERIC, hash TEXT, user_id TEXT, chat_id NUMERIC, PRIMARY KEY (message_id, chat_id) )")
user_cur.execute(
    "CREATE TABLE IF NOT EXISTS user_name(user_id PRIMARY KEY, name TEXT)")
settings_cur.execute("CREATE TABLE IF NOT EXISTS chat_settings(chat_id NUMERIC PRIMARY KEY, settings TEXT)")

get_chat_text = "SELECT settings FROM chat_settings WHERE chat_id = ?;"
add_chat_text = "INSERT INTO chat_settings VALUES(?, ?) ON CONFLICT (chat_id) DO UPDATE SET settings = ?;"

get_bayans = """
SELECT SUM(message_count) AS total_collisions
FROM (
    SELECT user_id, hash, COUNT(message_id) AS message_count
    FROM hash_data
    WHERE chat_id = ?
    AND user_id = ?
    GROUP BY user_id, hash
    HAVING message_count > 1
) AS collisions
GROUP BY user_id
ORDER BY total_collisions DESC;
"""
get_bayans_stat = """
SELECT user_id, SUM(message_count) AS total_collisions
FROM (
    SELECT user_id, hash, COUNT(message_id) AS message_count
    FROM hash_data
    WHERE chat_id = ?
    GROUP BY user_id, hash
    HAVING message_count > 1
) AS collisions
GROUP BY user_id
ORDER BY total_collisions DESC;
"""

get_messages_for_hash = "SELECT message_id FROM hash_data WHERE hash = ? AND chat_id = ?;"
get_hash = "SELECT hash FROM hash_data WHERE message_id = ? AND chat_id = ?;"
get_messages_except_last = "SELECT message_id FROM hash_data WHERE hash = ? AND chat_id = ? AND message_id != ?;"
get_orig_message = "SELECT MIN(message_id) FROM hash_data where hash = ? AND chat_id = ?;"
add_hash = "INSERT OR IGNORE INTO hash_data VALUES(?, ?, ?, ?);"

get_user_name = "SELECT name FROM user_name WHERE user_id = ?;"
add_user_name = "INSERT OR REPLACE INTO user_name VALUES(?, ?);"

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


async def bayan_stat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    boyanist_message_list = []
    chat_id = update.effective_chat.id
    boyanist_message_data = hash_cur.execute(get_bayans_stat, [chat_id]).fetchall()
    list_message = "List of idiots:"
    boyanist_message_list.append(list_message)
    for boyanist_data in boyanist_message_data:
        print(boyanist_data)
        user_id = boyanist_data[0]
        user_name = user_cur.execute(get_user_name, [int(user_id)]).fetchone()
        logging.info(f'Boyans for {user_name}, {user_id}')
        if user_name is None:
            user_name = "Unknown User"
        else:
            user_name = user_name[0]
        boyanist_message_list.append(f"{user_name} posted {boyanist_data[1]} bayans")
    boyanist_message_text = '\n'.join(boyanist_message_list)
    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=boyanist_message_text)


async def bayan_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id

    count = hash_cur.execute(get_bayans, [chat_id, user_id]).fetchone()[0]
    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=f"U posted {count} bayans")


async def get_chat_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    await context.bot.send_message(chat_id=chat_id, text=f"chat id is {chat_id} and user id is  {user_id}")


async def set_repl_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reply_text = update.message.text[10:]
    settings_cur.execute(add_chat_text, [str(update.message.chat_id), reply_text, reply_text])
    settings_con.commit()
    logging.info(str(update.message.chat.id))
    chat_text = settings_cur.execute(get_chat_text, [update.message.chat.id]).fetchone()[0]
    logging.info(chat_text)
    await context.bot.send_message(chat_id=update.effective_chat.id, text="Reply is set to " + chat_text)


async def byayan_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    current_msg_id = update.message.message_id
    message_user_name = update.message.from_user.name
    logging.info(f'message id is {current_msg_id}')
    logging.info(f'user name is {message_user_name}')
    chat_id = str(update.message.chat.id)
    logging.info('message received from ' + chat_id)
    if update.message.video is None:
        new_file = await update.message.effective_attachment[-1].get_file()
    else:
        new_file = await update.message.video.thumbnail.get_file()
    f = io.BytesIO()
    await new_file.download_to_memory(f)
    image_hash = imagehash.dhash(Image.open(f))
    hash_key = str(image_hash)
    hash_cur.execute(add_hash, [current_msg_id, hash_key, user_id, chat_id])
    hash_con.commit()
    user_cur.execute(add_user_name, [user_id, message_user_name])
    user_con.commit()
    previous_messages = hash_cur.execute(get_messages_except_last, [hash_key, chat_id, current_msg_id]).fetchall()
    if previous_messages:
        try:
            chat_text = settings_cur.execute(get_chat_text, [chat_id]).fetchone()[0]
        except TypeError:
            chat_text = "Reply has been not set\nPlease use /set_reply to set custom reply message"
        formated_chat_id = chat_id[4:]
        orig_message_id = hash_cur.execute(get_orig_message, [hash_key, chat_id]).fetchone()[0]
        await context.bot.send_message(chat_id=chat_id,
                                       text=chat_text + f"\nHas been posted {len(previous_messages)} times\n Original post:\n"
                                                        f" https://t.me/c/{formated_chat_id}/{orig_message_id}",
                                       reply_to_message_id=current_msg_id)

async def get_all_messages_with_picture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.message.reply_to_message is None:
        await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                       text="Reply with this command to a picture")
        return

    orig_message_id = update.message.reply_to_message.message_id
    hash = hash_cur.execute(get_hash, [orig_message_id, chat_id]).fetchone()

    if hash is None:
        await context.bot.send_message(chat_id=chat_id,
                                       text="I don't see a fukin picture here, moron",
                                       reply_to_message_id=update.message.message_id)
    else:
        messages = hash_cur.execute(get_messages_for_hash, [hash[0], chat_id]).fetchall()
        boyans_message_list = []
        list_message = f"This image has been posted {len(messages)} times:"
        boyans_message_list.append(list_message)
        for message in messages:
            message_id = message[0]
            formated_chat_id = str(chat_id)[4:]
            boyans_message_list.append(f"\nhttps://t.me/c/{formated_chat_id}/{message_id}")
        boyans_message_text = '\n'.join(boyans_message_list)
        await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                       text=boyans_message_text)

if __name__ == '__main__':
    start_handler = CommandHandler('start', start)
    repl_text_handler = CommandHandler('set_reply', set_repl_text)
    chat_id_handler = CommandHandler('get_chat_id', get_chat_id)
    chat_all_bayans = CommandHandler('get_all_bayans', get_all_messages_with_picture)
    bayan_counter_handler = CommandHandler('bayan_count', bayan_count)
    bayan_stat = CommandHandler('bayan_stat', bayan_stat)
    import_handler_private = CommandHandler('import_hash_data', private_import_hash_data, (~ChatType.GROUPS))

    byayan_handler = MessageHandler(filters.PHOTO | filters.VIDEO, byayan_checker)

    application.add_handler(start_handler)
    application.add_handler(repl_text_handler)
    application.add_handler(chat_id_handler)
    application.add_handler(chat_all_bayans)
    application.add_handler(import_handler_private)
    application.add_handler(bayan_stat)
    application.add_handler(byayan_handler)
    application.add_handler(bayan_counter_handler)

    application.run_polling()
