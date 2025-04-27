"""
MCP Server Entry Point for Suno AI Integration.

This server uses the Model Context Protocol (MCP) to expose Suno AI music
generation capabilities to compatible clients like Claude Desktop.
"""

import asyncio
import traceback
import io
from typing import Optional, AsyncIterator, List, Dict, Any # Added for type hints
from urllib.parse import urlparse # Added for URI parsing

# Import all MCP dependencies first
from fastmcp import FastMCP, Context

# Import local modules
from src import config # Loads .env automatically
from src.suno_api import SunoAdapter, SunoApiException
from src.audio_handler import download_audio # Updated import

# Create the MCP instance at module level so it can be imported by tests
mcp = FastMCP(
    name="Suno AI Music Generator",
    version="0.1.0-mvp",
    description="Generates music using the Suno AI API via MCP.",
    # Dependencies are managed via requirements.txt
)

# --- MCP Server Setup ---
# FastMCP server is initialized at module level above

# --- Lifespan Management (Optional but Recommended) ---
# --- Server Context for Lifespan ---
class ServerContext:
    """Holds resources needed during the server's lifespan."""
    def __init__(self):
        self.suno_client: Optional[SunoAdapter] = None

# --- Lifespan Management ---
@mcp.lifespan()
async def lifespan_manager(server: FastMCP) -> AsyncIterator[ServerContext]:
    """Manages the SunoAdapter client lifecycle."""
    print("MCP Server Lifespan: Initializing Suno API adapter...")
    app_context = ServerContext()
    try:
        # Initialize the adapter
        app_context.suno_client = SunoAdapter(cookie=config.SUNO_COOKIE)
        # Perform an initial check (e.g., try refreshing token) to ensure auth works
        try:
            await app_context.suno_client.refresh_token()
            print("Suno adapter initialized and token refreshed successfully.")
        except SunoApiException as e:
            print(f"Warning: Initial token refresh for Suno adapter failed: {e}")
            # Decide if this should prevent startup? For now, just warn.
        except Exception as e:
             print(f"Warning: Unexpected error during Suno adapter initialization: {e}")

        yield app_context # Make client available to tools via ctx.request_context.lifespan_context

    except ValueError as e:
        print(f"Error initializing Suno API adapter: {e}. Check SUNO_COOKIE.")
        # Allow server to start but client will be None, tools must check
        yield app_context
    except Exception as e:
        print(f"Critical error during Suno adapter initialization: {e}")
        traceback.print_exc()
        # Yield context even on critical error, tools must handle None client
        yield app_context
    finally:
        print("MCP Server Lifespan: Shutting down...")
        if app_context.suno_client:
            await app_context.suno_client.close()
            print("Suno API adapter closed.")


# --- MCP Tools ---

# Tool 1: Simple Generation
@mcp.tool()
async def generate_song(
    prompt: str,
    instrumental: bool = False,
    ctx: Context = None
) -> str:
    """
    Generates a song based on a descriptive prompt using Suno AI.

    Args:
        prompt: Detailed description of the music (e.g., '80s synthwave, retrofuturistic, driving beat').
        instrumental: Set to true to generate instrumental music only (default: False).
        ctx: MCP Context (automatically injected).

    Returns:
        A text description including a suno:// URI to play the generated song.
    """
    if not ctx: return "Error: MCP Context not available."
    lifespan_ctx: ServerContext = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.suno_client:
        return "Error: Suno API adapter not initialized. Check server logs."

    suno_client: SunoAdapter = lifespan_ctx.suno_client # Type assertion

    await ctx.info(f"Received simple generation request: '{prompt}' (Instrumental: {instrumental})")

    try:
        await ctx.report_progress(0, 100, "Starting simple generation...") # Progress: 0%

        clips: List[Dict[str, Any]] = await suno_client.generate(
            prompt=prompt,
            make_instrumental=instrumental,
            wait_audio=True, # Wait for generation to complete
            polling_interval=5
        )

        await ctx.report_progress(50, 100, "Waiting for Suno generation...") # Progress: 50%

        if not clips:
            await ctx.error("Suno request succeeded but returned no clips.")
            return "Music generation failed or returned no clips."

        # Filter for successfully completed clips with an ID
        successful_clips = [c for c in clips if c.get("status") == "complete" and c.get("id")]

        if not successful_clips:
            await ctx.error("Generation completed, but no successful audio clips were produced.")
            error_messages = [c.get('error_message', 'Unknown error') for c in clips if c.get('status') == 'error']
            return f"Generation failed. Errors: {'; '.join(error_messages)}" if error_messages else "No successful clips produced."

        # For MVP, just use the first successful clip
        first_clip = successful_clips[0]
        clip_id = first_clip.get("id")
        clip_title = first_clip.get("title", "Untitled Suno Track")

        if not clip_id:
             await ctx.error("Successful clip found, but it is missing an ID.")
             return "Generation succeeded but failed to retrieve clip ID."


        await ctx.info(f"Successfully generated clip '{clip_title}' (ID: {clip_id}).")
        await ctx.report_progress(100, 100, "Generation complete.") # Progress: 100%

        # Return text description with the resource URI
        return f"Generated song: '{clip_title}'.\nPlay it using the resource URI: suno://{clip_id}"

    except SunoApiException as e:
        await ctx.error(f"Suno API Error: {e}")
        return f"Error during simple generation: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected Error: {e}")
        traceback.print_exc()
        return f"An unexpected error occurred during simple generation: {e}"


