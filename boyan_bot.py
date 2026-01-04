import io
import json
import logging
import os
import sqlite3
from transformers import AutoModelForImageClassification, AutoFeatureExtractor, AutoImageProcessor
import torch

import imagehash
from PIL import Image
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, filters

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

bot_token = os.environ['APIKEY']

user_list = json.loads(os.environ['USER_LIST'])


if not os.path.exists("db"):
    os.mkdir("db")
hash_con = sqlite3.connect("db/hash_data.db")
settings_con = sqlite3.connect("db/settings.db")
user_con = sqlite3.connect("db/user_names.db")
hash_ignore_con = sqlite3.connect("db/hash_ignore.db")


hash_cur = hash_con.cursor()
settings_cur = settings_con.cursor()
user_cur = user_con.cursor()
hash_ignore_cur = hash_ignore_con.cursor()

device = "cuda" if torch.cuda.is_available() else "cpu"
logging.info(f"Using device: {device}")

# 2. Load model and move it to the specific device
model = AutoModelForImageClassification.from_pretrained("legekka/AI-Anime-Image-Detector-ViT")
model.to(device) # <--- Critical step: Move model to GPU
model.eval()

# Load processor
# AutoFeatureExtractor is deprecated; AutoImageProcessor is the modern equivalent for ViT
processor = AutoImageProcessor.from_pretrained("legekka/AI-Anime-Image-Detector-ViT")

hash_cur.execute(
    "CREATE TABLE IF NOT EXISTS hash_data(message_id NUMERIC, hash TEXT, user_id TEXT, chat_id NUMERIC, is_not_original BOOLEAN, PRIMARY KEY (message_id, chat_id) )")
user_cur.execute(
    "CREATE TABLE IF NOT EXISTS user_name(user_id PRIMARY KEY, name TEXT)")

settings_cur.execute("CREATE TABLE IF NOT EXISTS chat_settings(chat_id NUMERIC PRIMARY KEY, settings TEXT)")

hash_ignore_cur.execute("CREATE TABLE IF NOT EXISTS hash_ignore(hash TEXT, chat_id NUMERIC, PRIMARY KEY (hash, chat_id))")

get_ignored_hashes_req = "SELECT hash FROM hash_ignore WHERE chat_id = ?;"
get_ignored_hash_req = "SELECT hash FROM hash_ignore WHERE chat_id = ? AND hash = ?;"

add_ignored_hash = "INSERT OR IGNORE INTO hash_ignore VALUES(?, ?);"
remove_ignored_hash = "DELETE FROM hash_ignore WHERE hash = ? and chat_id = ?;"

get_chat_text = "SELECT settings FROM chat_settings WHERE chat_id = ?;"
add_chat_text = "INSERT INTO chat_settings VALUES(?, ?) ON CONFLICT (chat_id) DO UPDATE SET settings = ?;"

get_bayans = """
SELECT COUNT(message_id) AS total_collisions
FROM hash_data
WHERE user_id = ?
AND chat_id = ?
AND is_not_original = TRUE
ORDER BY total_collisions DESC;
"""
get_bayans_stat = """
SELECT user_id, COUNT(message_id) AS total_collisions
FROM hash_data
WHERE chat_id = ?
AND is_not_original = TRUE
GROUP BY user_id
ORDER BY total_collisions DESC;
"""

get_messages_for_hash = "SELECT message_id FROM hash_data WHERE hash = ? AND chat_id = ? ORDER BY message_id ASC;"
get_hash = "SELECT hash FROM hash_data WHERE message_id = ? AND chat_id = ?;"
get_messages_except_last = "SELECT message_id FROM hash_data WHERE hash = ? AND chat_id = ? AND message_id != ?;"
get_orig_message = "SELECT message_id FROM hash_data where hash = ? AND chat_id = ? AND is_not_original = FALSE;"
add_hash = "INSERT OR IGNORE INTO hash_data VALUES(?, ?, ?, ?, (SELECT COUNT(message_id) FROM hash_data WHERE hash = ? AND chat_id = ? LIMIT 1));"

