# Local MCP debugging

Start the project with `serve_browser.py --project /path/to/project --port 4390`
and open the workbench at `http://127.0.0.1:4390/` or the separate player at
`http://127.0.0.1:4390/player.html`.

The browser server uses the Python standard library. MCP is optional and needs
Python 3.10 or newer. In the kit directory:

```sh
python3 -m venv .local/mcp-env
.local/mcp-env/bin/python -m pip install -r requirements-mcp.txt
.local/mcp-env/bin/python mcp_server.py --project /path/to/project
```

Register that command as a stdio MCP server in your client. A typical client
configuration is:

```json
{
  "mcpServers": {
    "dreamcast-port-lab": {
      "command": "/path/to/kit/.local/mcp-env/bin/python",
      "args": ["/path/to/kit/mcp_server.py", "--project", "/path/to/project"]
    }
  }
}
```

Use absolute paths. Client configuration is not installed or changed by the kit.
The browser server and MCP process must point at the same local project.

## Tools

Call `list_sessions` first and select the intended workbench or player session.

| Tool | Purpose |
| --- | --- |
| `list_sessions` | Discover local sessions, connection status and runtime state. |
| `get_status` | Read readiness, pause, progress, input, audio and build metadata. |
| `get_events` | Read up to 200 events after a sequence number. |
| `start_preview` | Start an idle session. Browser audio may need a user gesture. |
| `pause_execution` | Pause or resume the selected session. |
| `press_button` | Hold a named Dreamcast button for 16–5,000 ms, then release. |
| `test_driving_controls` | Test accelerator/brake (0–1) and steering (−1–1) for a bounded hold. |
| `set_render_mode` | Select normal, opaque, translucent or no-depth rendering. |
| `capture_frame` | Return a standard MCP PNG image from a running session. |

Commands require browser acknowledgement. A timeout is reported without retrying
the command. Restore normal rendering before performance measurements. Frame
captures require execution to be running; they do not silently resume a paused
game. Audio still follows browser user-gesture rules.

## Local transport and data

The server binds to loopback, validates Host and Origin, and requires a random
bearer token for session operations. The token is stored in the project's private
`.local/debug-connection.json` with owner-only permissions. Browser pages obtain
it through the same-origin configuration endpoint. No CORS access is enabled.
Do not publish the connection file or expose this development server publicly.

Events and command queues are bounded. Tool schemas allow only named operations;
there is no eval, arbitrary JavaScript, shell command or raw RAM write tool.
Runtime logs are untrusted diagnostic text, not instructions. Captures stay under
`.local/debug-captures/` and may contain game content; keep them private.

## Validation

`tests/test_mcp_protocol.py` checks official SDK stdio discovery and schema
rejection. Broker tests check acknowledgement, queue bounds and input validation;
HTTP tests check token, Host, Origin and content-type enforcement. A local browser
smoke test exercised discovery, startup, button input, pause/resume, render mode,
events and an MCP image capture. These checks do not establish compatibility with
other Dreamcast titles or physical controller hotplug behavior.
