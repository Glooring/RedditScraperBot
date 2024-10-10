import os
import logging
import asyncio
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackQueryHandler, ContextTypes
from dotenv import load_dotenv
from helpers.latest_posts import get_latest_posts  # Import the get_latest_posts function

# Load environment variables
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# Set up logging to show only warnings and errors
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.WARNING)
logger = logging.getLogger(__name__)

# Store the user profile URLs and their states
tracked_users = []

# Store the latest menu message ID to delete it when necessary
latest_menu_message_id = None

# Store background task for current user
background_task = None

# Store last sent posts to avoid duplicate messages
last_sent_posts = {}

# Function to send messages with retry logic
async def send_message_with_retry(context, chat_id, message, retries=3, delay=2, disable_web_page_preview=False):
    for attempt in range(retries):
        try:
            await context.bot.send_message(chat_id=chat_id, text=message, disable_web_page_preview=disable_web_page_preview, parse_mode="Markdown")
            break
        except Exception as e:
            if attempt < retries - 1:
                logger.warning(f"Failed to send message, retrying in {delay} seconds... ({e})")
                await asyncio.sleep(delay)
            else:
                logger.error(f"Failed to send message after {retries} attempts: {e}")


# Async function to send latest posts in an infinite loop
async def send_latest_posts_infinite(chat_id: int, context: ContextTypes.DEFAULT_TYPE, user_profile_url: str, username: str) -> None:
    global last_sent_posts
    while True:
        latest_posts = get_latest_posts(user_profile_url + "submitted/")
        
        # Print the combined latest posts for debugging
        
        if chat_id not in last_sent_posts or last_sent_posts[chat_id] != latest_posts:
            if isinstance(latest_posts, list):
                message = f"Latest Post of {username}:\n" + "\n".join([f"[{post['title']}]({post['url']})" for post in latest_posts])
                last_sent_posts[chat_id] = latest_posts
                await send_message_with_retry(context, chat_id, message, disable_web_page_preview=True)
                await context.bot.send_message(chat_id=chat_id, text="Checking for new posts...", disable_web_page_preview=True)
        #else:
        #    print("Same as before")
        
        await asyncio.sleep(3)












