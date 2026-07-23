from mcp.server.fastmcp import FastMCP
from shared_tools import (
    publish_story,
    web_search,
    fetch_webpage,
    delegate_to_specialist,
    generate_image,
    run_python_code,
    render_js_webpage
)

# Initialize FastMCP Server
mcp = FastMCP("VilfinTV MCP Central Server")

@mcp.tool()
def mcp_publish_story(section: str, heading: str, story: str, photo_url: str = None) -> str:
    """
    Publish a new news story to the website.
    """
    return publish_story(section, heading, story, photo_url)

@mcp.tool()
def mcp_web_search(query: str) -> str:
    """
    Search the web for up-to-date facts, news, and information.
    """
    return web_search(query)

@mcp.tool()
def mcp_fetch_webpage(url: str) -> str:
    """
    Download and read the text content of a webpage.
    """
    return fetch_webpage(url)

@mcp.tool()
def mcp_delegate_to_specialist(persona: str, prompt: str) -> str:
    """
    Delegate a sub-task to a specialized AI sub-agent.
    """
    return delegate_to_specialist(persona, prompt)

@mcp.tool()
def mcp_generate_image(heading: str, text: str) -> str:
    """
    Generate an AI photo for a news article thumbnail based on the heading.
    """
    return generate_image(heading, text)

@mcp.tool()
def run_python_code_mcp(code: str, telegram_id: str = None) -> str:
    """Run python code locally on the server."""
    return run_python_code(code, telegram_id)

@mcp.tool()
def render_js_webpage_mcp(url: str, wait_for_timeout: int = 2000) -> str:
    """Load a URL in a headless Chromium browser to render JavaScript widgets."""
    return render_js_webpage(url, wait_for_timeout)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--sse", action="store_true", help="Run over SSE transport instead of stdio")
    parser.add_argument("--port", type=int, default=8000, help="Port for SSE server")
    args = parser.parse_args()
    
    if args.sse:
        print(f"Starting MCP Server on HTTP SSE transport (port {args.port})...")
        mcp.run(transport='sse')
    else:
        # Default stdio for local Claude Desktop or Claude CLI
        mcp.run()
