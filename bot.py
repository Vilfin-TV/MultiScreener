import os
import asyncio
import json
import urllib.request
import urllib.error
import io
import sys
import contextlib
import docx
from dotenv import load_dotenv
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from database import Database

load_dotenv()

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
OWNER_TELEGRAM_ID = int(os.getenv("OWNER_TELEGRAM_ID", 0))

from shared_tools import (
    publish_story,
    web_search,
    fetch_webpage,
    delegate_to_specialist,
    generate_image,
    run_python_code
)

tools = [
    publish_story,
    web_search,
    fetch_webpage,
    delegate_to_specialist,
    run_python_code,
    generate_image
]

if GEMINI_API_KEY and GEMINI_API_KEY != "PLACEHOLDER_KEY":
    genai.configure(api_key=GEMINI_API_KEY)
    # Using the Gemini Flash model to bypass Pro quota limits on Free Tier
    model = genai.GenerativeModel(
        'models/gemini-flash-latest',
        tools=tools,
        system_instruction="You are Antigravity, a highly capable parallel multi-agent orchestrator for VilfinTV. You have access to various specialized tools (web search, web browsing, publishing, python testing, specialized personas, and AI image generation). Use them concurrently when needed. For complex requests (e.g. 'Research X, generate a photo, translate to Malayalam, and publish'), you can orchestrate multiple tools to achieve the final result. For python execution, ensure you pass the user's Telegram ID into the tool. NEVER use markdown ```html blocks when generating story content for publish_story. When asked to create an image, use the generate_image tool, then pass the resulting URL to publish_story. IMPORTANT: Your primary source for Indian market, business, and financial news is https://www.livemint.com/rss - always read this RSS feed to stay up to date when the user asks for stock or market news."
    )
else:
    model = None

db = Database()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    welcome_text = "Hello! I am Antigravity Agent. I am running securely on your server as a parallel multi-agent orchestrator."
    await update.message.reply_text(welcome_text)
    db.add_message(update.message.from_user.id, "model", welcome_text)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    user_text = update.message.text or update.message.caption or ""
    parts = [user_text]

    # Handle file downloads
    temp_file_path = None
    if update.message.photo:
        file = await update.message.photo[-1].get_file()
        temp_file_path = f"temp_{file.file_id}.jpg"
        await file.download_to_drive(temp_file_path)
    elif update.message.document:
        file = await update.message.document.get_file()
        temp_file_path = f"temp_{file.file_id}_{update.message.document.file_name}"
        await file.download_to_drive(temp_file_path)

    # Provide the user_id implicitly to the run_python_code tool by injecting it into the prompt if code execution is requested
    if "run" in user_text.lower() or "test" in user_text.lower() or "code" in user_text.lower():
        user_text = f"[System: The user's Telegram ID is {user_id}. Pass this to the run_python_code tool if needed.]\n{user_text}"
        parts[0] = user_text # update parts array

    # Save user message
    db.add_message(user_id, "user", user_text or "[Sent a file]")

    # Fetch history
    history = db.get_history(user_id, limit=30)
    
    messages = []
    for role, content in history:
        messages.append({
            "role": role,
            "parts": [content]
        })
    
    try:
        if not model:
            reply_text = "I received your message, but my Gemini API Key is not set yet. Please update the .env file on the server with your Gemini API key and restart the service."
        else:
            # Process the downloaded file
            if temp_file_path:
                if temp_file_path.lower().endswith('.docx'):
                    try:
                        doc = docx.Document(temp_file_path)
                        full_text = "\n".join([para.text for para in doc.paragraphs])
                        parts.append(f"\n[Content of {update.message.document.file_name}]:\n{full_text}")
                    except Exception as e:
                        parts.append(f"\n[Failed to read Word document: {e}]")
                else:
                    # Treat everything else as something Gemini File API can handle (PDFs, Images, txt, etc)
                    try:
                        uploaded_file = genai.upload_file(temp_file_path)
                        parts.append(uploaded_file)
                    except Exception as e:
                        parts.append(f"\n[Failed to upload file to Gemini: {e}]")

            # Filter out empty string parts
            parts = [p for p in parts if p != ""]

            # Generate response using chat session with automatic function calling enabled
            chat = model.start_chat(history=messages[:-1], enable_automatic_function_calling=True)
            response = chat.send_message(parts)
            reply_text = response.text
    except Exception as e:
        reply_text = f"An error occurred: {e}"
    finally:
        # Cleanup temp file
        if temp_file_path and os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except:
                pass

    # Save and send model message
    db.add_message(user_id, "model", reply_text)
    await update.message.reply_text(reply_text)

def main():
    if not TELEGRAM_TOKEN:
        print("Error: TELEGRAM_TOKEN not found in environment.")
        return

    application = Application.builder().token(TELEGRAM_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler((filters.TEXT | filters.PHOTO | filters.Document.ALL) & ~filters.COMMAND, handle_message))

    print("Starting parallel orchestrator polling...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
