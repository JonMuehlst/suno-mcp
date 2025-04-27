"""
MCP Server Entry Point for Suno AI Integration.

This server uses the Model Context Protocol (MCP) to expose Suno AI music
generation capabilities to compatible clients like Claude Desktop.
"""

import asyncio
import traceback
from mcp.server.fastmcp import FastMCP, Context, Image
from mcp.server.models import ToolInputSchema, ToolParameter

from src import config # Loads .env automatically
from src.suno_api import SunoAdapter, SunoApiException # Changed import
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
# Use lifespan to manage the SunoAdapter client lifecycle
class ServerContext:
    def __init__(self):
        self.suno_client: SunoAdapter | None = None # Changed type hint

@mcp.lifespan()
async def lifespan_manager(server: FastMCP) -> asyncio.AsyncIterator[ServerContext]:
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
    # custom_lyrics: str | None = None, # Custom lyrics mode not implemented in minimal adapter
    ctx: Context | None = None # Context object provided by FastMCP
) -> str | Image: # Return text description or Image object
    """MCP Tool function to generate music."""
    if not ctx:
         return "Error: MCP Context not available."

    lifespan_ctx: ServerContext = ctx.request_context.lifespan_context
    if not lifespan_ctx or not lifespan_ctx.suno_client:
        return "Error: Suno API adapter is not initialized. Check server logs and configuration."

    suno_client: SunoAdapter = lifespan_ctx.suno_client # Type hint updated

    await ctx.info(f"Received music generation request: '{prompt}' (Instrumental: {instrumental}, Style: {style_tags}, Title: {title})")

    try:
        await ctx.report_progress(0, 100, "Starting music generation...") # Progress: 0%

        # Decide which adapter method to call based on provided parameters
        # Use custom_generate if style_tags or title are provided, otherwise use generate
        if style_tags or title:
            await ctx.info("Using custom generation mode (tags/title provided).")
            # Note: In Suno's custom mode, the 'prompt' usually contains lyrics.
            # Here, we are passing the description as prompt, and style/title separately.
            # This might not align perfectly with Suno's intended custom mode usage,
            # but fits the adapter's current structure.
            clips = await suno_client.custom_generate(
                prompt=prompt, # Pass description as prompt
                tags=style_tags,
                title=title,
                make_instrumental=instrumental,
                wait_audio=True,
                polling_interval=5
            )
        else:
            await ctx.info("Using simple generation mode.")
            clips = await suno_client.generate(
                prompt=prompt,
                make_instrumental=instrumental,
                wait_audio=True,
                polling_interval=5
            )

        await ctx.report_progress(50, 100, "Generation request submitted, waiting for results...") # Progress: 50%

        if not clips:
            await ctx.error("Music generation request succeeded but returned no clips.")
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
        traceback.print_exc() # Log full traceback to server console
        return f"An unexpected error occurred: {e}"

# --- Removed get_suno_credits tool as it's not part of the minimal adapter ---

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
