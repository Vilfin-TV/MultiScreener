import os
import json
import urllib.request
import urllib.error
import io
import contextlib
import google.generativeai as genai
from dotenv import load_dotenv

load_dotenv()
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
            return text
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
            'models/gemini-1.5-pro',
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
