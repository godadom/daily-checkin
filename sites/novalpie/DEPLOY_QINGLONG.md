# QingLong deployment

Upload or clone this repository, then work from the NovalPie project directory. Confirm Python 3.11 or newer and install the pinned dependency:

```text
cd /ql/data/scripts/checkin/sites/novalpie
python3 --version
python3 -m pip install --disable-pip-version-check -r requirements.txt
python3 tests/run_offline.py
```

The verified base URL and both API paths are built into the code. Do not create `CHECKIN_BASE_URL`, `CHECKIN_STATUS_PATH`, or `CHECKIN_ACTION_PATH`; they are not configuration variables and any inherited values with those names are ignored. For one account, only `CHECKIN_TOKEN` is required; `CHECKIN_ACCOUNT_NAME` is optional. For multiple accounts use one `CHECKIN_ACCOUNTS` JSON value such as `[{"name":"account-a","token":"<REDACTED_TOKEN>"}]` and omit the single-account token. Supply token values without the `Bearer ` prefix. Account aliases must not be phone numbers, emails, or other identifiers.

After a normal browser login, obtain only your own token from an authorized request's Bearer header and place it directly into QingLong. Never put it in the cron command, repository URL, source code, screenshots, or logs. When it expires, log in normally and replace the protected value; no refresh or login endpoint is invented by this project.

Create one serial task:

```text
cd /ql/data/scripts/checkin/sites/novalpie && python3 run.py
```

Recommended five-field cron: `31 8 * * *`. Confirm your QingLong version's cron format and container timezone. The application already defaults to `Asia/Shanghai`; set `CHECKIN_TIMEZONE` only when you need another IANA timezone. The minute avoids the top-of-hour peak. Keep concurrency at one; optional jitter is disabled by default.

Run `python3 tests/run_offline.py` after every update. Before enabling the schedule, manually run `python3 run.py` once with protected variables configured. The built-in notification mode only writes a redacted summary; set `CHECKIN_NOTIFY_MODE=off` to disable it.

## Troubleshooting

| State / exit | Action |
| --- | --- |
| `SUCCESS` / `ALREADY_DONE` / `0` | No action. Browser auto-check-in and this task can coexist because status is queried first. |
| `CONFIG_ERROR` / `2` | Check variable names, JSON, token format, and IANA timezone. |
| `AUTH_EXPIRED` / `3` | Log in normally and replace only the affected protected token. |
| `TEMPORARY_ERROR` / `4` | Check connectivity, rate limits, and service health; wait before rerunning. |
| `SITE_CHANGED` / `5` | Disable the task and collect a newly sanitized response shape before updating code. |
| `UNSUPPORTED_SECURITY_CHALLENGE` / `6` | Disable automation and complete the intended manual flow; do not bypass it. |
| `ACCESS_DENIED` / `7` | Disable the task and verify account permission or site policy; do not retry or bypass it. |
| `INTERNAL_ERROR` / `70` | Inspect only redacted logs and reproduce with offline tests. |

To stop automation, disable the task and its related environment variables. Remove the task before deleting the project directory or protected values.
