# NodeSeek daily attendance for QingLong

This Python 3 project runs the verified, deterministic NodeSeek daily-attendance flow for accounts you are authorized to automate. It uses one shared entry point for local shells and QingLong: `python3 run.py`.

It first queries `GET /api/attendance/board?page=1`. A non-null attendance record means `ALREADY_DONE`; otherwise it sends one attendance POST. `CHECKIN_ATTENDANCE_MODE=fixed` uses `random=false`, while `random` uses `random=true`. A successful response must contain `success: true`, a string message, and numeric gain/current fields. It does not retry a POST. If its result is ambiguous, it performs one state query and reports a non-zero failure unless the site confirms attendance.

## Configuration

Set these values in QingLong's protected environment-variable store, never in the task command or repository:

| Variable | Required | Purpose |
| --- | --- | --- |
| `CHECKIN_BASE_URL` | yes | Must remain `https://www.nodeseek.com` |
| `CHECKIN_STATUS_PATH` | yes | Verified path `/api/attendance/board?page=1` |
| `CHECKIN_ATTENDANCE_MODE` | no | `fixed` (default, 5 chicken legs) or `random` (“try luck”) |
| `CHECKIN_COOKIE` | single account | Full authorized Cookie header value |
| `CHECKIN_ACCOUNT_NAME` | no | Non-sensitive log alias |
| `CHECKIN_ACCOUNTS` | multi-account | JSON array of cookie accounts; overrides the single-account cookie |
| `CHECKIN_TIMEZONE` | no | IANA zone, default `Asia/Shanghai` |
| `CHECKIN_CONNECT_TIMEOUT`, `CHECKIN_READ_TIMEOUT`, `CHECKIN_MAX_RETRIES` | no | Bounded HTTP behavior |
| `CHECKIN_NOTIFY_MODE` | no | `log` or `off`; no external notifier is bundled |

Example multi-account value: `[ {"name":"account-a","cookie":"<REDACTED_COOKIE>"} ]`.

## Run and verify

```text
python3 -m pip install -r requirements.txt
python3 tests/run_offline.py
python3 run.py
```

Offline tests deny all sockets. A live run happens only when a valid protected Cookie is configured. Exit code `0` means every account is `SUCCESS` or `ALREADY_DONE`; `2` configuration, `3` expired authentication, `4` temporary failure, `5` site change, `6` unsupported security challenge, `7` access denied, and `70` internal error. Mixed failures use this priority: access denied, security challenge, configuration, site change, authentication, temporary failure, then internal error.

| State | Meaning |
| --- | --- |
| `AUTH_EXPIRED` | The site returned HTTP 401; replace the protected cookie through the normal login flow. |
| `ACCESS_DENIED` | An explicit permission-denial response was received. Stop the task and verify account permission or site policy. |
| `TEMPORARY_ERROR` | Network failure, rate limiting, or 5xx; wait for the next scheduled run. |
| `SITE_CHANGED` | The verified endpoint or JSON contract no longer matches. Disable the task and refresh sanitized evidence. |
| `CONFIG_ERROR` | An environment value is missing, malformed, or changed from the verified endpoint. |
| `UNSUPPORTED_SECURITY_CHALLENGE` | A manual security control was detected. Stop instead of bypassing it. |

## Safety

Do not commit credentials. Logs redact cookie-like values and never retain raw requests or responses. The project does not automate login, CAPTCHA, WAF, device verification, SMS, WebAuthn, or proxies. `random` is an explicit operator-selected normal attendance mode, not a retry or evasion mechanism. This repository intentionally targets QingLong only; GitHub Actions deployment is not included. See [SECURITY.md](SECURITY.md), [site analysis](docs/site-analysis.md), and [QingLong deployment](DEPLOY_QINGLONG.md).
