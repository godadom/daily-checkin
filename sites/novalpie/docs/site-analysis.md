# NovalPie check-in analysis

## Scope and evidence

- Site and entry page: `https://novalpie.cc/`
- Check-in page: the signed-in user's “签到” tab; no account-specific URL is retained here.
- Deployment target: QingLong with Python 3.11+.
- Authorization scope — the operator explicitly confirmed account ownership, automatic check-in permission, and permission for real interface evidence on 2026-07-21.
- Evidence: an authorized logged-in Chrome session, sanitized Network/CDP summaries, and the site's loaded Nuxt client code. No token, authorization value, user identifier, email, raw response, browser storage, or personal page data was saved.

## Verified normal flow

| Stage | Method and URL | Authentication | Success evidence | Confidence |
| --- | --- | --- | --- | --- |
| Read current user preference | `GET /api/users/me` | Bearer authentication header | JSON includes numeric `auto_checkin`; the visible switch was enabled | Verified in the authorized browser session |
| Read today's attendance | `GET /api/users/me/checkins?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD` | Bearer header | HTTP 200, `success: true`, `data.today_checked` Boolean, `data.records` object | Verified with a sanitized live response shape |
| Submit attendance | `POST /api/users/me/checkins` | Bearer header | Bodyless request; success must be followed by today's status query | Method/path/header/body verified from client code and a live already-done request |
| Confirm attendance | same GET as above | Bearer header | `today_checked: true` and a current-date record with numeric `points`, numeric `streak`, and string `time` | Verified with a sanitized live response shape |

The browser client waits until authentication is available, checks whether `auto_checkin` is enabled, and attempts one automatic check-in per local calendar day after a normal page visit. The browser preference is independent of this QingLong project. The project always queries server state first, so leaving the browser switch enabled does not cause a blind duplicate POST.

## Request contract

- Authentication is a Bearer token. The observed successful API request had an `Authorization` header and no Cookie or CSRF header.
- The POST has no query parameters and no request body. Its observed required application headers were `Accept` and `Authorization`; this project adds an honest User-Agent.
- The status GET uses only `start_date` and `end_date`, both set to the current date in `CHECKIN_TIMEZONE`.
- A live already-done POST returned HTTP 400, `success: false`, and a message explicitly stating that today's check-in was already completed. The loaded client also recognizes the same already-done semantics and another UI path handles HTTP 409.
- The exact HTTP 200 success-body shape was not live-captured because the account was already checked in. Loaded client code indicates a points field, but the implementation does not rely on it: it requires the follow-up GET to confirm today's record.
- No token refresh, login automation, CSRF exchange, request signing, browser fingerprinting, proxying, or security challenge was observed or implemented.

## State evidence and mapping

- `SUCCESS`: one POST was sent and the follow-up GET confirms today's valid record.
- `ALREADY_DONE`: the preflight GET reports `today_checked: true`, or an HTTP 400/409 response contains the evidenced already-done message.
- `AUTH_EXPIRED`: HTTP 401 or an explicit authentication rejection.
- `ACCESS_DENIED`: HTTP 403 only with explicit permission-denial semantics; unknown 403 remains `SITE_CHANGED`.
- `TEMPORARY_ERROR`: bounded network failure, HTTP 429, or recoverable 5xx. An ambiguous POST is never repeated; one status query follows.
- `SITE_CHANGED`: malformed JSON, HTML/login content, an unclassified status, or missing/contradictory required fields.
- `CONFIG_ERROR`: missing/invalid environment configuration or a changed verified endpoint.
- `UNSUPPORTED_SECURITY_CHALLENGE`: CAPTCHA, WAF, device proof, WebAuthn, SMS, or another manual challenge; stop rather than bypass it.

## Remaining assumptions and limits

- A future authorized run on a not-yet-checked-in day can confirm the optional success response's points field. Correctness does not depend on that field because the status query is authoritative.
- Token lifetime and replacement cadence are not documented by the captured flow. On HTTP 401, use NovalPie's normal login and replace the protected token manually.
- Rate-limit `Retry-After` behavior was not triggered live. The client honors standard seconds/date values with a 60-second safety cap and otherwise waits for the next schedule.
