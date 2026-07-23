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

def publish_story(section: str, heading: str, story: str, photo_url: str = None) -> str:
    """
    Publish a new news story to the website.
    
    Args:
        section: The category of the news (e.g. 'trending', 'global', 'india', 'stock', 'malayalam', 'tech', 'space', 'science', 'movies', 'sports').
        heading: The title of the news story.
        story: The content of the story in HTML format (using <p>, <h3>, <ul>, etc). DO NOT use <h1> or <h2>.
        photo_url: Optional URL of an image to feature in the news story. Use the generate_image tool to create one.
    """
    worker_url = os.getenv("WORKER_URL")
    agent_key = os.getenv("AGENT_API_KEY")
    
    if not worker_url or not agent_key:
        return "Error: WORKER_URL or AGENT_API_KEY is not set in the .env file on the server."
        
    url = f"{worker_url}/api/agent/publish"
    payload = {
        "section": section,
        "heading": heading,
        "story": story
    }
    if photo_url:
        payload["photo"] = photo_url
        
    data = json.dumps(payload).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {agent_key}"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            return f"Successfully published story. Response: {res_body}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return f"Failed to publish story. HTTP {e.code}: {err_body}"
    except Exception as e:
        return f"Exception occurred while publishing: {e}"

def web_search(query: str) -> str:
    """
    Search the web for up-to-date facts, news, and information.
    
    Args:
        query: The search query to look up.
    """
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=5))
            if not results:
                return "No results found."
            formatted = "\n\n".join([f"Title: {r['title']}\nLink: {r['href']}\nSnippet: {r['body']}" for r in results])
            return formatted
    except Exception as e:
        return f"Search failed: {e}"

def fetch_webpage(url: str) -> str:
    """
    Download and read the text content of a webpage (useful for reading documentation or full articles).
    
    Args:
        url: The URL of the webpage to fetch.
    """
    try:
        import urllib.request
        from bs4 import BeautifulSoup
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8')
            soup = BeautifulSoup(html, 'html.parser')
            # Extract main text
            for script in soup(["script", "style"]):
                script.extract()
            text = soup.get_text(separator=' ', strip=True)
            return text[:8000] # Return first 8000 chars to avoid token limits
    except Exception as e:
        return f"Failed to fetch webpage: {e}"

def delegate_to_specialist(persona: str, prompt: str) -> str:
    """
    Delegate a sub-task to a specialized AI sub-agent.
    
    Args:
        persona: The persona to adopt (e.g. 'Malayalam Translator', 'Japanese Translator', 'Drama Writer', 'Comedy Writer', 'Security Auditor').
        prompt: The specific task or text for the sub-agent to process.
    """
    try:
        sub_model = genai.GenerativeModel(
            'models/gemini-flash-latest',
            system_instruction=f"You are an expert {persona}. Completely fulfill the user's prompt in your specific style."
        )
        response = sub_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Delegation failed: {e}"

def generate_image(heading: str, text: str) -> str:
    """
    Generate an AI photo for a news article thumbnail based on the heading.
    Returns the URL of the generated image, which can then be passed to the publish_story tool.
    
    Args:
        heading: The title of the news story.
        text: A short description of the story.
    """
    worker_url = os.getenv("WORKER_URL")
    agent_key = os.getenv("AGENT_API_KEY")
    
    if not worker_url or not agent_key:
        return "Error: WORKER_URL or AGENT_API_KEY is not set."
        
    url = f"{worker_url}/api/generate-photo"
    data = json.dumps({
        "heading": heading,
        "text": text
    }).encode("utf-8")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {agent_key}"
    }
    
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as response:
            res_body = response.read().decode("utf-8")
            res_json = json.loads(res_body)
            if res_json.get("ok"):
                return res_json.get("url", "No URL found in response")
            return f"Failed: {res_body}"
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8")
        return f"Image generation failed. HTTP {e.code}: {err_body} (Note: Your Agent API Key must have the 'operator' scope enabled in the console to use image generation)."
    except Exception as e:
        return f"Exception occurred while generating image: {e}"

def run_python_code(code: str, user_id: int) -> str:
    """
    Execute Python code locally on the server for testing purposes.
    WARNING: This executes arbitrary code. It is protected by an ownership check.
    
    Args:
        code: The python code to run.
        user_id: The Telegram ID of the user requesting execution (passed automatically, or use the context's user ID).
    """
    # Security Check
    if user_id != OWNER_TELEGRAM_ID or OWNER_TELEGRAM_ID == 0:
        return "Security Error: You are not authorized to run code on this server. Please set OWNER_TELEGRAM_ID in the .env file."
        
    f = io.StringIO()
    with contextlib.redirect_stdout(f), contextlib.redirect_stderr(f):
        try:
            exec(code, {})
            return f.getvalue() or "Code executed successfully with no output."
        except Exception as e:
            return f.getvalue() + f"\nError: {e}"

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
    # Using the latest available flash model from 2026
    model = genai.GenerativeModel(
        'models/gemini-flash-latest',
        tools=tools,
        system_instruction="You are Antigravity, a highly capable parallel multi-agent orchestrator for VilfinTV. You have access to various specialized tools (web search, web browsing, publishing, python testing, specialized personas, and AI image generation). Use them concurrently when needed. For complex requests (e.g. 'Research X, generate a photo, translate to Malayalam, and publish'), you can orchestrate multiple tools to achieve the final result. For python execution, ensure you pass the user's Telegram ID into the tool. NEVER use markdown ```html blocks when generating story content for publish_story. When asked to create an image, use the generate_image tool, then pass the resulting URL to publish_story."
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
    history = db.get_history(user_id, limit=10)
    
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
