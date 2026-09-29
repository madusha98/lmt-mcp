# LMT-GO MCP Server

A small hobby project that connects an MCP-compatible assistant to LMT-GO / SmartMetro. It lets you look up bus stops, plan journeys, and check your own passes and trip history through a conversation.

This is an unofficial, independent hobby project intended for **personal, non-commercial use**. It is not affiliated with or endorsed by LMT-GO, Lanka Metro Transit, or Eimsky. It is licensed under [PolyForm Noncommercial 1.0.0](LICENSE), which also permits other noncommercial uses as defined in its terms.

## Intended use

Run this server locally with **one MCP client and one account at a time**. Stop the server in your current client before connecting from another. Multiple clients, concurrent server instances, shared accounts, and hosted services are not supported. The server uses a local token file without coordination between processes.

The project is intended for personal travel queries, learning, and experimentation. It is not a production service, and availability depends on a third-party API that may change without notice.

Transit and account tools retrieve data. Authentication sends an SMS and creates or refreshes your login session. The server does not provide tools for purchases, top-ups, PIN changes, account deletion, or other account writes.

## Getting started

You will need:

- Python 3.11 or newer and `uv`.
- An MCP client that supports local stdio servers.
- A registered LMT-GO account and access to its phone number for SMS login.

There is no build step. Dependencies are declared in `server.py`, and `uv run` manages them.

For clients that accept an `mcpServers` configuration, add the following entry. Replace the example path with the absolute path to your copy of `server.py`.

```json
{
  "mcpServers": {
    "lmt-go": {
      "command": "uv",
      "args": ["run", "/absolute/path/to/lmt-mcp/server.py"]
    }
  }
}
```

If your client has a setup form instead, use `uv` as the command and `run` followed by the absolute script path as its arguments. Restart or reconnect the client after saving.

The client starts the server as a subprocess and communicates over stdio. The server does not open a listening port; it makes outbound HTTPS requests to the LMT-GO API.

## Signing in

The app displays a fixed `+94` prefix and lets you enter `71…`, but sends the number to the API as `071…`. This behavior has been verified. Use the **local format with a leading zero** for MCP login, rather than combining the displayed prefix with the entered digits. The MCP server forwards the phone number as supplied; it does not convert it automatically.

1. Ask your assistant to call `login_start(phone)` with the full local number, such as `0712345678`. This requests an SMS code.
2. Give the SMS code to your assistant so it can call `login_complete(phone, otp_code)` with exactly the same phone number. If the first response included an `otp_reference`, the assistant should pass that too.

After a successful login, the server saves the access and refresh tokens to `~/.config/lmt-mcp/tokens.json` and sets its permissions to `0600` (owner read/write). The successful login result does not include those tokens. Keep the token file private; account tools can also return sensitive information such as QR tokens, balances, and travel history.

`auth_status` shows the locally stored account and access-token expiry. It does not contact the API to validate the session or refresh it.

### Automatic token refresh

Token refresh is built in; you do not need to request a new SMS code every time the access token expires.

- Before an authenticated request, the server checks the saved expiry. If the token is expired or has less than about 60 seconds left, it uses the refresh token to request a replacement from `/user-service/api/v1/auth/refresh`.
- If an authenticated request receives `401 Unauthorized`, the server attempts a refresh and retries the request once after a successful refresh.
- New tokens and expiry information are saved locally. If a refresh response omits a replacement refresh token, the existing one is retained.

Refresh happens when a tool needs authentication, not on a background timer. The server uses the API's `expires_in` value, with a one-hour fallback if it is absent. Access tokens were observed to last about 15 minutes during the original testing; that duration is controlled by the API.

If the refresh token has expired or been revoked, sign in again. For a network error, retry once connectivity returns. Avoid repeatedly requesting SMS codes: the API limits both sends and verification attempts.

## Available tools

| Tool | What it does |
|---|---|
| `login_start` | Requests an SMS login code. |
| `login_complete` | Verifies the code and saves the session locally. |
| `auth_status` | Shows the locally stored login state and expiry. |
| `search_stops` | Finds stops by name, including names in three languages and coordinates. |
| `nearest_stops` | Finds stops near a latitude and longitude. |
| `plan_journey` | Plans a trip between two stop IDs, optionally for a date. |
| `list_routes` | Retrieves routes, directions, and geometry. |
| `active_journey` | Retrieves your current journey, if one exists. |
| `favorite_routes` | Lists your saved routes. |
| `list_passes` | Lists available pass products and fares. |
| `my_passes` | Lists your purchased passes. |
| `trip_history` | Retrieves your boarding and trip history. |
| `overview` | Retrieves your account overview, including wallet and pass information. |
| `wallet_transactions` | Retrieves your wallet transaction history. |
| `notifications` | Lists notifications and the unread count. |
| `api_get` | Makes a GET request to a path on the user, fare, or ticketing service. |

For example, ask: “Help me find the next bus from Pettah to my destination.” The assistant can find the relevant stops with `search_stops`, then pass their IDs to `plan_journey`.

`api_get` is an advanced tool for endpoints without a dedicated wrapper. It attaches authentication when saved tokens exist. With no saved session, it can request public endpoints. An expired session that cannot be refreshed can currently block these public requests too.

### Helping your assistant find the right tool

