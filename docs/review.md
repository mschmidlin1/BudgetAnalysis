# Code Review: Uncommitted Plaid / Bank Connection Changes

**Branch:** `robinhood`  
**Scope:** Uncommitted working-tree changes (modified + untracked)  
**Date:** 2026-07-25  
**Focus:** Security (priority), then maintainability

## Summary

This change set adds Plaid Link bank connection to Budget Analysis: encrypted access-token storage, transaction sync → analysis CSV, Streamlit UI, custom Link component, docs, and unit tests.

**Verdict:** Solid baseline (encryption, per-user isolation, disconnect cleanup). One **medium** security gap should be fixed before relying on this in a multi-user deployment: bind `public_token` exchange to the server-issued Link session. Remaining items are reliability and cleanup.

---

## Files in scope

### Modified
- `.streamlit/secrets.toml.example`
- `Dockerfile`
- `README.md`
- `analysis_utils.py`
- `data_import_tab.py`
- `docs/deployment.md`
- `info_tab.py`
- `requirements.txt`
- `tests/test_storage_utils.py`

### Untracked (new)
- `docs/robinhood_plan.md`
- `plaid_link_component.py`
- `plaid_link_frontend/index.html`
- `plaid_service.py`
- `plaid_ui.py`
- `tests/test_analysis_utils.py`
- `tests/test_plaid_service.py`

---

## Security findings

| Severity | Location | Finding |
|----------|----------|---------|
| Medium | `plaid_ui.py` (~242–258), `plaid_service.py` (~258–265) | Unbound `public_token` exchange: a stolen token can be attached under an attacker’s username |

### Medium — Unbound `public_token` exchange (cross-user Item hijack)

**Impact:** An authenticated attacker who obtains another user’s Plaid `public_token` can exchange it and persist the resulting access token under the attacker’s username, then sync that victim’s transactions into the attacker’s storage (`{attacker}/uploads/*_plaid.csv`, `{attacker}/configs/*_plaid_transactions.json`).

**Attack path:**
1. Victim completes Plaid Link (phishing clone, MITM, or social engineering); attacker captures the short-lived `public_token`.
2. Attacker logs into Budget Analysis as themselves and opens **Data Import → Connect account**.
3. Instead of finishing Link in the iframe, the attacker forges a Streamlit component value (e.g. browser tooling / `postMessage` with `streamlit:setComponentValue`) containing the stolen `public_token`.
4. Server accepts any component-supplied token and exchanges it with no further checks.

**Why this is exploitable:**
- `link_token` is stored in session (`plaid_link_token_{username}`) but never validated against the returned payload (`link_session_id` is serialized in the frontend but ignored server-side).
- `exchange_public_token` has no binding to `client_user_id` or the issued link token; Plaid’s exchange API only needs the `public_token`.
- Component return values are client-origin data in Streamlit’s model; a user can inject them in their own session without breaking server-side auth.
- Multi-user deployment (Google Sheets auth + per-user NFS paths) makes cross-user financial data exposure meaningful.

**Remediation:**
- Treat `public_token` as untrusted input; bind exchange to the server-initiated Link session, e.g.:
  - Require a pending link attempt in session (server-generated `link_token` / nonce) before exchange; reject if missing or already consumed.
  - Persist and verify `metadata.link_session_id` from the component against the expected session for that link flow (or use Plaid’s recommended server-side session pattern).
  - Single-use: clear pending state immediately after successful exchange; reject duplicate exchanges.
- Optionally, after exchange, verify Item identity matches the logged-in app user before `save_connection`.
- Document that users must only complete Link on the legitimate app origin (helps phishing, does not replace server binding).

### Areas reviewed — no medium+ issues found

| Area | Assessment |
|------|------------|
| Auth gating | `login.py` stops UI before tabs; `render_plaid_import()` requires `get_username()`. Plaid secret and encryption key stay server-side in `st.secrets`. |
| Token storage | Access tokens encrypted with Fernet at `{username}/secrets/plaid_access_token.enc`; decrypt errors avoid leaking secrets (`PlaidTokenError`). |
| Logging / errors | No token logging in Plaid modules; `_safe_error_message()` parses Plaid API JSON, not raw credentials. |
| Path traversal | Storage keys go through `_resolve_path()` (`..` rejected, root containment). Plaid CSV names are slugged (`institution_csv_filename`). |
| Per-user isolation | All Plaid paths keyed off session `username`; link token session keys include username. |
| Disconnect / consent | `disconnect()` deletes local token, metadata, full transaction JSON, and CSV even if Plaid `item_remove` fails. |
| XSS | No `unsafe_allow_html`; institution names flow through Streamlit widgets; CSV filenames are slug-restricted. |
| SSRF / injection | Plaid SDK uses fixed environment hosts; no user-controlled URLs. |
| Secrets in repo | `.streamlit/secrets.toml.example` uses placeholders only; docs warn not to commit real values. |

