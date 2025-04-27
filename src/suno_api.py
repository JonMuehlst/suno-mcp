"""
Minimal Python adapter for the unofficial Suno AI API.
Focuses on essential MVP features: generation and retrieval.
Inspired by: https://github.com/gcui-art/suno-api/blob/main/src/lib/SunoApi.ts
"""

import httpx
import asyncio
import time
import logging
from typing import Any, Dict, List, Optional

from src import config
from src.captcha_solver import solve_hcaptcha

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_BASE_URL = "https://studio-api.suno.ai"
DEFAULT_CLERK_BASE_URL = "https://clerk.suno.ai"
LOCAL_API_PATTERN = "localhost:|127.0.0.1:"
# Use a known working Clerk version, can be updated if needed
# CLERK_VERSION = "4.72.0-snapshot.vc141245" # From old code
CLERK_VERSION = "5.15.0" # From TS code analysis

DEFAULT_MODEL = "chirp-v3-5" # Default model from TS code

# --- Custom Exception ---
class SunoApiException(Exception):
    """Custom exception for Suno API adapter errors."""
    pass

# --- Minimal Suno Adapter ---
class SunoAdapter:
    def __init__(self, cookie: Optional[str] = None, base_url: Optional[str] = None):
        """
        Initializes the Suno API adapter.

        Args:
            cookie: The '__client' and 'sid' cookie string. If None, uses config.SUNO_COOKIE.
            base_url: The base URL for the Suno API. If None, uses the default.
        """
        self._cookie = cookie or config.SUNO_COOKIE
        self._base_url = base_url or DEFAULT_BASE_URL
        self._clerk_base_url = DEFAULT_CLERK_BASE_URL
        if not self._cookie:
            raise ValueError("Suno cookie must be provided either via argument or SUNO_COOKIE env var.")

        self._session_id = self._extract_sid_from_cookie(self._cookie)
        if not self._session_id:
            # Fallback to env var if not in cookie (though Clerk usually sets it)
            self._session_id = getattr(config, 'SUNO_SESSION_ID', None)
            if not self._session_id:
                 raise ValueError("Could not find 'sid' in cookie and SUNO_SESSION_ID is not set.")

        # Initial token from config (if available), will be refreshed
        self._token: Optional[str] = getattr(config, 'SUNO_TOKEN', None)
        self._client = httpx.AsyncClient(base_url=self._base_url, timeout=60.0)
        # Mimic headers observed in TS code/browser requests
        self._client.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36", # Example modern UA
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "en-US,en;q=0.9",
            "Origin": "https://app.suno.ai",
            "Referer": "https://app.suno.ai/",
            "Sec-Ch-Ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": '"Windows"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-site",
        })
        self._update_headers() # Set initial cookie/token headers

    def _extract_sid_from_cookie(self, cookie_str: str) -> Optional[str]:
        """Extracts the 'sid' value from a cookie string."""
        parts = cookie_str.split(';')
        for part in parts:
            if 'sid=' in part:
                return part.split('sid=')[1].strip()
        logger.warning("Could not extract 'sid' from the provided cookie string.")
        return None

    def _update_headers(self):
        """Updates the HTTP client headers with the current cookie and token."""
        headers = {
            "Cookie": self._cookie,
        }
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        self._client.headers.update(headers)
        logger.debug("Updated HTTP client headers.")

    async def refresh_token(self) -> None:
        """Refreshes the authentication token using the session ID via Clerk."""
        # Skip token refresh for local API servers
        if any(pattern in self._base_url for pattern in LOCAL_API_PATTERN.split('|')):
            logger.info(f"Skipping token refresh for local API server: {self._base_url}")
            # Set a dummy token for local development
            self._token = "local-development-token"
            self._update_headers()
            return

        if not self._session_id:
            raise SunoApiException("Cannot refresh token: Session ID (sid) is missing.")

        logger.info(f"Refreshing token using session ID: {self._session_id}")
        # Use a separate client for Clerk requests to avoid header conflicts
        async with httpx.AsyncClient(base_url=self._clerk_base_url, timeout=30.0) as clerk_client:
            try:
                # Endpoint from TS code analysis
                refresh_url = f"/v1/client/sessions/{self._session_id}/tokens?_clerk_js_version={CLERK_VERSION}"
                # Clerk requires the __client cookie for this
                clerk_headers = {"Cookie": self._cookie, "User-Agent": self._client.headers["User-Agent"]}
                response = await clerk_client.post(refresh_url, headers=clerk_headers)
                response.raise_for_status()
                data = response.json()

                new_token = data.get("jwt")
                if not new_token:
                    raise SunoApiException(f"Could not find JWT in token refresh response: {data}")

                self._token = new_token
                self._update_headers() # Update main client's headers
                logger.info("Token refreshed successfully.")

            except httpx.HTTPStatusError as e:
                # Log more details on failure
                error_body = e.response.text
                logger.error(f"Failed to refresh token. Status: {e.response.status_code}, Body: {error_body}")
                # Check if it's an expired session ID
                if e.response.status_code == 401 or e.response.status_code == 404:
                     raise SunoApiException(f"Failed to refresh token: Session ID '{self._session_id}' might be invalid or expired. Update SUNO_COOKIE. (Status: {e.response.status_code})") from e
                else:
                     raise SunoApiException(f"Failed to refresh token: {e.response.status_code} - {error_body}") from e
            except Exception as e:
                logger.exception("An unexpected error occurred during token refresh.")
                raise SunoApiException(f"An unexpected error occurred during token refresh: {e}") from e

    async def _request(self, method: str, endpoint: str, attempt_captcha_solve: bool = True, **kwargs) -> Any:
        """
        Makes an authenticated request to the Suno API, handling token refresh and CAPTCHA.

        Args:
            method: HTTP method (e.g., "GET", "POST").
            endpoint: API endpoint path (e.g., "/api/feed/v2").
            attempt_captcha_solve: If True and CAPTCHA (402) is detected, attempt to solve it.
            **kwargs: Additional arguments for httpx.request (e.g., json, params).

        Returns:
            The JSON response from the API.

        Raises:
            SunoApiException: For API errors, network issues, or CAPTCHA failures.
        """
        # For local API servers, we may not need a token
        is_local_api = any(pattern in self._base_url for pattern in LOCAL_API_PATTERN.split('|'))
        
        if not self._token and not is_local_api:
            logger.info("No initial token found, attempting refresh...")
            await self.refresh_token()

        try:
            logger.debug(f"Making request: {method} {endpoint}")
            response = await self._client.request(method, endpoint, **kwargs)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.warning(f"HTTP Error: {e.response.status_code} for {method} {endpoint}")
            if e.response.status_code == 401: # Unauthorized -> Refresh token and retry ONCE
                logger.info("Received 401 Unauthorized. Attempting token refresh...")
                try:
                    await self.refresh_token()
                    logger.info("Retrying request after token refresh...")
                    response = await self._client.request(method, endpoint, **kwargs)
                    response.raise_for_status()
                    return response.json()
                except Exception as refresh_err:
                     logger.error(f"Error during token refresh or retry: {refresh_err}")
                     raise SunoApiException(f"Token refresh failed or retry failed after 401: {refresh_err}") from refresh_err

            elif e.response.status_code == 402 and attempt_captcha_solve: # Payment Required / CAPTCHA
                logger.warning("Received 402 Payment Required, likely a CAPTCHA challenge.")
                try:
                    error_data = e.response.json()
                    logger.debug(f"402 Error Body: {error_data}")
                    # {"error":"Captcha Required","captcha_sitekey":"a5f74b19-9e45-40e0-b45d-47ff5374d174","captcha_url":"https://app.suno.ai/api/c/challenge/"}
                    sitekey = error_data.get("captcha_sitekey")
                    # The 'captcha_url' might not be the direct page URL, but an API endpoint.
                    # Use the base app URL for 2Captcha as per their docs.
                    captcha_page_url = "https://app.suno.ai/"

                    if sitekey:
                        logger.info(f"Attempting to solve hCaptcha with sitekey: {sitekey}")
                        captcha_token = solve_hcaptcha(sitekey=sitekey, url=captcha_page_url)

                        if captcha_token:
                            logger.info("CAPTCHA solved successfully. Retrying request with token.")
                            # Add captcha token to the original request payload (assuming POST JSON)
                            original_payload = kwargs.get("json", {})
                            original_payload["captcha_token"] = captcha_token # Adjust key if needed
                            kwargs["json"] = original_payload

                            # Retry the request with the CAPTCHA token
                            # Set attempt_captcha_solve=False to prevent infinite loop if solving fails
                            return await self._request(method, endpoint, attempt_captcha_solve=False, **kwargs)
                        else:
                            logger.error("CAPTCHA solving failed.")
                            raise SunoApiException(f"CAPTCHA required but solving failed. Response: {error_data}")
                    else:
                        logger.error("CAPTCHA required (402) but sitekey not found in response.")
                        raise SunoApiException(f"CAPTCHA required (402) but sitekey missing. Response: {error_data}")
                except Exception as captcha_err:
                    logger.exception("Error during CAPTCHA handling.")
                    raise SunoApiException(f"Error processing CAPTCHA challenge: {captcha_err}") from captcha_err

            elif e.response.status_code == 429: # Rate limited
                 logger.error(f"Rate limited (429). Response: {e.response.text}")
                 raise SunoApiException(f"API rate limit exceeded: {e.response.text}") from e
            else:
                # Handle other HTTP errors
                error_body = e.response.text
                logger.error(f"Unhandled API Error {e.response.status_code}: {error_body}")
                raise SunoApiException(f"API Error {e.response.status_code}: {error_body}") from e
        except httpx.RequestError as e:
            logger.exception(f"Network error during API request to {endpoint}: {e}")
            raise SunoApiException(f"Network error connecting to Suno API: {e}") from e
        except Exception as e:
            logger.exception(f"An unexpected error occurred during API request to {endpoint}: {e}")
            raise SunoApiException(f"An unexpected error occurred: {e}") from e

    async def _generate_request(
        self,
        payload: Dict[str, Any],
        wait_audio: bool = True,
        polling_interval: int = 5,
        timeout: int = 300
    ) -> List[Dict[str, Any]]:
        """Internal helper to make generation request and handle polling."""
        endpoint = "/api/generate/v2/"
        logger.info(f"Submitting generation request to {endpoint} with payload: {payload}")

        # The _request method handles CAPTCHA reactively if a 402 is returned.
        initial_response = await self._request("POST", endpoint, json=payload)
        logger.debug(f"Initial generation response: {initial_response}")

        if not isinstance(initial_response, dict) or "clips" not in initial_response:
            raise SunoApiException(f"Unexpected initial response format: {initial_response}")

        clips = initial_response["clips"]
        clip_ids = [clip["id"] for clip in clips if "id" in clip]

        if not clip_ids:
            logger.warning("No clip IDs found in initial generation response.")
            # Check if there was an error message in the response
            if initial_response.get("error"):
                 raise SunoApiException(f"Generation request failed: {initial_response.get('error')}")
            return [] # Return empty list if no clips and no obvious error

        if not wait_audio:
            logger.info("Returning initial clip data without waiting for completion.")
            return clips # Return potentially incomplete clips

        # --- Polling for Completion ---
        logger.info(f"Polling for completion of clips: {clip_ids}")
        start_time = time.time()

        while time.time() - start_time < timeout:
            await asyncio.sleep(polling_interval)
            try:
                # Refresh token periodically during long polls
                if time.time() - start_time > 60: # Example: refresh every minute
                    await self.refresh_token()

                feed_response = await self.get(clip_ids)
                logger.debug(f"Polling feed response: {feed_response}")

                if not feed_response:
                    logger.warning("Polling returned empty feed response.")
                    # Continue polling, maybe temporary issue
                    continue

                all_done = True
                errors = []
                for clip_id in clip_ids:
                    # Find the corresponding clip data in the feed response
                    clip_data = next((c for c in feed_response if c.get("id") == clip_id), None)
                    if not clip_data:
                        logger.warning(f"Clip ID {clip_id} not found in polling response. Assuming still processing.")
                        all_done = False
                        break # Exit inner loop, continue outer polling loop
                    elif clip_data.get("status") == "complete":
                        logger.debug(f"Clip {clip_id} is complete.")
                        continue # Check next clip
                    elif clip_data.get("status") == "error":
                        error_msg = clip_data.get('error_message', 'Unknown error')
                        logger.error(f"Error generating clip {clip_id}: {error_msg}")
                        errors.append(f"Clip {clip_id}: {error_msg}")
                        # Continue checking other clips, but mark as not all done if any error
                        continue # Treat error as 'done' for polling purposes
                    else: # Still processing (e.g., 'streaming', 'submitted')
                        logger.debug(f"Clip {clip_id} status: {clip_data.get('status')}. Still processing.")
                        all_done = False
                        break # Exit inner loop, continue outer polling loop

                if all_done:
                    logger.info("All requested clips have completed processing (or errored).")
                    # Return the final state from the last successful feed fetch
                    final_clips = [c for c in feed_response if c.get("id") in clip_ids]
                    if errors:
                         # Optionally raise an exception or just return the data including errors
                         logger.warning(f"Generation finished with errors: {'; '.join(errors)}")
                         # raise SunoApiException(f"Generation failed for some clips: {'; '.join(errors)}")
                    return final_clips

            except SunoApiException as e:
                logger.error(f"API error during polling: {e}. Will retry polling.")
                # Optional: implement backoff or stop after too many polling errors
            except Exception as e:
                logger.exception("Unexpected error during polling. Will retry polling.")

        raise SunoApiException(f"Timeout ({timeout}s) waiting for clips {clip_ids} to complete.")

    async def generate(
        self,
        prompt: str,
        make_instrumental: bool = False,
        model: str = DEFAULT_MODEL,
        wait_audio: bool = True,
        polling_interval: int = 5,
        timeout: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Generates music based on a simple prompt (description).

        Args:
            prompt: The text prompt describing the desired music.
            make_instrumental: Generate instrumental music only.
            model: The generation model to use (e.g., 'chirp-v3-5').
            wait_audio: If True, poll the API until generation is complete or timeout.
            polling_interval: Seconds between polling attempts.
            timeout: Maximum seconds to wait for generation completion.

        Returns:
            A list of dictionaries, each representing a generated audio clip.
        """
        payload = {
            "gpt_description_prompt": prompt,
            "prompt": "", # Keep empty for simple mode as per TS analysis
            "mv": model,
            "make_instrumental": make_instrumental,
            # "token": None # CAPTCHA token added by _request if needed
        }
        return await self._generate_request(payload, wait_audio, polling_interval, timeout)

    async def custom_generate(
        self,
        prompt: str, # Should contain lyrics for custom mode
        tags: Optional[str] = None,
        title: Optional[str] = None,
        make_instrumental: bool = False, # Usually False for custom lyrics
        model: str = DEFAULT_MODEL,
        wait_audio: bool = True,
        polling_interval: int = 5,
        timeout: int = 300
    ) -> List[Dict[str, Any]]:
        """
        Generates music using custom mode (lyrics in prompt, optional style tags/title).

        Args:
            prompt: The lyrics for the song.
            tags: Style tags (e.g., "pop, upbeat").
            title: Title for the generated track.
            make_instrumental: Generate instrumental music (rarely used with custom lyrics).
            model: The generation model to use.
            wait_audio: If True, poll the API until generation is complete or timeout.
            polling_interval: Seconds between polling attempts.
            timeout: Maximum seconds to wait for generation completion.

        Returns:
            A list of dictionaries, each representing a generated audio clip.
        """
        payload = {
            "prompt": prompt, # Lyrics go here in custom mode
            "tags": tags,
            "title": title,
            "mv": model,
            "make_instrumental": make_instrumental,
            "gpt_description_prompt": None, # Not used in custom mode
            # "token": None # CAPTCHA token added by _request if needed
        }
        # Clean payload from None values
        payload = {k: v for k, v in payload.items() if v is not None}
        return await self._generate_request(payload, wait_audio, polling_interval, timeout)

    async def get(self, ids: List[str]) -> List[Dict[str, Any]]:
        """
        Fetches the status and details of specific audio clips using the v2 feed endpoint.

        Args:
            ids: A list of clip IDs to fetch.

        Returns:
            A list of dictionaries, each containing details for a clip found.
            Returns an empty list if no IDs are provided or none are found.
        """
        if not ids:
            return []
        logger.info(f"Fetching feed for IDs: {ids}")
        ids_param = ",".join(ids)
        try:
            # Use attempt_captcha_solve=False as GET requests shouldn't require CAPTCHA
            response_data = await self._request("GET", f"/api/feed/v2?ids={ids_param}", attempt_captcha_solve=False)

            # The v2 endpoint returns a list directly
            if isinstance(response_data, list):
                 # Filter results to only include requested IDs, as API might return extras
                 return [clip for clip in response_data if clip.get("id") in ids]
            else:
                 logger.warning(f"Unexpected response format from /api/feed/v2: {response_data}")
                 return []

        except SunoApiException as e:
            # Log error but return empty list as clips might just not exist yet/anymore
            logger.error(f"Failed to get feed for IDs {ids}: {e}")
            return []
        except Exception as e:
            logger.exception(f"Unexpected error fetching feed for IDs {ids}.")
            return []


    async def close(self):
        """Closes the underlying HTTP client."""
        await self._client.aclose()
        logger.info("Suno API adapter client closed.")
