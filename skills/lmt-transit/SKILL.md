---
name: lmt-transit
description: Find Sri Lankan Metro bus routes, next departures, fastest journeys, stops and fares using the connected LMT-GO / SmartMetro / Lanka Metro Transit MCP. Use for travel between Sri Lankan towns such as Moratuwa, Panadura and Athurugiriya when the user mentions Metro or this operator, even without naming the MCP. Excludes other countries' metro systems, driving directions and requests to develop the server.
---

# Sri Lankan Metro bus journeys

This skill requires an MCP-capable client with the LMT-GO server connected.
It provides workflow instructions and does not install or start the server.

Use the connected LMT-GO MCP for this operator's stops and journey options.
For these requests, query the MCP before using general web search or browser
timetables, unless the user explicitly asks for another source. The connection
is normally named `lmt-go`; tool-name prefixes and discovery controls vary by
client. Match the server and the advertised tool names below rather than
assuming a particular namespace or invocation syntax.

1. Locate `search_stops` and `plan_journey` in the available MCP tools. If the
   client defers tools, use its tool discovery facility to load them. If they
   are unavailable, report the connection problem; do not imply the API was
   checked. Web information may be a fallback, with its source and limits stated.
2. Search the origin and destination separately. For “Moratuwa to Athrugiriya
   via metro”, search “Moratuwa” and “Athurugiriya”. Resolve ambiguous matches
   with the user. Use returned stop IDs; never invent IDs or substitute a
   different boarding location without explaining and confirming the choice.
3. Call `plan_journey` with those IDs. Omit `date` for the next available trip;
   pass a requested date as `YYYY-MM-DD`. If an API result is empty, say what
   was not found rather than inferring that the operator has no service.
4. For the next bus, compare returned departure times. For the fastest arrival,
   compare arrival times and include waiting and transfers where provided.
   Distinguish earliest arrival from shortest trip duration. Explain route
   codes, boarding and transfer stops, times and fares using returned data.
   Do not claim real-time vehicle tracking or guaranteed arrival times.

If a tool requires login, ask for the user's phone number and offer the SMS
login flow. Use the local leading-zero format, for example `0712345678`, and
the same phone in `login_start` and `login_complete`. Request an SMS only when
the user authorizes login; obtain the code from them and pass `otp_reference`
if returned. Resume the journey lookup after login. Do not read token files
or print credentials. For rate limits, stop retrying and explain the response.

An API error is not evidence that a route is unavailable. If using a fallback
source, distinguish it from MCP results and do not present an old timetable
as the next available departure.
