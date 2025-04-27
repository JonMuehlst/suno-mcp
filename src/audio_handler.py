"""Minimal audio handling utility for downloading audio."""

import httpx
import io
import mimetypes
from typing import Optional, Tuple

# Add common audio types if not recognized by default
mimetypes.add_type("audio/mpeg", ".mp3")
mimetypes.add_type("audio/ogg", ".ogg")
mimetypes.add_type("audio/wav", ".wav")

async def download_audio(url: str) -> Optional[Tuple[io.BytesIO, str]]:
    """
    Downloads audio from a URL and returns it as BytesIO with its MIME type.

    Args:
        url: The URL of the audio file (e.g., MP3 from Suno).

    Returns:
        A tuple containing (io.BytesIO object with audio data, MIME type string)
        or None if download fails.
    """
    try:
        async with httpx.AsyncClient() as client:
            print(f"Downloading audio from: {url}")
            response = await client.get(url, follow_redirects=True, timeout=60.0)
            response.raise_for_status()
            print("Download successful.")

            audio_data = io.BytesIO(response.content)
            audio_data.seek(0) # Reset buffer position for reading

            # Determine MIME type from URL or response headers
            mime_type, _ = mimetypes.guess_type(url)
            if not mime_type and 'content-type' in response.headers:
                 # Fallback to Content-Type header
                 mime_type = response.headers['content-type'].split(';')[0].strip()

            # Default to audio/mpeg if still unknown (common for Suno)
            if not mime_type:
                print("Warning: Could not determine MIME type, defaulting to audio/mpeg.")
                mime_type = "audio/mpeg"
            else:
                 print(f"Determined MIME type: {mime_type}")


            return audio_data, mime_type

    except httpx.HTTPStatusError as e:
        print(f"HTTP error downloading audio from {url}: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"Error downloading audio from {url}: {e}")
        return None

# Example Usage (can be run directly if needed)
async def example_download():
    # Replace with a valid Suno audio URL after generation
    # Example MP3 URL structure (replace ... with actual ID)
    test_audio_url = "https://cdn1.suno.ai/audio_prompt/..." # Replace with actual URL

    if "..." in test_audio_url:
        print("Skipping example: Replace test_audio_url with a real URL.")
        return

    result = await download_audio(test_audio_url)

    if result:
        audio_bytes_io, mime = result
        print(f"Successfully downloaded audio (in memory). MIME type: {mime}")
        print(f"Audio size: {len(audio_bytes_io.getvalue())} bytes")
        # Example: Save the downloaded file
        # save_format = mime.split('/')[-1] # e.g., 'mpeg' -> use 'mp3' maybe?
        # filename = f"downloaded_audio.{'mp3' if save_format == 'mpeg' else save_format}"
        # with open(filename, "wb") as f:
        #     f.write(audio_bytes_io.getvalue())
        # print(f"Saved audio to {filename}")
    else:
        print("Failed to download audio.")


if __name__ == "__main__":
    import asyncio
    # Note: Running this requires a valid audio URL.
    # asyncio.run(example_download())
    print("Minimal audio handler module loaded. Run example_download() with a valid URL for testing.")