### Lower-priority security notes

1. **Plaintext full transaction cache** — `{username}_plaid_transactions.json` is unencrypted on NFS (same trust model as uploaded CSVs). Be aware of NFS ACL / backup exposure.
2. **App-wide Fernet key** — one `token_encryption_key` decrypts every user’s token. Compromise of app secrets + storage exposes all Items.
3. **Plaid CDN without SRI** — standard for Link; rare supply-chain risk if the CDN is compromised.
4. **`postMessage(..., "*")`** — matches typical Streamlit custom components; parent is the Streamlit app in normal deployment.
5. **Date-filter session keys not namespaced by user** (`plaid_filter_start_date` / `plaid_filter_end_date`) and not cleared on logout — low privacy/UX bleed if two users share a browser session; not a bank-token issue.
6. **TODO: `ITEM_LOGIN_REQUIRED` re-Link** — UX/resilience gap, not an open auth bypass on the connect path.

---

## Maintainability / code quality

Overall structure is good: `plaid_service` (logic), `plaid_ui` (Streamlit), thin component wrapper. Unit tests for crypto, sync, disconnect, and date filter are solid.

### Reliability

1. **Partial connect on sync failure** — `save_connection` runs before `sync_transactions` in the same `try`. If sync fails, the user can be left “connected” with little/no CSV. Prefer clear rollback or an explicit “connected but sync failed; click Sync” state.
2. **Bare `except Exception`** on `transactions_refresh` and `item_remove` — hides unexpected bugs. Prefer catching Plaid/API errors (and logging exception type server-side without secrets).
3. **`ITEM_LOGIN_REQUIRED` / update mode** — `create_link_token(..., access_token=...)` exists but UI never uses it. Reconnect UX will break when the bank needs re-auth.

### Design / cleanup

4. **Legacy Robinhood hardcoding** — fallbacks and cleanup still special-case `robinhood_plaid.csv` while the rest of the code is institution-agnostic. Collapse once migration is done.
5. **Date-filter widgets not per-user** — keys should include `username` (and clear on logout) so shared browsers don’t reuse another user’s filter.
6. **Default calendar filter end = Jan 1 next year** — works with inclusive end-of-day math, but awkward UX; Dec 31 (or exclusive end) would be clearer.
7. **`filter_transactions_by_date` end bound** — `+ 1 day - 1 microsecond` is brittle; `Date < end + 1 day` is simpler and timezone-safer.
8. **Amount sign still unverified** — plan TODO. Plaid positives = purchases, which usually matches `combine_transaction_files`’ majority-sign heuristic, but payments/refunds can skew charts; verify with Sandbox/real data.
9. **`docs/robinhood_plan.md` is stale** — still describes constant `Source=Robinhood` / fixed CSV name; code already generalized. Update or don’t ship the plan as product docs.
10. **Missing newline at EOF** in `analysis_utils.py` — tiny nit.

### Smaller polish

- `_safe_error_message` is a good pattern; reuse it anywhere Plaid errors surface.
- `SyncResult` / settings dataclasses are clear; consider a small `PlaidConnection` facade if `plaid_service` keeps growing.
- Add a UI/unit test for “pending link required before exchange” once session binding is implemented.

---

## What’s done well

- Clear module boundaries for a Streamlit app of this size
- Fernet-at-rest for access tokens; secrets not logged
- Path containment and slug-restricted generated filenames
- Disconnect removes retained local Plaid data even when Plaid is unreachable
- Meaningful unit coverage without live Plaid calls
- Docs/example secrets avoid committing real credentials

---

## Recommended follow-ups (priority order)

1. **(Security)** Bind `public_token` exchange to a single-use server-side pending Link session.
2. **(Reliability)** Handle connect + sync failure without leaving a half-connected state.
3. **(UX/security hygiene)** Namespace/clear Plaid date-filter session keys per user / on logout.
4. **(UX)** Wire update-mode Link for `ITEM_LOGIN_REQUIRED`.
5. **(Cleanup)** Remove legacy `robinhood_plaid.csv` special cases; refresh or archive `docs/robinhood_plan.md`.
6. **(Data quality)** Verify Amount sign behavior against real/Sandbox data.