get_user_name = "SELECT name FROM user_name WHERE user_id = ?;"
add_user_name = "INSERT OR REPLACE INTO user_name VALUES(?, ?);"

hash_data = {}
hash_length_data = {}

application = ApplicationBuilder().token(bot_token).build()



async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_message(chat_id=update.effective_chat.id,
                                   text="I'm a BAYANIST PUNISHER! \nBEHOLD THE TERROR IN THEIR EYES!")


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

    count = hash_cur.execute(get_bayans, [user_id, chat_id]).fetchone()[0]
    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=f"U posted {count} bayans")

async def get_ignored_hashes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    image_hashes = hash_ignore_cur.execute(get_ignored_hashes_req, [chat_id]).fetchall()
    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=f"Ignored image hashes for this chat {image_hashes}")

async def get_image_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    orig_message_id = update.message.reply_to_message.message_id
    image_hash = hash_cur.execute(get_hash, [orig_message_id, chat_id]).fetchone()[0]
    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=f"Image hash is {image_hash}")

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
    hash_cur.execute(add_hash, [current_msg_id, hash_key, user_id, chat_id, hash_key, chat_id])
    hash_con.commit()
    user_cur.execute(add_user_name, [user_id, message_user_name])
    user_con.commit()
    ignored_hash = hash_ignore_cur.execute(get_ignored_hash_req, [chat_id, hash_key]).fetchone()
    if ignored_hash:
        return
    previous_messages = hash_cur.execute(get_messages_except_last, [hash_key, chat_id, current_msg_id]).fetchall()
    await evaluate_ai_slop(update, context)
    if previous_messages:
        try:
            chat_text = settings_cur.execute(get_chat_text, [chat_id]).fetchone()[0]
        except TypeError:
            chat_text = "Reply has been not set\nPlease use /set_reply to set custom reply message"
        formated_chat_id = chat_id[4:]
        boyans_message_list = []
        boyans_message_list.append("<blockquote expandable>")
        for message in previous_messages:
            message_id = message[0]
            boyans_message_list.append(f"https://t.me/c/{formated_chat_id}/{message_id}")
        boyans_message_list.append("</blockquote>")
        boyans_message_text = '\n'.join(boyans_message_list)

        await context.bot.send_message(chat_id=chat_id,
                                       text=f"{message_user_name}, {chat_text}\nHas been posted {len(previous_messages)} times\nPrevious posts:\n {boyans_message_text}",
                                       reply_to_message_id=current_msg_id, parse_mode=ParseMode.HTML)


async def get_all_messages_with_picture(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    if update.message.reply_to_message is None:
        await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                       text="Reply with this command to a picture")
        return

    orig_message_id = update.message.reply_to_message.message_id
    image_hash = hash_cur.execute(get_hash, [orig_message_id, chat_id]).fetchone()

    if image_hash is None:
        await context.bot.send_message(chat_id=chat_id,
                                       text="I don't see a fukin picture here, moron",
                                       reply_to_message_id=update.message.message_id)
    else:
        messages = hash_cur.execute(get_messages_for_hash, [image_hash[0], chat_id]).fetchall()
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


async def get_all_messages_with_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id

    image_hash = update.message.text.split(' ')[1]
    messages = hash_cur.execute(get_messages_for_hash, [image_hash, chat_id]).fetchall()

    if messages:
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
    else:
        await context.bot.send_message(chat_id=chat_id,
                                       text="There are no messages with this hash",
                                       reply_to_message_id=update.message.message_id)

async def ignore_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in user_list:
        return
    chat_id = update.message.chat_id
    image_hash = update.message.text.split(' ')[1]

    hash_ignore_cur.execute(add_ignored_hash, [image_hash, chat_id])
    hash_ignore_con.commit()
    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=f"Images with hash {image_hash} will be ignored")

async def unignore_hash(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in user_list:
        return
    chat_id = update.message.chat_id
    image_hash = update.message.text.split(' ')[1]

    hash_ignore_cur.execute(remove_ignored_hash, [image_hash, chat_id])
    hash_ignore_con.commit()
    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=f"Images with hash {image_hash} will not be ignored")