# Tool 2: Custom Generation
@mcp.tool()
async def custom_generate_song(
    lyrics: str,
    style_tags: Optional[str] = None,
    title: Optional[str] = None,
    instrumental: bool = False,
    ctx: Context = None
) -> str:
    """
    Generates a song with custom lyrics, style tags, and title using Suno AI.

    Args:
        lyrics: The full lyrics for the song.
        style_tags: Comma-separated style tags (e.g., 'pop, upbeat, female vocalist').
        title: Optional title for the generated track.
        instrumental: Set to true to generate instrumental music only (default: False).
        ctx: MCP Context (automatically injected).

    Returns:
        A text description including a suno:// URI to play the generated song.
    """
    if not ctx: return "Error: MCP Context not available."
    lifespan_ctx: ServerContext = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.suno_client:
        return "Error: Suno API adapter not initialized. Check server logs."

    suno_client: SunoAdapter = lifespan_ctx.suno_client # Type assertion

    await ctx.info(f"Received custom generation request: (Title: {title}, Style: {style_tags}, Instrumental: {instrumental})")
    await ctx.debug(f"Lyrics: {lyrics[:100]}...") # Log start of lyrics

    try:
        await ctx.report_progress(0, 100, "Starting custom generation...") # Progress: 0%

        clips: List[Dict[str, Any]] = await suno_client.custom_generate(
            prompt=lyrics, # Use lyrics as the main prompt for custom mode
            tags=style_tags,
            title=title,
            make_instrumental=instrumental,
            wait_audio=True, # Wait for generation to complete
            polling_interval=5
        )

        await ctx.report_progress(50, 100, "Waiting for Suno custom generation...") # Progress: 50%

        if not clips:
            await ctx.error("Suno custom request succeeded but returned no clips.")
            return "Custom music generation failed or returned no clips."

        # Filter for successfully completed clips with an ID
        successful_clips = [c for c in clips if c.get("status") == "complete" and c.get("id")]

        if not successful_clips:
            await ctx.error("Custom generation completed, but no successful audio clips were produced.")
            error_messages = [c.get('error_message', 'Unknown error') for c in clips if c.get('status') == 'error']
            return f"Custom generation failed. Errors: {'; '.join(error_messages)}" if error_messages else "No successful clips produced."

        # For MVP, just use the first successful clip
        first_clip = successful_clips[0]
        clip_id = first_clip.get("id")
        clip_title = first_clip.get("title", title or "Untitled Custom Suno Track") # Use provided title or default

        if not clip_id:
             await ctx.error("Successful custom clip found, but it is missing an ID.")
             return "Custom generation succeeded but failed to retrieve clip ID."

        await ctx.info(f"Successfully generated custom clip '{clip_title}' (ID: {clip_id}).")
        await ctx.report_progress(100, 100, "Custom generation complete.") # Progress: 100%

        # Return text description with the resource URI
        return f"Generated custom song: '{clip_title}'.\nPlay it using the resource URI: suno://{clip_id}"

    except SunoApiException as e:
        await ctx.error(f"Suno API Error during custom generation: {e}")
        return f"Error during custom music generation: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected Error during custom generation: {e}")
        traceback.print_exc()
        return f"An unexpected error occurred during custom generation: {e}"


# --- MCP Resource Handler ---

