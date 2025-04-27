# Claude Desktop Integration for Suno MCP Server

This document outlines the steps to integrate the Suno MCP server with Claude Desktop and provides basic usage examples.

## 1. Configure Claude Desktop

You need to edit the Claude Desktop configuration file.

*   **Windows Location:** `%APPDATA%\Claude\claude_desktop_config.json`
    *   You can usually open this folder by typing `%APPDATA%\Claude` into the Windows File Explorer address bar.

If the file `claude_desktop_config.json` doesn't exist, create it. Add the following JSON content. If the file *does* exist and already has content (like `"mcpServers": {}`), carefully merge the `"suno"` configuration into the existing `mcpServers` object.

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

**Important Notes:**

*   This configuration assumes you are running Claude Desktop from the root directory of your `suno-mcp` project *or* that your project's `src` directory is accessible via `python -m src.main`.
*   Ensure your Python executable is in your system's PATH.
*   If you are using a Python virtual environment, you might need to specify the full path to the Python executable within that environment in the `"command"` field (e.g., `"command": "C:\\path\\to\\your\\venv\\Scripts\\python.exe"`).
*   **Restart Claude Desktop** after saving the changes to `claude_desktop_config.json` for the changes to take effect.

## 2. Example Prompts for Claude Desktop

Use these prompts directly in the Claude Desktop chat interface to test the integration:

**Example 1: Generate Song (Simple Prompt)**

```
@suno generate a cheerful upbeat pop song about walking a dog in the park on a sunny day
```

**Example 2: Generate Custom Song (Lyrics and Style)**

```
@suno create a custom song with the style "80s synthwave ballad" and the following lyrics:

[Verse 1]
Neon lights reflect in the rain
Another lonely night, feeling the pain
Searching for a signal, lost in the code
A digital ghost on this empty road

[Chorus]
Synthwave dreams, fading in the night
Chasing echoes in the pale moonlight
Heartbeat drums, a retro sound
Lost in the circuits, never to be found
```

## Expected Interaction

1.  Claude recognizes the `@suno` command and the specific tool (`generate` or `create a custom song`).
2.  Claude sends the request details to your local Suno MCP server running via the configured command.
3.  Your MCP server processes the request, interacts with the Suno API, and generates the song.
4.  The server returns a resource URI (e.g., `resource:suno/audio/<song_id>.mp3`) back to Claude.
5.  Claude Desktop should display an embedded audio player or a link for the generated song in the chat.
