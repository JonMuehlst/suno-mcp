# Suno MCP Server MVP - Quick Start Tutorial

Welcome! This guide will help you set up and use the Minimum Viable Product (MVP) version of the Suno MCP server with Claude Desktop. This version allows basic song generation and custom song generation with your own lyrics.

## 1. Installation and Setup

Follow these steps to get the server ready.

**a. Install Python:**
*   Ensure you have Python 3.10 or newer installed. You can download it from [python.org](https://www.python.org/).
*   Verify your installation by opening a terminal or command prompt and running: `python --version` or `python3 --version`.

**b. Install Dependencies:**
*   Open a terminal or command prompt in the project's root directory (the one containing `requirements.txt`).
*   It's recommended to use a virtual environment:
    ```bash
    python -m venv venv
    # On Windows
    .\venv\Scripts\activate
    # On macOS/Linux
    # source venv/bin/activate
    ```
*   Install the required packages (listed in `requirements.txt`):
    ```bash
    pip install -r requirements.txt
    ```

**c. Get Your Suno Cookie:**
*   Log in to your Suno account at [suno.com](https://suno.com/).
*   Open your browser's developer tools (usually by pressing F12).
*   Go to the "Network" tab.
*   Refresh the Suno page or perform an action (like generating a song).
*   Look for requests made to `studio-api.suno.ai` or similar Suno API endpoints.
*   Click on one of these requests and find the "Request Headers" section.
*   Locate the `cookie:` header. You need to copy the **entire value** of this header. It will likely contain multiple parts separated by semicolons, such as `__client=...; sid=...;`.

**d. Set up the `.env` File:**
*   Find the file named `.env.example` in the project directory.
*   Make a copy of this file and rename the copy to `.env`.
*   Open the `.env` file in a text editor.
*   Paste the **entire** Suno cookie string you copied in the previous step as the value for `SUNO_COOKIE=`. Make sure there are no extra spaces or quotes around the cookie value unless they were part of the original cookie string.
    ```dotenv
    # Example .env content (replace the value with your actual cookie)
    SUNO_COOKIE=__client=YOUR_COPIED_CLIENT_PART; sid=YOUR_COPIED_SID_PART; other_parts...

    # You can leave other settings like TWOCAPTCHA_API_KEY blank for the MVP
    TWOCAPTCHA_API_KEY=
    ```
*   Save and close the `.env` file. The application will load this variable automatically.

## 2. Configure Claude Desktop

Now, let's tell Claude Desktop how to find and run your Suno server.

**a. Find the Configuration File:**
*   **Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
    *   Tip: Type `%APPDATA%\Claude` into the Windows File Explorer address bar and press Enter.
*   **macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`
    *   Tip: In Finder, click "Go" in the menu bar, hold down the Option key, and click "Library". Then navigate to `Application Support/Claude`.

**b. Edit the Configuration:**
*   Open `claude_desktop_config.json` with a text editor. If the file doesn't exist, create it.
*   Add the following JSON configuration. If the file already has a `"mcpServers": {}` section, just add the `"suno"` part inside the existing curly braces `{}`.

    ```json
    {
      "mcpServers": {
        "suno": {
          "command": "python",
          "args": ["-m", "src.main"]
        }
      }
    }
    ```
    *   **Virtual Environment Note:** If you activated a virtual environment in Step 1b, you should specify the full path to the Python executable *within that environment* here.
        *   Example (Windows): `"command": "C:\\path\\to\\your\\project\\venv\\Scripts\\python.exe"` (use double backslashes `\\`).
        *   Example (macOS/Linux): `"command": "/path/to/your/project/venv/bin/python"`
    *   Ensure the path in `"args"` (`"src.main"`) is correct relative to where Claude Desktop will execute the command (usually the project root if configured as above).

**c. Restart Claude Desktop:**
*   Completely close and reopen Claude Desktop for the changes to take effect.

**d. Verify Connection:**
*   Once Claude Desktop restarts, look for a small **hammer icon** (🔨) in the bottom status bar or near the chat input area. This indicates that Claude has successfully connected to your local MCP server. If you hover over it, it should mention "suno".

## 3. Using the Suno Tools (MVP Features)

You can now use the `@suno` command in Claude Desktop.

**a. Simple Song Generation:**
*   Type a prompt describing the song you want.
    ```
    @suno generate a funky disco track about dancing robots
    ```
    Or:
    ```
    @suno generate a sea shanty about finding treasure on a remote island
    ```

**b. Custom Song Generation (Lyrics):**
*   Provide lyrics and optionally a style/genre tag.
    ```
    @suno create a custom song with the style "acoustic folk ballad" and the following lyrics:

    [Verse 1]
    Sunrise paints the mountains gold
    A story whispered, centuries old
    River flows, a steady friend
    On this quiet path, time transcends

    [Chorus]
    Oh, the simple life, a gentle breeze
    Rustling through the ancient trees
    Finding peace in morning light
    Everything just feels so right
    ```

Claude will process the request using your local server, and the generated audio should appear in the chat interface shortly after.

## 4. Common Troubleshooting Tips

*   **No Hammer Icon (🔨) in Claude:**
    *   **Restart Claude:** Did you fully restart Claude Desktop after editing the config file?
    *   **Check Config Path:** Double-check the `claude_desktop_config.json` file. Is the `"command"` path to Python (especially if using a venv) correct? Is the `"args"` value `["-m", "src.main"]` correct? Syntax errors in the JSON can also prevent loading.
    *   **Run Manually:** Open your terminal, activate your virtual environment (if used), navigate to the project root directory, and run the command from your config file manually: `python -m src.main`. Does it start without errors? Watch the terminal output for clues. Fix any errors reported there.
    *   **Check `.env`:** Ensure the `.env` file exists in the project root and `SUNO_COOKIE` is set. The server might fail to start if the cookie is missing.
*   **Errors During Song Generation:**
    *   **Check Logs:** Look at the terminal window where your server is running (if you ran it manually) or check Claude's output. Errors from the Suno API might be shown there.
    *   **Cookie Issues:** The most common problem is an invalid or expired `SUNO_COOKIE` in your `.env` file. The cookie might expire after a day or two. Repeat Step 1c to get a fresh cookie and update your `.env` file. Ensure the *entire* cookie value was copied correctly.
    *   **Suno API Changes:** Suno's internal API can change without notice. If it stops working suddenly, the server code might need an update. Check the project's repository or community channels for recent updates or known issues.
    *   **Rate Limits/Usage:** You might hit usage limits on your Suno account. Check your account status on the Suno website.

That's it for the MVP! Enjoy generating music with Suno and Claude.
