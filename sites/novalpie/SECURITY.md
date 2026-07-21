# Security policy

Never commit or share NovalPie tokens, authorization headers, passwords, emails, user IDs, browser profiles, personal response data, or populated environment files. Secrets belong only in QingLong's protected environment-variable store or the current process environment.

If a token appears in chat, logs, screenshots, files, artifacts, or Git history, stop using it, complete NovalPie's normal login flow to replace or revoke it, update the protected variable, inspect account activity, and clean affected artifacts. Deleting only the latest file does not remove a secret from Git history.

Sanitized reports may include HTTP status, field names, value types, the redacted request sequence, and mock fixtures. Do not post raw headers, response bodies, HAR files, `.env` files, or reusable token fragments in public issues. If no private security channel is available, do not disclose credentials in an issue.

This project will not automate login, extract another person's session, bypass CAPTCHA/WAF/Turnstile/WebAuthn/device or SMS verification, evade permissions or rate limits, mass-register accounts, or abuse rewards. A security challenge stops the flow as `UNSUPPORTED_SECURITY_CHALLENGE`.
