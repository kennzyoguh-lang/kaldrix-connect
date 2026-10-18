# Install in your assistant

Every assistant that speaks MCP needs the same three things:

* **command:** `uvx`
* **arguments:** `--from git+https://github.com/kennzyoguh-lang/kaldrix-connect kaldrix-connect`
* **environment:** `KALDRIX_AGENT_KEY` = the limited key from your dashboard ("Connect your own AI assistant")

You need [`uv`](https://docs.astral.sh/uv/getting-started/installation/) installed (`uvx` comes with it). Restart the assistant after you add the connector.

> The settings files below are the usual shape for each tool. Tools change their settings often, so if one does not match, check that tool's own documentation for "MCP servers" and use the three things above.

## Claude Code

```
claude mcp add kaldrix -e KALDRIX_AGENT_KEY=kz_YOUR_AGENT_KEY -- uvx --from git+https://github.com/kennzyoguh-lang/kaldrix-connect kaldrix-connect
```

Or as a plugin (adds the skill and `/kaldrix-start`; set `KALDRIX_AGENT_KEY` in your environment first):

```
/plugin marketplace add kennzyoguh-lang/kaldrix-connect
/plugin install kaldrix@kaldrix
```

## Claude Desktop

Add to `claude_desktop_config.json` (Settings → Developer → Edit config):

```json
{
  "mcpServers": {
    "kaldrix": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/kennzyoguh-lang/kaldrix-connect", "kaldrix-connect"],
      "env": { "KALDRIX_AGENT_KEY": "kz_YOUR_AGENT_KEY" }
    }
  }
}
```

## Cursor

`~/.cursor/mcp.json` (or `.cursor/mcp.json` in a project), same shape as above.

## VS Code (GitHub Copilot, agent mode)

`.vscode/mcp.json`:

```json
{
  "servers": {
    "kaldrix": {
      "type": "stdio",
      "command": "uvx",
      "args": ["--from", "git+https://github.com/kennzyoguh-lang/kaldrix-connect", "kaldrix-connect"],
      "env": { "KALDRIX_AGENT_KEY": "kz_YOUR_AGENT_KEY" }
    }
  }
}
```

## Codex

`~/.codex/config.toml`:

```toml
[mcp_servers.kaldrix]
command = "uvx"
args = ["--from", "git+https://github.com/kennzyoguh-lang/kaldrix-connect", "kaldrix-connect"]
env = { KALDRIX_AGENT_KEY = "kz_YOUR_AGENT_KEY" }
```

## ChatGPT

ChatGPT connects to MCP servers over the internet, not on your computer, so it needs a hosted version of this connector. That is not built yet.

## Check that it works

Ask your assistant: **"Who am I with Kaldrix?"** It should call `kaldrix_who_am_i` and tell you its public key. If it says the agent key is not set, the `KALDRIX_AGENT_KEY` setting did not reach the connector: check the spelling and restart the assistant.

## Where the agent's own key is kept

In `~/.kaldrix/connector.json` (set `KALDRIX_HOME` to change it). It never leaves your computer. Keep that file private.
