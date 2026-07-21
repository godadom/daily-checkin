# NovalPie daily check-in for QingLong

This Python 3 project performs the normal NovalPie daily check-in for accounts the operator is authorized to automate. Local shells and QingLong use the same entry point: `python3 run.py`.

For each account it queries today's record with `GET /api/users/me/checkins`, skips submission when `today_checked` is true, otherwise sends one bodyless `POST /api/users/me/checkins`, then queries today's record again. A POST is never blindly repeated. NovalPie's browser-side “auto check-in on visit” setting may remain enabled: this project detects an existing record and returns `ALREADY_DONE` without another POST.

## Configuration

Store secrets in QingLong's protected environment-variable page, never in this repository or the task command.

The verified site address and API paths are source-controlled in `src/checkin/site_config.py`: `https://novalpie.cc` and `/api/users/me/checkins`. Do not create `CHECKIN_BASE_URL`, `CHECKIN_STATUS_PATH`, or `CHECKIN_ACTION_PATH`; the application rejects those legacy override names so a token cannot be redirected to another host.

| Variable | Required | Purpose |
| --- | --- | --- |
| `CHECKIN_TOKEN` | single account | Authorized token value without the `Bearer ` prefix |
| `CHECKIN_ACCOUNT_NAME` | no | Non-sensitive log alias |
| `CHECKIN_ACCOUNTS` | multiple accounts | JSON array of token accounts; overrides the single token |
| `CHECKIN_TIMEZONE` | no | IANA timezone, default `Asia/Shanghai` |
| `CHECKIN_CONNECT_TIMEOUT`, `CHECKIN_READ_TIMEOUT` | no | Connection/read timeout seconds |
| `CHECKIN_MAX_RETRIES` | no | Safe GET retry limit; default 2 |
| `CHECKIN_JITTER_MAX_SECONDS` | no | Optional small scheduling jitter; default 0 |
| `CHECKIN_NOTIFY_MODE` | no | `log` or `off`; no external sender is bundled |

Multi-account example: `[{"name":"account-a","token":"<REDACTED_TOKEN>"}]`.

Obtain your own token only through NovalPie's normal signed-in browser flow. Copy the token value from an authorized request's `Authorization: Bearer ...` header directly into QingLong's protected variable; do not paste it into chat, logs, screenshots, or files. The project does not automate login or token refresh.

## Run and verify

```text
python3 -m pip install -r requirements.txt
python3 tests/run_offline.py
python3 run.py
```

Offline tests block all sockets. A live run occurs only after a protected token is configured. Exit code `0` means every account is `SUCCESS` or `ALREADY_DONE`; `2` configuration, `3` authentication expired, `4` temporary failure, `5` site change, `6` unsupported security challenge, `7` access denied, and `70` internal error. Mixed failures prioritize access denied, security challenge, configuration, site change, authentication, temporary failure, then internal error.

| State | Meaning |
| --- | --- |
| `SUCCESS` | The POST was followed by a status query that confirmed today's record. |
| `ALREADY_DONE` | Today's record already exists or the server explicitly reports a completed check-in. |
| `AUTH_EXPIRED` | The protected token was rejected and must be replaced through normal login. |
| `ACCESS_DENIED` | The authenticated account received an explicit permission denial. |
| `TEMPORARY_ERROR` | A bounded timeout, rate limit, or recoverable server error occurred. |
| `SITE_CHANGED` | The verified endpoint or JSON contract no longer matches. |
| `CONFIG_ERROR` | A required environment value is missing or malformed. |
| `UNSUPPORTED_SECURITY_CHALLENGE` | A manual security challenge was detected and automation stopped. |
| `INTERNAL_ERROR` | An unclassified internal failure was safely redacted. |

## Safety

The client uses Bearer authentication, has no request body or CSRF header for the verified check-in request, caps responses at 1 MiB, and logs only redacted summaries. It does not bypass CAPTCHA, WAF, device verification, WebAuthn, SMS verification, permissions, or rate limits. See [site analysis](docs/site-analysis.md), [QingLong deployment](DEPLOY_QINGLONG.md), and [security policy](SECURITY.md).

This site project intentionally targets QingLong only. GitHub Actions deployment is not generated.
