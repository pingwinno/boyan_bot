# Boyan – Telegram Group Chat Bot  

Boyan is a bot that helps manage images in group chats by using perceptual hashing to detect duplicate posts.  

## Features  
- Identifies whether an image has been previously posted in the chat.  
- Notifies users of the original message containing the duplicate image.  
- Stores hashes of all images posted in the chat for future reference. Users can retrieve all links to messages containing the same image by replying to a picture with a bot command.  

## Commands  
- **`get_all_bayans`** – Reply to a picture with this command to find all messages containing the same image.  
- **`bayan_count`** – Get your bayan count.  
- **`bayan_stat`** – Get bayan stats for this chat.  

## Limitations & Workaround  
Due to Telegram Bot API restrictions, the bot can only process messages sent after it was added to the chat. However, a workaround exists: you can manually populate the database using the chat export feature available in the Telegram desktop client.  
