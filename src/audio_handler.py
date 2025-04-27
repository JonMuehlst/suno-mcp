"""Utilities for handling audio data, e.g., downloading, format conversion."""

import httpx
from pydub import AudioSegment
import io
import os
from typing import Optional

async def download_audio(url: str, output_path: Optional[str] = None) -> Optional[io.BytesIO]:
    """
    Downloads audio from a URL.

    Args:
        url: The URL of the audio file (e.g., MP3 from Suno).
        output_path: Optional path to save the downloaded file. If None, returns BytesIO.

    Returns:
        An io.BytesIO object containing the audio data if output_path is None,
        otherwise None. Returns None on download failure.
    """
    try:
        async with httpx.AsyncClient() as client:
            print(f"Downloading audio from: {url}")
            response = await client.get(url, follow_redirects=True, timeout=60.0)
            response.raise_for_status()
            print("Download successful.")

            audio_data = io.BytesIO(response.content)

            if output_path:
                print(f"Saving audio to: {output_path}")
                os.makedirs(os.path.dirname(output_path), exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(audio_data.getvalue())
                return None # Indicate file saved, no BytesIO returned
            else:
                return audio_data # Return in-memory data

    except httpx.HTTPStatusError as e:
        print(f"HTTP error downloading audio from {url}: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"Error downloading audio from {url}: {e}")
        return None

def convert_audio(input_data: io.BytesIO, target_format: str = "wav", source_format: str = "mp3") -> Optional[io.BytesIO]:
    """
    Converts audio data from one format to another using pydub.
    Requires ffmpeg or libav to be installed and in the system PATH.

    Args:
        input_data: BytesIO object containing the source audio data.
        target_format: The desired output format (e.g., "wav", "ogg").
        source_format: The format of the input data (e.g., "mp3").

    Returns:
        A BytesIO object with the converted audio data, or None if conversion fails.
    """
    try:
        print(f"Converting audio from {source_format} to {target_format}...")
        # Ensure the input data buffer is reset
        input_data.seek(0)
        audio = AudioSegment.from_file(input_data, format=source_format)

        output_data = io.BytesIO()
        audio.export(output_data, format=target_format)
        output_data.seek(0) # Reset buffer position for reading
        print("Conversion successful.")
        return output_data
    except Exception as e:
        # pydub often raises generic Exceptions, especially if ffmpeg is missing
        print(f"Error converting audio: {e}")
        print("Ensure ffmpeg or libav is installed and accessible in your PATH.")
        return None

# Example Usage
async def example_download_and_convert():
    # Replace with a valid Suno audio URL after generation
    test_audio_url = "https://cdn1.suno.ai/..." # Replace with actual URL

    if "..." in test_audio_url:
        print("Skipping example: Replace test_audio_url with a real URL.")
        return

    # 1. Download MP3
    mp3_data = await download_audio(test_audio_url)

    if mp3_data:
        # 2. Convert MP3 to WAV
        wav_data = convert_audio(mp3_data, target_format="wav", source_format="mp3")

        if wav_data:
            print("Successfully downloaded MP3 and converted to WAV (in memory).")
            # You could save the WAV data here if needed:
            # with open("output.wav", "wb") as f:
            #     f.write(wav_data.getvalue())
        else:
            print("Downloaded MP3, but failed to convert to WAV.")

        # Example: Save directly during download
        await download_audio(test_audio_url, output_path="downloaded_audio.mp3")

    else:
        print("Failed to download audio.")


if __name__ == "__main__":
    import asyncio
    # Note: Running this requires a valid audio URL.
    # asyncio.run(example_download_and_convert())
    print("Audio handler module loaded. Run example_download_and_convert() with a valid URL for testing.")
