# NodeSeek attendance analysis

## Scope

- Site: `https://www.nodeseek.com/`
- Attendance page: `https://www.nodeseek.com/board`
- Deployment target: QingLong with Python 3.
- Operator confirmation: authorization was explicitly confirmed for the operator's normal daily attendance.
- Evidence: an authorized, already logged-in Chrome session on 2026-07-17. No cookies, account identifiers, request headers, or raw responses were retained.

## Verified normal request flow

| Stage | Method and URL | Authentication | Success evidence | Confidence |
| --- | --- | --- | --- | --- |
| Read today's state | `GET /api/attendance/board?page=1` | Existing session cookie | `record` is `null` before attendance; a correctly shaped object after attendance | Verified in browser session |
| Fixed attendance | `POST /api/attendance?random=false` | Existing session cookie | HTTP 200 JSON with `success: true`, string `message`, numeric `gain`, numeric `current` | Verified in browser session |
| Random attendance | `POST /api/attendance?random=true` | Existing session cookie | Uses the same JSON result contract | Supported by NodeSeekX's published `signIn` module; not live-run because fixed attendance had already completed |

The browser menu's “签到” control only navigates to `/board`; it does not itself submit attendance. The page also offers a random-reward option. NodeSeekX's published `signIn` source maps that option to the same API with `random=true`, while its fixed mode uses `random=false`. The project exposes this choice as `CHECKIN_ATTENDANCE_MODE`, defaulting to `fixed`.

## Request contract

- The status request uses the session Cookie supplied at runtime and has no request body.
- The attendance request is a `POST` with no request body and one of two explicitly selected static queries: `random=false` for `fixed`, `random=true` for `random`.
- No CSRF header, CSRF query parameter, or CSRF body field was observed in this verified request. The implementation does not invent one.
- Only the business fields listed below are read; complete responses and request headers are never logged.

## State mapping

- `SUCCESS`: the POST returns HTTP 200 and the verified `success`, `message`, `gain`, and `current` field types.
- `ALREADY_DONE`: the status response contains a well-formed non-null `record`.
- `AUTH_EXPIRED`: HTTP 401.
- `ACCESS_DENIED`: HTTP 403 only when a JSON business code explicitly states `access_denied`, `forbidden`, or `permission_denied`; an unclassified 403 fails closed as `SITE_CHANGED`.
- `TEMPORARY_ERROR`: connection/read failure, HTTP 429, or 5xx. An ambiguous POST is never repeated; the status endpoint is queried once instead.
- `SITE_CHANGED`: unexpected JSON, fields, types, HTTP status, or HTML response.
- `UNSUPPORTED_SECURITY_CHALLENGE`: a detected WAF, CAPTCHA, or other manual security challenge. The project stops and never bypasses it.

## State evidence

The field names and types above came from a real successful response. A non-null board `record` was observed after attendance. No expired-cookie, access-denied, repeated-attendance, or challenge response sample was collected. The permission-code mapping is a conservative defensive contract rather than a NodeSeek-observed response; unknown 403 responses remain `SITE_CHANGED` pending new sanitized evidence.

## Limits and assumptions

- Cookie authentication was observed as browser session state. The project accepts a complete authorized `Cookie` header value only through `CHECKIN_COOKIE` or `CHECKIN_ACCOUNTS`; it does not log in, refresh tokens, inspect browser storage, or persist a session.
- The `record`-is-null pre-attendance interpretation is supported by the observed page state and board response. Revalidate it with a sanitized capture if NodeSeek changes the attendance page.
- The random query mapping is source-supported but not live-verified during this run because the account had already used the fixed mode. A later authorized, sanitized capture can elevate it to browser-verified evidence. The project otherwise does not use browser automation, proxying, fingerprint changes, or challenge handling.