async def evaluate_ai_slop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    current_msg_id = update.message.message_id
    message_user_name = update.message.from_user.name
    logging.info(f'message id is {current_msg_id}')
    logging.info(f'user name is {message_user_name}')
    chat_id = str(update.message.chat.id)
    logging.info('message received from ' + chat_id)
    new_file = await update.message.effective_attachment[-1].get_file()
    f = io.BytesIO()
    await new_file.download_to_memory(f)
    image = Image.open(f).convert('RGB')

    # 3. Process image and move inputs to the same device as the model
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}  # <--- Critical step: Move inputs to GPU

    # Inference
    with torch.no_grad():  # Good practice to disable gradient calculation for inference
        outputs = model(**inputs)
        logits = outputs.logits

    # Post-processing (move back to CPU for printing/logic if needed)
    probs = torch.nn.functional.softmax(logits, dim=1)
    predicted_class_idx = torch.argmax(probs, dim=1).item()
    label = model.config.id2label[predicted_class_idx]
    confidence = probs[0][predicted_class_idx].item()

    logging.info(f"Prediction: {label} ({confidence:.2%})")
    if label == "ai":
        await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                   text=f"Is that fucking slop?\n{label} ({confidence:.2%})")

async def is_ai_slop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    orig_message_id = update.message.reply_to_message
    new_file = await orig_message_id.effective_attachment[-1].get_file()
    f = io.BytesIO()
    await new_file.download_to_memory(f)
    image = Image.open(f).convert('RGB')

    # 3. Process image and move inputs to the same device as the model
    inputs = processor(images=image, return_tensors="pt")
    inputs = {k: v.to(device) for k, v in inputs.items()}  # <--- Critical step: Move inputs to GPU

    # Inference
    with torch.no_grad():  # Good practice to disable gradient calculation for inference
        outputs = model(**inputs)
        logits = outputs.logits

    # Post-processing (move back to CPU for printing/logic if needed)
    probs = torch.nn.functional.softmax(logits, dim=1)
    predicted_class_idx = torch.argmax(probs, dim=1).item()
    label = model.config.id2label[predicted_class_idx]
    confidence = probs[0][predicted_class_idx].item()

    logging.info(f"Prediction: {label} ({confidence:.2%})")

    await context.bot.send_message(chat_id=chat_id, reply_to_message_id=update.message.id,
                                       text=f"Well... The answer is:\n{label} ({confidence:.2%})")


if __name__ == '__main__':
    start_handler = CommandHandler('start', start)
    repl_text_handler = CommandHandler('set_reply', set_repl_text)
    chat_id_handler = CommandHandler('get_chat_id', get_chat_id)
    chat_all_bayans = CommandHandler('get_all_bayans', get_all_messages_with_picture)
    bayan_counter_handler = CommandHandler('bayan_count', bayan_count)
    bayan_stat = CommandHandler('bayan_stat', bayan_stat)
    image_hash = CommandHandler('get_hash', get_image_hash)
    get_by_hash = CommandHandler('get_by_hash', get_all_messages_with_hash)
    get_ignored_hash_images = CommandHandler('get_ignored', get_ignored_hashes)
    is_ai_slop = CommandHandler('is_slop', is_ai_slop)
    ignore_hash_image = CommandHandler('ignore', ignore_hash)
    unignore_hash_image = CommandHandler('unignore', unignore_hash)


    byayan_handler = MessageHandler(filters.PHOTO | filters.VIDEO , byayan_checker)

    application.add_handler(get_ignored_hash_images)
    application.add_handler(ignore_hash_image)
    application.add_handler(unignore_hash_image)
    application.add_handler(get_by_hash)
    application.add_handler(image_hash)
    application.add_handler(start_handler)
    application.add_handler(repl_text_handler)
    application.add_handler(chat_id_handler)
    application.add_handler(chat_all_bayans)
    application.add_handler(bayan_stat)
    application.add_handler(byayan_handler)
    application.add_handler(bayan_counter_handler)
    application.add_handler(is_ai_slop)

    application.run_polling()