@mcp.resource_handler("suno")
async def handle_suno_resource(uri: str, ctx: Context = None):
    """
    Handles requests for suno://<song_id> URIs to retrieve and serve audio.

    Args:
        uri: The resource URI (e.g., "suno://abc-123").
        ctx: MCP Context (automatically injected).

    Returns:
        An MCP Resource object containing the audio data and MIME type, or None if retrieval fails.
    """
    if not ctx:
        print("Error: MCP Context not available in resource handler.")
        return None

    lifespan_ctx: ServerContext = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.suno_client:
        print("Error: Suno API adapter not initialized in resource handler.")
        # Log to server console, client won't see this directly unless MCP forwards it
        await ctx.error("Resource handler cannot access Suno client (not initialized).")
        return None

    suno_client: SunoAdapter = lifespan_ctx.suno_client

    try:
        parsed_uri = urlparse(uri)
        if parsed_uri.scheme != "suno" or not parsed_uri.netloc:
            await ctx.error(f"Invalid Suno resource URI format: {uri}")
            return None

        song_id = parsed_uri.netloc # The song ID is the 'host' part of the URI
        await ctx.info(f"Handling resource request for Suno song ID: {song_id}")

        # 1. Get clip details from Suno API using the ID
        await ctx.report_progress(10, 100, f"Fetching details for song {song_id}...")
        clip_details_list = await suno_client.get([song_id])

        if not clip_details_list:
            await ctx.error(f"Could not find details for song ID: {song_id}")
            return None

        clip_details = clip_details_list[0] # .get() returns a list
        audio_url = clip_details.get("audio_url")
        clip_title = clip_details.get("title", "Untitled Suno Track")
        clip_status = clip_details.get("status")

        if clip_status != "complete" or not audio_url:
            # Check if it's still processing
            if clip_status in ["submitted", "processing", "queued"]:
                 await ctx.info(f"Song {song_id} is still processing (Status: {clip_status}). Client should retry.")
                 # Return a temporary error or specific message? MCP doesn't have a standard retry mechanism here.
                 # For now, treat as failure for the resource handler.
                 await ctx.error(f"Song {song_id} is not ready yet (Status: {clip_status}). Please try again later.")
                 return None # Indicate failure to retrieve resource *now*
            else:
                await ctx.error(f"Song {song_id} is not complete or has no audio URL (Status: {clip_status}).")
                # Optionally, check for error messages in clip_details
                return None

        await ctx.info(f"Found audio URL for song {song_id}: {audio_url}")
        await ctx.report_progress(30, 100, "Downloading audio...")

        # 2. Download the audio using audio_handler
        # download_audio returns a tuple: (BytesIO, mime_type) or None
        download_result = await download_audio(audio_url)

        if not download_result:
            await ctx.error(f"Failed to download audio for song {song_id} from {audio_url}")
            return None

        audio_data_bytes_io, audio_mime_type = download_result
        audio_bytes = audio_data_bytes_io.getvalue()
        await ctx.info(f"Audio downloaded ({len(audio_bytes)} bytes, type: {audio_mime_type}).")
        await ctx.report_progress(90, 100, "Audio downloaded. Preparing resource...")

        # 3. Create and return the MCP Resource
        from fastmcp import Resource
        resource = Resource(
            uri=uri,
            mime_type=audio_mime_type,
            data=audio_bytes,
            description=f"Suno AI Generated Audio: {clip_title} (ID: {song_id})"
        )
        await ctx.report_progress(100, 100, "Resource ready.")
        return resource

    except SunoApiException as e:
        await ctx.error(f"Suno API Error while handling resource {uri}: {e}")
        return None
    except Exception as e:
        await ctx.error(f"Unexpected Error while handling resource {uri}: {e}")
        traceback.print_exc() # Log full traceback to server console
        return None


# --- Main Execution ---
if __name__ == "__main__":
    print("Starting Suno AI MCP Server...")
    # Use mcp.run() for direct execution (e.g., testing locally)
    # For Claude Desktop, you'll use `mcp install src/main.py`
    # and Claude Desktop will manage running the server process.

    # To run directly (e.g., python src/main.py):
    # Note: This uses stdio transport by default.
    # You might need to configure host/port if running as a standalone web service.
    try:
        mcp.run() # This blocks until the server is stopped
    except Exception as e:
        print(f"Server failed to start or crashed: {e}")
        import traceback
        traceback.print_exc()

    # Example command to test installation with Claude Desktop:
    # mcp install src/main.py --name "Suno Music Gen" -f .env