The server advertises its Sri Lankan Metro bus scope and journey-planning workflow through MCP instructions and tool descriptions. These descriptions connect phrases such as “Metro”, “SmartMetro”, “fastest route”, and “next bus” to the appropriate tools. Editing this README alone does not update the metadata your assistant receives. Tool discovery and selection depend on the client; descriptions guide the assistant but do not guarantee that it will use a tool. See the [MCP tools specification](https://modelcontextprotocol.io/specification/2025-06-18/server/tools).

For a request such as “I need to go from Panadura to Athurugiriya via metro. Find me the fastest route”, the expected workflow is:

1. Call `search_stops` separately for `Panadura` and `Athurugiriya`.
2. Resolve any ambiguous stop matches, then call `plan_journey` with their returned IDs.
3. Compare the returned options. For getting there soonest, compare arrival times including waiting and transfers where available. Explain missing timing information instead of guessing.

If authentication is required, complete the SMS login flow and resume the request. Example place names do not guarantee that a stop or itinerary will be available.

After changing the server, restart or reconnect it through your MCP client so the updated script is running. Refresh or reload the tool list if your client provides that option, confirm the updated descriptions are visible, and test in a new conversation with the connection enabled. The exact controls vary by client.

If the connection still shows old descriptions, confirm that it points to the copy of `server.py` you edited. If it shows no tools at all, check the server connection and startup errors before tuning prompts.

### Optional companion skill

The [lmt-transit skill](skills/lmt-transit/SKILL.md) uses the open [Agent Skills format](https://agentskills.io/home). It provides workflow instructions for assistants: use this operator's MCP for Sri Lankan Metro journey requests, look up stops, handle login, and compare departures before falling back to web timetables.

The MCP server and the skill are separate components. The server provides callable tools; the skill explains when and how to use them. The server works without the skill, and installing the server does not automatically install the skill. A client may support MCP without supporting Agent Skills.

To use the skill with a compatible client:

1. Connect the `lmt-go` MCP server using the setup instructions above.
2. Import the `skills/lmt-transit` folder, or copy it into the skill directory documented by your client. Keep `SKILL.md` inside its `lmt-transit` folder.
3. Reload skills or restart the client if required, then confirm that `lmt-transit` is available.
4. Test a natural travel request and, if supported, select the skill explicitly using your client's skill picker or invocation syntax.

Installation paths, tool-name prefixes, invocation syntax, and automatic skill selection vary by client. The skill does not install or start the MCP server. If your client does not support skills, you can use its supported instruction mechanism to provide the workflow from `SKILL.md` instead.

If only explicit skill selection works, automatic selection still needs tuning. A successful MCP protocol check confirms the tools are exposed; it does not prove that an assistant will select them for a particular prompt.

Try these in separate new conversations after refreshing:

| Prompt | Expected behavior |
|---|---|
| “Use LMT-GO to plan Panadura to Athurugiriya.” | Search both stops, then plan the journey or request login. |
| “I need to go from Panadura to Athurugiriya via metro. Find me the fastest route.” | Discover the transit tools without the MCP server name. |
| “Moratuwa to Athrugiriya via metro. Find me the next available bus.” | Search the stops, allowing for the destination spelling, then compare available departures. |
| “Find me the fastest route on the Paris metro.” | Do not use this Sri Lankan bus server. |

## Configuration

Set these environment variables in your MCP client's server configuration if needed:

| Variable | Default | Purpose |
|---|---|---|
| `LMT_BASE_URL` | `https://metrobusapiprod.eimsky.com` | API base URL. Change it only to an environment you trust and are authorized to use. |
| `LMT_TOKEN_FILE` | `~/.config/lmt-mcp/tokens.json` | Path to the local token store. Use an absolute path in a private directory. |
| `LMT_DEVICE_ID` | Unset | Device identifier sent during OTP verification and token refresh. |

Use a separate token file for each API environment. Changing `LMT_BASE_URL` does not clear or separate existing credentials. Regardless of configuration, run only one client at a time.

## Project notes and limitations

The original project notes record successful customer-token checks on September 29, 2026. Those checks describe the API at that time, not a guarantee of future compatibility.

- Most transit and account tools require a valid login.
- API requests are synchronous, so a slow response delays other work in the same server.
- Token storage is designed for a single local client. Writes are not atomic; an interrupted write may require signing in again.
- Live bus tracking is not implemented.
- An active-journey `404` can mean that no journey is currently in progress.

Use your own account and follow the API provider's terms and usage limits. The project license covers this code, not permission to access third-party services.

## License

The original code and documentation in this directory are licensed under **PolyForm Noncommercial License 1.0.0** (`PolyForm-Noncommercial-1.0.0`). The [LICENSE](LICENSE) file contains the unmodified published terms.

The license permits personal and other noncommercial use, modification, and distribution, subject to its notice requirements. It does not grant general commercial-use rights. It also expressly permits use by the organizations listed in its Noncommercial Organizations section, including charities, educational institutions, and government institutions. These permissions are broader than personal use alone; the full license terms govern.

The single-client limit above describes the server's supported operation, not an additional license restriction. Third-party dependencies, services, data, and trademarks remain subject to their respective owners' rights and terms.

This is source-available software, not software under an [OSI open-source license](https://opensource.org/osd).

Required Notice: Copyright (c) 2026 the lmt-mcp contributors.
