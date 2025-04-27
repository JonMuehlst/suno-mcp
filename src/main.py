"""
MCP Server Entry Point for Suno AI Integration.

This server uses the Model Context Protocol (MCP) to expose Suno AI music
generation capabilities to compatible clients like Claude Desktop.
"""

import asyncio
from mcp.server.fastmcp import FastMCP, Context, Image
from mcp.server.models import ToolInputSchema, ToolParameter

from src import config # Loads .env automatically
from src.suno_api import SunoApi, SunoApiException
from src.audio_handler import download_audio, convert_audio

# --- MCP Server Setup ---
# Initialize FastMCP server
mcp = FastMCP(
    name="Suno AI Music Generator",
    version="0.1.0",
    description="Generates music using the unofficial Suno AI API.",
    # Define dependencies needed if installed via `mcp install`
    dependencies=[
        "httpx>=0.27.0",
        "python-2captcha-solver>=1.0.5",
        "pydub>=0.25.1",
        "python-dotenv>=1.0.0",
        # Add mcp itself if not implicitly included by the installer
        "mcp[cli]>=1.6.0"
    ]
)

# --- Lifespan Management (Optional but Recommended) ---
# Use lifespan to manage the SunoApi client lifecycle
class ServerContext:
    def __init__(self):
        self.suno_client: SunoApi | None = None

@mcp.lifespan()
async def lifespan_manager(server: FastMCP) -> asyncio.AsyncIterator[ServerContext]:
    """Manages the SunoApi client lifecycle."""
    print("MCP Server Lifespan: Initializing Suno API client...")
    app_context = ServerContext()
    try:
        app_context.suno_client = SunoApi(cookie=config.SUNO_COOKIE)
        # Perform an initial check, like getting credits, to ensure connection works
        try:
            credits = await app_context.suno_client.get_credits()
            print(f"Suno client initialized successfully. Credits info: {credits}")
        except SunoApiException as e:
            print(f"Warning: Initial check with Suno API failed: {e}")
            # Decide if this should prevent startup? For now, just warn.
        except Exception as e:
             print(f"Warning: Unexpected error during Suno client initialization: {e}")

        yield app_context # Make client available to tools via ctx.request_context.lifespan_context

    except ValueError as e:
        print(f"Error initializing Suno API client: {e}. Check SUNO_COOKIE.")
        # Optionally raise to prevent server start if cookie is essential
        # raise RuntimeError(f"Failed to initialize Suno API client: {e}") from e
        # For now, allow server to start but client will be None
        yield app_context # Yield even if client failed, tools should check
    finally:
        print("MCP Server Lifespan: Shutting down...")
        if app_context.suno_client:
            await app_context.suno_client.close()
            print("Suno API client closed.")


# --- MCP Tools ---

