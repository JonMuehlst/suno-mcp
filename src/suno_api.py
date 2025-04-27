"""
Client for interacting with the unofficial Suno API.

Based on the reverse-engineered logic from:
https://github.com/gcui-art/suno-api/blob/main/src/lib/SunoApi.ts
"""

import httpx
import asyncio
import time
from typing import Any, Dict, List, Optional

from src import config
from src.captcha_solver import solve_hcaptcha

BASE_URL = "https://studio-api.suno.ai"
CLERK_BASE_URL = "https://clerk.suno.ai" # Suno uses Clerk for authentication


class SunoApiException(Exception):
    """Custom exception for Suno API errors."""
    pass


class SunoApi:
    def __init__(self, cookie: Optional[str] = None):
        """
        Initializes the Suno API client.

        Args:
            cookie: The '__client' and 'sid' cookie string. If None, uses config.SUNO_COOKIE.
        """
        self._cookie = cookie or config.SUNO_COOKIE
        if not self._cookie:
            raise ValueError("Suno cookie must be provided either via argument or SUNO_COOKIE env var.")

        # Extract session ID if available in the cookie, otherwise use config
        self._session_id = self._extract_sid_from_cookie(self._cookie) or config.SUNO_SESSION_ID
        self._token: Optional[str] = config.SUNO_TOKEN # Initial token from config, will be refreshed

        self._client = httpx.AsyncClient(base_url=BASE_URL, timeout=60.0)
        self._client.headers.update({"User-Agent": "Mozilla/5.0"}) # Mimic browser
        self._update_headers() # Set initial headers

    def _extract_sid_from_cookie(self, cookie_str: str) -> Optional[str]:
        """Extracts the 'sid' value from a cookie string."""
        parts = cookie_str.split(';')
        for part in parts:
            if 'sid=' in part:
                return part.split('sid=')[1].strip()
        return None

    def _update_headers(self):
        """Updates the HTTP client headers with the current cookie and token."""
        headers = {
            "Cookie": self._cookie,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client.headers.update(headers)
        print("Debug: Updated headers with new token/cookie.") # Debugging

    async def _request(self, method: str, endpoint: str, **kwargs) -> Any:
        """Makes an authenticated request to the Suno API, handling token refresh."""
        if not self._token:
            print("Attempting to refresh token before request...")
            await self.refresh_token() # Ensure token exists before first request

        try:
            response = await self._client.request(method, endpoint, **kwargs)
            response.raise_for_status() # Raise HTTP errors
            return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401: # Unauthorized, likely expired token
                print("Received 401 Unauthorized. Attempting token refresh...")
                await self.refresh_token()
                # Retry the request with the new token
                response = await self._client.request(method, endpoint, **kwargs)
                response.raise_for_status()
                return response.json()
            elif e.response.status_code == 402: # Payment Required / CAPTCHA likely
                 # Check response body for CAPTCHA details (structure might vary)
                error_data = e.response.json()
                if "captcha_sitekey" in error_data and "captcha_url" in error_data:
                    print("CAPTCHA challenge detected.")
                    # TODO: Implement CAPTCHA solving flow
                    # sitekey = error_data["captcha_sitekey"]
                    # url = error_data["captcha_url"]
                    # captcha_token = solve_hcaptcha(sitekey, url)
                    # if captcha_token:
                    #     # Need to figure out how to resubmit the request with the captcha token
                    #     print("CAPTCHA solved, but resubmission logic not implemented.")
                    #     raise SunoApiException(f"CAPTCHA required, solving not fully implemented: {error_data}")
                    # else:
                    #     raise SunoApiException(f"CAPTCHA required but solving failed: {error_data}")
                    raise SunoApiException(f"CAPTCHA required, solving not implemented: {error_data}") # Placeholder
                else:
                     raise SunoApiException(f"API Error {e.response.status_code}: {e.response.text}") from e

            else:
                raise SunoApiException(f"API Error {e.response.status_code}: {e.response.text}") from e
        except Exception as e:
            raise SunoApiException(f"An unexpected error occurred: {e}") from e

    async def refresh_token(self) -> None:
        """Refreshes the authentication token using the session ID."""
        if not self._session_id:
            raise SunoApiException("Cannot refresh token: Session ID (sid) is missing.")

        print(f"Debug: Refreshing token using session ID: {self._session_id}")
        clerk_client = httpx.AsyncClient(base_url=CLERK_BASE_URL, timeout=30.0)
        try:
            # This endpoint is based on observed browser behavior with Clerk
            refresh_url = f"/v1/client/sessions/{self._session_id}/tokens?_clerk_js_version=4.72.0-snapshot.vc141245" # Version might change
            response = await clerk_client.post(refresh_url, headers={"Cookie": self._cookie})
            response.raise_for_status()
            data = response.json()

            # Find the JWT token in the response (structure might vary)
            new_token = None
            if "jwt" in data:
                new_token = data["jwt"]
            elif isinstance(data.get("response"), dict) and "jwt" in data["response"]:
                 new_token = data["response"]["jwt"] # Nested structure observed sometimes

            if not new_token:
                 raise SunoApiException(f"Could not find JWT in token refresh response: {data}")

            self._token = new_token
            self._update_headers()
            print("Token refreshed successfully.")
        except httpx.HTTPStatusError as e:
            raise SunoApiException(f"Failed to refresh token: {e.response.status_code} - {e.response.text}") from e
        except Exception as e:
            raise SunoApiException(f"An unexpected error occurred during token refresh: {e}") from e
        finally:
            await clerk_client.aclose()


    async def get_credits(self) -> Dict[str, Any]:
        """Fetches the user's current credit balance."""
        print("Fetching credits...")
        return await self._request("GET", "/api/billing/info/")

    async def generate_music(
        self,
        prompt: str,
        tags: Optional[str] = None,
        title: Optional[str] = None,
        is_custom: bool = False,
        instrumental: bool = False,
        wait_for_completion: bool = True,
        polling_interval: int = 5,
    ) -> List[Dict[str, Any]]:
        """
        Generates music based on a prompt.

        Args:
            prompt: The text prompt describing the desired music.
            tags: Style tags (e.g., "pop, upbeat").
            title: Title for the generated track.
            is_custom: True for custom mode (lyrics provided in prompt), False for simple mode.
            instrumental: Generate instrumental music only.
            wait_for_completion: If True, poll the API until generation is complete.
            polling_interval: Seconds between polling attempts.

        Returns:
            A list of dictionaries, each representing a generated audio clip,
            or the initial generation response if wait_for_completion is False.
        """
        print(f"Generating music with prompt: '{prompt}'")
        endpoint = "/api/generate/v2/" if not is_custom else "/api/generate/lyrics/" # Different endpoints? Check TS code
        # The TS code uses /api/generate/v2/ for both, let's stick to that for now.
        endpoint = "/api/generate/v2/"

        payload = {
            "gpt_description_prompt": prompt,
            "mv": "chirp-v3-0",  # Model version, might need updates
            "prompt": "" if is_custom else prompt, # Simple mode repeats prompt here
            "make_instrumental": instrumental,
            # Optional fields based on TS code observation
            "tags": tags,
            "title": title,
            # "continue_at": None, # For extending clips
            # "continue_clip_id": None, # For extending clips
        }
        # Clean payload from None values
        payload = {k: v for k, v in payload.items() if v is not None}

        if is_custom:
             # Custom mode might require different payload structure - needs verification
             # The TS code seems to put lyrics directly in gpt_description_prompt
             # and leaves 'prompt' empty. Let's assume that for now.
             payload["prompt"] = "" # Ensure prompt is empty for custom mode per TS logic
             print("Using custom mode generation.")


        initial_response = await self._request("POST", endpoint, json=payload)
        print(f"Initial generation response: {initial_response}")

        if not isinstance(initial_response, dict) or "clips" not in initial_response:
             raise SunoApiException(f"Unexpected initial response format: {initial_response}")

        if not wait_for_completion:
            return initial_response["clips"] # Return potentially incomplete clips

        clip_ids = [clip["id"] for clip in initial_response["clips"]]
        if not clip_ids:
             print("Warning: No clip IDs found in initial response.")
             return []

        print(f"Polling for completion of clips: {clip_ids}")
        start_time = time.time()
        timeout = 300 # 5 minutes timeout for generation

        while time.time() - start_time < timeout:
            await asyncio.sleep(polling_interval)
            try:
                feed_response = await self.get_feed(clip_ids)
                print(f"Polling response: {feed_response}") # Debugging

                complete_clips = []
                all_done = True
                for clip_data in feed_response:
                    if clip_data.get("status") == "complete":
                        complete_clips.append(clip_data)
                    elif clip_data.get("status") == "error":
                         print(f"Error generating clip {clip_data.get('id')}: {clip_data.get('error_message')}")
                         # Decide how to handle errors - skip or raise? For now, just note it.
                    else:
                        all_done = False # At least one clip is still processing

                if all_done:
                    print("All clips processed.")
                    # Verify we have data for all requested IDs, even if errored
                    final_clips = []
                    processed_ids = {c['id'] for c in feed_response}
                    for clip_id in clip_ids:
                        if clip_id in processed_ids:
                            final_clips.extend([c for c in feed_response if c['id'] == clip_id])
                        else:
                            print(f"Warning: Clip ID {clip_id} not found in final feed response.")
                    return final_clips # Return all clips found in the feed

            except SunoApiException as e:
                print(f"Error during polling: {e}. Continuing polling.")
            except Exception as e:
                 print(f"Unexpected error during polling: {e}. Continuing polling.")


        raise SunoApiException(f"Timeout waiting for clips {clip_ids} to complete.")


    async def get_feed(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches the status and details of specific audio clips.

        Args:
            ids: A list of clip IDs to fetch.

        Returns:
            A list of dictionaries, each containing details for a clip.
        """
        if not ids:
            return []
        print(f"Fetching feed for IDs: {ids}")
        ids_param = ",".join(ids)
        return await self._request("GET", f"/api/feed/?ids={ids_param}")

    async def get_lyrics(self, prompt: str) -> Dict[str, Any]:
        """
        Generates lyrics based on a prompt using the dedicated lyrics endpoint.

        Args:
            prompt: The prompt to generate lyrics from.

        Returns:
            A dictionary containing the generated lyrics and metadata.
        """
        print(f"Generating lyrics for prompt: '{prompt}'")
        payload = {"prompt": prompt}
        # Note: The TS code uses POST /api/generate/lyrics/ but the structure seems
        # more like a request to generate *music* with custom lyrics.
        # Let's assume there's a dedicated endpoint for *just* lyrics generation.
        # If this endpoint 404s, we might need to adjust.
        # Update: Based on further review, /api/generate/lyrics might be for submitting
        # *existing* lyrics to generate music. Let's try /api/generate/prompt for lyrics?
        # This needs verification against actual API behavior.
        # Trying the endpoint observed in some network requests: /api/generate/lyrics/
        # Let's revert to the endpoint used in the TS code for *submitting* lyrics generation
        # and see if it works for *generating* lyrics too. This is uncertain.
        # POST /api/generate/lyrics/
        try:
            # This endpoint might actually be for *submitting* a generation request
            # with pre-defined lyrics, not generating lyrics themselves.
            # Need to find the correct endpoint if it exists.
            # For now, let's assume it requires a POST to a specific lyrics endpoint.
            # This is speculative.
            lyrics_endpoint = "/api/generate/lyrics/" # Placeholder - likely incorrect for *generating* lyrics
            response = await self._request("POST", lyrics_endpoint, json=payload)
            print(f"Lyrics generation response: {response}")
            return response
        except SunoApiException as e:
             # If the above fails, maybe there isn't a dedicated lyrics generation endpoint?
             print(f"Error calling assumed lyrics endpoint {lyrics_endpoint}: {e}")
             print("Falling back to trying /api/generate/v2/ with a specific instruction?")
             # Fallback: Try asking the main generation endpoint? Unlikely to work well.
             # raise SunoApiException("Dedicated lyrics generation endpoint not found or failed.") from e
             # Let's assume for now this feature might not be directly available or requires
             # a different approach (e.g., using the chat interface endpoint if one exists).
             raise NotImplementedError("Dedicated lyrics generation endpoint is uncertain or not found.")


    async def close(self):
        """Closes the underlying HTTP client."""
        await self._client.aclose()
        print("Suno API client closed.")


# Example Usage (async context)
async def main():
    if not config.SUNO_COOKIE:
        print("Please set the SUNO_COOKIE environment variable in a .env file or export it.")
        return

    api = SunoApi()
    try:
        print("--- Getting Credits ---")
        credits = await api.get_credits()
        print(f"Credits info: {credits}")

        print("\n--- Generating Instrumental Music ---")
        instrumental_prompt = "A calming lofi hip hop beat"
        instrumental_clips = await api.generate_music(
            prompt=instrumental_prompt,
            instrumental=True,
            wait_for_completion=True
        )
        print(f"Generated {len(instrumental_clips)} instrumental clips:")
        for clip in instrumental_clips:
            print(f"  ID: {clip.get('id')}, Title: {clip.get('title')}, Status: {clip.get('status')}")
            if clip.get('audio_url'):
                print(f"  Audio URL: {clip.get('audio_url')}")


        # print("\n--- Generating Music with Lyrics (Simple Mode) ---")
        # simple_prompt = "A cheerful pop song about sunshine"
        # simple_clips = await api.generate_music(
        #     prompt=simple_prompt,
        #     tags="pop, cheerful, upbeat",
        #     title="Sunshine Day",
        #     wait_for_completion=True
        # )
        # print(f"Generated {len(simple_clips)} simple clips:")
        # for clip in simple_clips:
        #     print(f"  ID: {clip.get('id')}, Title: {clip.get('title')}, Status: {clip.get('status')}")
        #     if clip.get('audio_url'):
        #         print(f"  Audio URL: {clip.get('audio_url')}")

        # print("\n--- Generating Lyrics (Experimental) ---")
        # try:
        #     lyrics_prompt = "Write a short verse about rain"
        #     lyrics_result = await api.get_lyrics(lyrics_prompt)
        #     print(f"Generated lyrics result: {lyrics_result}")
        # except NotImplementedError as e:
        #     print(f"Could not generate lyrics: {e}")
        # except SunoApiException as e:
        #      print(f"API error generating lyrics: {e}")


    except SunoApiException as e:
        print(f"\nAn API error occurred: {e}")
    except Exception as e:
        print(f"\nAn unexpected error occurred: {e}")
    finally:
        await api.close()

if __name__ == "__main__":
    # To run this example:
    # 1. Create a .env file with your SUNO_COOKIE
    # 2. Run `python -m src.suno_api`
    asyncio.run(main())
