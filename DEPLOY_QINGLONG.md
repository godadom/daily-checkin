# QingLong deployment

Upload or clone this project into a QingLong scripts directory. From that directory, use Python 3.11+ and run:

```text
python3 -m pip install --disable-pip-version-check -r requirements.txt
python3 tests/run_offline.py
```

In QingLong's environment-variable page, add `CHECKIN_BASE_URL`, `CHECKIN_STATUS_PATH`, `CHECKIN_ATTENDANCE_MODE`, `CHECKIN_COOKIE`, and optionally `CHECKIN_ACCOUNT_NAME`. Copy the non-secret values from `.env.example`; set the cookie only in the protected environment store. `CHECKIN_ATTENDANCE_MODE=fixed` is the default fixed-5 mode; set it to `random` to select NodeSeek's “try luck” mode. For multiple accounts, use one `CHECKIN_ACCOUNTS` JSON value and omit the single-account cookie.

`CHECKIN_STATUS_PATH` is the verified board endpoint. `CHECKIN_ACTION_PATH` is deliberately not configurable: the application derives the verified attendance action path from `CHECKIN_ATTENDANCE_MODE`, preventing accidental use of an unreviewed endpoint.

Create one serial task, adjusting the directory to your installation:

```text
cd /ql/data/scripts/nodeseek-attendance && python3 run.py
```

Cron expression: 23 8 * * *

Set the QingLong container scheduler plus `CHECKIN_TIMEZONE` to `Asia/Shanghai`. Run the command manually once before enabling the schedule. Disable the task before changing authentication or investigating a site change.

## Troubleshoot

| State | Action |
| --- | --- |
| `SUCCESS` / `ALREADY_DONE` | No action needed. |
| `CONFIG_ERROR` | Check environment names, endpoint values, JSON, and timezone. |
| `AUTH_EXPIRED` | Log in normally and replace the protected cookie. |
| `ACCESS_DENIED` | Disable the task and verify account permission or site policy; do not retry or bypass it. |
| `TEMPORARY_ERROR` | Wait for the next schedule; do not repeatedly trigger the task. |
| `SITE_CHANGED` | Disable the task and collect a new sanitized network capture before updating code. |
| `UNSUPPORTED_SECURITY_CHALLENGE` | Disable automation and complete the site's intended manual flow; do not bypass it. |
| `INTERNAL_ERROR` | Inspect only redacted logs and reproduce with offline tests. |
