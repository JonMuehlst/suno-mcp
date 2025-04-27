"""Handles solving CAPTCHA challenges, specifically hCaptcha for Suno."""

from twocaptcha import TwoCaptcha
from src import config

def solve_hcaptcha(sitekey: str, url: str) -> str | None:
    """
    Solves an hCaptcha challenge using the 2Captcha service.

    Args:
        sitekey: The hCaptcha sitekey found on the target page.
        url: The URL of the page where the hCaptcha is present.

    Returns:
        The solved CAPTCHA token string, or None if solving failed.
    """
    if not config.TWOCAPTCHA_API_KEY:
        print("Error: TWOCAPTCHA_API_KEY is not configured.")
        return None

    solver = TwoCaptcha(config.TWOCAPTCHA_API_KEY)

    try:
        print(f"Attempting to solve hCaptcha for sitekey: {sitekey} at {url}")
        result = solver.hcaptcha(sitekey=sitekey, url=url)
        print("hCaptcha solved successfully.")
        return result['code'] # The token is in the 'code' key
    except Exception as e:
        print(f"Error solving hCaptcha: {e}")
        return None

# Example usage (for testing purposes)
if __name__ == "__main__":
    # Replace with actual values from Suno's login/challenge page if needed for testing
    test_sitekey = "a5f74b19-9e45-40e0-b45d-47ff5374d174" # Example sitekey, likely incorrect/outdated
    test_url = "https://app.suno.ai/" # Example URL

    if config.TWOCAPTCHA_API_KEY:
        print("Testing hCaptcha solver...")
        token = solve_hcaptcha(test_sitekey, test_url)
        if token:
            print(f"Test successful, received token (partial): {token[:10]}...")
        else:
            print("Test failed.")
    else:
        print("Skipping test, TWOCAPTCHA_API_KEY not set.")
