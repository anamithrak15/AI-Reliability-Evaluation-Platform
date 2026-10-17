# Smoke-test checklist

Run after any deployment. Each item states the expected result; stop and investigate on the first mismatch.

## 1. Platform is up

- [ ] `GET /health` returns `200 {"status":"ok"}`.
- [ ] `GET /ready` returns `200` with `database: ok` and `redis: ok`.
- [ ] The UI loads and shows the **Sign in** form, with no console errors.
- [ ] Response headers include `Content-Security-Policy`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.

## 2. Accounts

- [ ] Create an account at `#/register` (10+ character password). You land on **Datasets** and see `support-ticket-classification`.
- [ ] Sign out, then sign in again with the same credentials.
- [ ] A wrong password shows "Incorrect email or password", the same text for an unknown email.
- [ ] Opening `#/runs` while signed out shows the sign-in form, not data.
- [ ] A second account sees **none** of the first account's datasets or runs.
- [ ] A new account shows the "email address is not verified" banner; **Account > Resend verification email** reports success (or `Email is not configured on this server` when no provider is set).
- [ ] With a provider configured, the emailed link marks the account **verified**; a garbage link at `#/verify-email?token=x` shows "invalid or has expired".
- [ ] **Forgot password** gives the same message for a known and an unknown address; the emailed reset link works once, then shows the expired-link error, and the old password stops working.
- [ ] **Account > Change password** rejects a wrong current password, accepts the right one, and keeps this browser signed in.

## 3. Main workflow (fresh account)

- [ ] **Runs**: dataset `support-ticket-classification`, version `v1 (6 cases)`, models `fast-model` and `accurate-model`, **Start run**. Progress reaches 12/12 and the status is `completed`.
- [ ] Click a case: the page shows the prompt, the expected answer and both models' outputs.
- [ ] **Compare**: `accurate-model` has higher quality than `fast-model`; the recommendation is `accurate-model`; cost shows *unavailable* for mock models.
- [ ] Start a second run with only `accurate-model`, then on the first run's compare page set it as the **baseline**: findings appear, with a severity and an explanation.
- [ ] A run with `flaky-model` finishes as `completed with errors`, shows the partial-failure notice, and lists the failed cases with their errors.

## 4. Failure handling

- [ ] Open `#/nope`: "Page not found".
- [ ] Stop the API (or let the free instance sleep): pages show "Cannot reach the API" with **Retry**, and recover when it is back.
- [ ] Try to use a baseline from a different dataset version: a red "dataset content differs" message, nothing saved.

## 5. Abuse controls

- [ ] Six wrong sign-ins for one email in a minute return `429`.
- [ ] A state-changing request without `X-Requested-With: fetch` returns `403 csrf_check_failed`.
- [ ] `curl --ssl-no-revoke -H "X-Forwarded-For: 1.2.3.4" <url>/api/v1/auth/me` (expect `401`): the API log's `client_ip` is **not** `1.2.3.4` (hosted deployments only). Do not use `/health`; it is logged at debug level.

## 6. Hosted demo extras

- [ ] `ENABLE_LIVE_LLM` is `false`; `/api/v1/models` lists only mock models.
- [ ] `SECRET_KEY` is a generated value, `COOKIE_SECURE=true`, and the session cookie shows `Secure; HttpOnly; SameSite=Lax`.
- [ ] After 15 idle minutes the first request is slow but succeeds on retry.
- [ ] Render shows the free database's expiry date; note it somewhere you will see it.