@mcp.tool(
    name="generate_music",
    description="Generates a short music clip based on a text prompt using Suno AI.",
    input_schema=ToolInputSchema(
        parameters=[
            ToolParameter(name="prompt", description="Detailed description of the music (e.g., '80s synthwave, retrofuturistic, driving beat').", type="string", required=True),
            ToolParameter(name="instrumental", description="Set to true to generate instrumental music only.", type="boolean", required=False, default=False),
            ToolParameter(name="style_tags", description="Comma-separated style tags (e.g., 'pop, upbeat, female vocalist').", type="string", required=False),
            ToolParameter(name="title", description="Optional title for the generated track.", type="string", required=False),
            # ToolParameter(name="custom_lyrics", description="Provide full lyrics for the song (experimental). If used, the main prompt should describe the music style.", type="string", required=False),
        ]
    )
)
async def generate_music_tool(
    prompt: str,
    instrumental: bool = False,
    style_tags: str | None = None,
    title: str | None = None,
    # custom_lyrics: str | None = None, # Re-enable when custom lyrics are better understood
    ctx: Context | None = None # Context object provided by FastMCP
) -> str | Image: # Return text description or Image object
    """MCP Tool function to generate music."""
    if not ctx:
         return "Error: MCP Context not available."

    lifespan_ctx: ServerContext = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.suno_client:
        return "Error: Suno API client is not initialized. Check server logs and configuration."

    suno_client = lifespan_ctx.suno_client
    is_custom = False # Currently disabled
    # is_custom = bool(custom_lyrics)
    # generation_prompt = custom_lyrics if is_custom else prompt

    await ctx.info(f"Received music generation request: '{prompt}' (Instrumental: {instrumental})")

    try:
        await ctx.report_progress(0, 100, "Starting music generation...") # Progress: 0%
        clips = await suno_client.generate_music(
            prompt=prompt, # Use main prompt for description even in custom mode for now
            tags=style_tags,
            title=title,
            is_custom=is_custom, # Pass custom flag
            instrumental=instrumental,
            wait_for_completion=True, # Wait for results
            polling_interval=5
        )
        await ctx.report_progress(50, 100, "Generation request submitted, waiting for results...") # Progress: 50%

        if not clips:
            await ctx.error("Music generation failed or returned no clips.")
            return "Music generation failed or returned no clips."

        results = []
        successful_clips = [c for c in clips if c.get("status") == "complete" and c.get("audio_url")]

        if not successful_clips:
             await ctx.error("Generation completed, but no successful audio clips were produced.")
             # Provide more detail if available
             error_messages = [c.get('error_message', 'Unknown error') for c in clips if c.get('status') == 'error']
             if error_messages:
                 return f"Generation failed. Errors: {'; '.join(error_messages)}"
             else:
                 return "Generation completed, but no successful audio clips were produced."


        await ctx.info(f"Successfully generated {len(successful_clips)} audio clip(s).")
        await ctx.report_progress(80, 100, "Downloading audio...") # Progress: 80%

        # For simplicity, return the first successful clip's audio
        # TODO: Handle multiple clips better (e.g., return list of URLs or multiple Image objects?)
        first_clip = successful_clips[0]
        audio_url = first_clip.get("audio_url")
        clip_title = first_clip.get("title", "Untitled Suno Track")
        clip_id = first_clip.get("id")

        if not audio_url:
             await ctx.error(f"Clip {clip_id} is complete but has no audio URL.")
             return f"Clip {clip_id} generated but audio URL is missing."

        # Download the audio (MP3 typically)
        audio_data_mp3 = await download_audio(audio_url)

        if not audio_data_mp3:
            await ctx.error(f"Failed to download audio for clip {clip_id} from {audio_url}")
            return f"Failed to download audio for clip {clip_id}."

        # MCP Image type supports common formats, let's try returning MP3 directly
        # If Claude Desktop has issues, we might need to convert to WAV/OGG
        # image = Image(data=audio_data_mp3.getvalue(), format="mp3", description=f"Generated Music: {clip_title}")

        # Let's convert to WAV for potentially wider compatibility in clients
        await ctx.report_progress(90, 100, "Converting audio to WAV...") # Progress: 90%
        audio_data_wav = convert_audio(audio_data_mp3, target_format="wav", source_format="mp3")

        if not audio_data_wav:
             await ctx.error(f"Failed to convert audio for clip {clip_id} to WAV.")
             # Fallback to returning MP3 URL? Or just fail? Let's fail for now.
             return f"Failed download/convert audio for clip {clip_id}."


        image = Image(
            data=audio_data_wav.getvalue(),
            format="wav", # Use 'wav' format identifier
            description=f"Generated Music: {clip_title} (ID: {clip_id})"
        )

        await ctx.report_progress(100, 100, "Audio ready.") # Progress: 100%
        return image # Return the MCP Image object

    except SunoApiException as e:
        await ctx.error(f"Suno API Error: {e}")
        return f"Error during music generation: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected Error: {e}")
        import traceback
        traceback.print_exc() # Log full traceback to server console
        return f"An unexpected error occurred: {e}"


@mcp.tool(
    name="get_suno_credits",
    description="Retrieves the current Suno AI credit balance.",
    input_schema=ToolInputSchema(parameters=[]) # No input parameters
)
async def get_credits_tool(ctx: Context | None = None) -> str:
    """MCP Tool function to get Suno credits."""
    if not ctx:
         return "Error: MCP Context not available."

    lifespan_ctx: ServerContext = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.suno_client:
        return "Error: Suno API client is not initialized. Check server logs and configuration."

    suno_client = lifespan_ctx.suno_client
    await ctx.info("Fetching Suno credits...")
    try:
        credits_info = await suno_client.get_credits()
        # Format the response nicely
        # Example structure: {'credits': 50, 'usage': 10, 'period': 'monthly', 'next_reset': '...'}
        # Adjust formatting based on actual response structure
        credits = credits_info.get('credits', 'N/A')
        total_monthly_limit = credits_info.get('monthly_limit', 'N/A')
        monthly_usage = credits_info.get('monthly_usage', 'N/A')
        response_str = f"Suno Credits: {credits} remaining. Monthly Usage: {monthly_usage}/{total_monthly_limit}."
        await ctx.info(f"Credits fetched: {response_str}")
        return response_str
    except SunoApiException as e:
        await ctx.error(f"Suno API Error fetching credits: {e}")
        return f"Error fetching credits: {e}"
    except Exception as e:
        await ctx.error(f"Unexpected Error fetching credits: {e}")
        return f"An unexpected error occurred while fetching credits: {e}"


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