# Define the bot commands and callbacks
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global latest_menu_message_id
    keyboard = [
        [InlineKeyboardButton("Select platforms to track", callback_data='select_platform')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    message = await update.message.reply_text("Welcome! Please select a platform to track:", reply_markup=reply_markup)
    latest_menu_message_id = message.message_id

async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    keyboard = [
        [InlineKeyboardButton("Reddit", callback_data='select_reddit')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Select platforms to track:", reply_markup=reply_markup)

async def select_reddit(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    keyboard = [[InlineKeyboardButton("Back", callback_data='select_platform')]]
    
    for user in tracked_users:
        username = user['username']
        checked = user['checked']
        label = f"{username} {'✅' if checked else ''}"
        callback_data = f'toggle_user_{username}'
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    if tracked_users:
        keyboard.append([InlineKeyboardButton("Add user", callback_data='add_user')])
    else:
        keyboard.append([InlineKeyboardButton("Add user", callback_data='add_user')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text="Reddit users in track:", reply_markup=reply_markup)

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global latest_menu_message_id
    query = update.callback_query
    await query.answer()

    #if latest_menu_message_id:
    #    try:
    #        await context.bot.delete_message(chat_id=query.message.chat_id, message_id=latest_menu_message_id)
    #    except Exception as e:
    #        logger.warning(f"Failed to delete message: {e}")
    
    await query.message.reply_text(
        text="Enter the link of the reddit user profile in the format: https://www.reddit.com/user/UserName/",
        disable_web_page_preview=True
    )

async def handle_user_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global tracked_users
    global latest_menu_message_id
    global background_task
    user_profile_url = update.message.text


    if not user_profile_url.endswith('/'):
        user_profile_url += '/'
        
    if user_profile_url.endswith('submitted/'):
        user_profile_url = user_profile_url[:-10]

    if user_profile_url.startswith("https://www.reddit.com/user/"):
        username = user_profile_url.split('/')[-2]

        # Check if the user is already tracked
        user_already_tracked = False
        for user in tracked_users:
            if user['username'] == username:
                user_already_tracked = True
                # Check the user if it is not already checked
                if not user['checked']:
                    user['checked'] = True

                    # Uncheck all other users
                    for other_user in tracked_users:
                        if other_user['username'] != username:
                            other_user['checked'] = False

                    # Cancel the previous background task if it exists
                    if background_task:
                        background_task.cancel()

                    # Start fetching posts for the existing user
                    background_task = asyncio.create_task(send_latest_posts_infinite(update.message.chat_id, context, user_profile_url, username))

                break

        if user_already_tracked:
            await update.message.reply_text(f"User {username} is already being tracked.")

            # Show the latest panel
            keyboard = [[InlineKeyboardButton("Back", callback_data='select_platform')]]
        
            for user in tracked_users:
                username = user['username']
                checked = user['checked']
                label = f"{username} {'✅' if checked else ''}"
                callback_data = f'toggle_user_{username}'
                keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
            
            keyboard.append([InlineKeyboardButton("Add user", callback_data='add_user')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("Reddit users in track:", reply_markup=reply_markup)
        else:
            # Uncheck all users
            for user in tracked_users:
                user['checked'] = False
            
            # Add the new user and check it
            tracked_users.append({'username': username, 'url': user_profile_url, 'checked': True})
            
            keyboard = [[InlineKeyboardButton("Back", callback_data='select_platform')]]
        
            for user in tracked_users:
                username = user['username']
                checked = user['checked']
                label = f"{username} {'✅' if checked else ''}"
                callback_data = f'toggle_user_{username}'
                keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
            
            keyboard.append([InlineKeyboardButton("Add user", callback_data='add_user')])

            reply_markup = InlineKeyboardMarkup(keyboard)
            message = await update.message.reply_text(f"Added {username}", reply_markup=reply_markup)
            latest_menu_message_id = message.message_id

            # Cancel the previous background task if it exists
            if background_task:
                background_task.cancel()

            # Start fetching posts for the new user
            background_task = asyncio.create_task(send_latest_posts_infinite(update.message.chat_id, context, user_profile_url, username))
    else:
        await update.message.reply_text("Invalid URL format. Please try again.")




async def toggle_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global tracked_users
    global background_task
    global latest_menu_message_id
    query = update.callback_query
    await query.answer()

    username = query.data.split('_')[-1]

    for user in tracked_users:
        user['checked'] = (user['username'] == username)

    # Delete the latest menu message if it exists
    if latest_menu_message_id:
        try:
            await context.bot.delete_message(chat_id=query.message.chat_id, message_id=latest_menu_message_id)
        except Exception as e:
            logger.warning(f"Failed to delete message: {e}")

    keyboard = [[InlineKeyboardButton("Back", callback_data='select_platform')]]
    
    for user in tracked_users:
        username = user['username']
        checked = user['checked']
        label = f"{username} {'✅' if checked else ''}"
        callback_data = f'toggle_user_{username}'
        keyboard.append([InlineKeyboardButton(label, callback_data=callback_data)])
    
    keyboard.append([InlineKeyboardButton("Add user", callback_data='add_user')])

    reply_markup = InlineKeyboardMarkup(keyboard)
    new_menu_message = await context.bot.send_message(
        chat_id=query.message.chat_id,
        text="Reddit users in track:",
        reply_markup=reply_markup
    )

    # Update the latest menu message ID
    latest_menu_message_id = new_menu_message.message_id

    # Cancel the previous background task if it exists
    if background_task:
        background_task.cancel()

    # Start a new background task for the selected user
    selected_user = next(user for user in tracked_users if user['checked'])
    chat_id = query.message.chat_id
    background_task = asyncio.create_task(send_latest_posts_infinite(chat_id, context, selected_user['url'], selected_user['username']))



async def start_tracking(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global tracked_users
    query = update.callback_query
    await query.answer()
    
    selected_user = next(user for user in tracked_users if user['checked'])
    selected_user_profile_url = selected_user['url']
    
    job_queue = context.job_queue
    job_queue.run_repeating(send_latest_posts, interval=3, first=0, data={'previous_latest_posts': [], 'chat_id': query.message.chat_id, 'url': selected_user_profile_url})

async def send_latest_posts(context: ContextTypes.DEFAULT_TYPE) -> None:
    job = context.job
    previous_latest_posts = job.data.get('previous_latest_posts', [])
    user_profile_url = job.data['url']

    current_latest_posts, new_post_made = check_new_post(user_profile_url, previous_latest_posts)

    if new_post_made:
        message = f"Latest Post:\n" + "\n".join(current_latest_posts) + "\n\nNew post made"
        job.data['previous_latest_posts'] = current_latest_posts
    else:
        message = f"Latest Post:\n" + "\n".join(current_latest_posts) + "\n\nNo new post made"

    await context.bot.send_message(job.chat_id, text=message)

def main() -> None:
    application = Application.builder().token(TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_link))
    application.add_handler(CallbackQueryHandler(select_platform, pattern='^select_platform$'))
    application.add_handler(CallbackQueryHandler(select_reddit, pattern='^select_reddit$'))
    application.add_handler(CallbackQueryHandler(add_user, pattern='^add_user$'))
    application.add_handler(CallbackQueryHandler(toggle_user, pattern='^toggle_user_'))
    application.add_handler(CallbackQueryHandler(start_tracking, pattern='^start_tracking$'))

    application.run_polling()

if __name__ == '__main__':
    main()
