"""Streamlit UI for connecting and syncing a bank account through Plaid."""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from typing import Any, MutableMapping, Optional

import streamlit as st

from plaid_integration.plaid_link_component import plaid_link
from plaid_integration.plaid_service import (
    MAX_TRANSACTION_HISTORY_DAYS,
    PlaidConfigurationError,
    PlaidSettings,
    calendar_year_date_range,
    create_client,
    create_link_token,
    disconnect,
    exchange_public_token,
    is_connected,
    load_access_token,
    load_metadata,
    save_connection,
    set_date_filter,
    sync_transactions,
)
from storage.user_tools import get_username


class PendingLinkError(ValueError):
    """Raised when public_token exchange is not bound to a pending Link session."""


def pending_link_session_key(username: str) -> str:
    return f"plaid_pending_link_{username}"


def update_link_session_key(username: str) -> str:
    return f"plaid_update_pending_{username}"


def needs_reauth_session_key(username: str) -> str:
    return f"plaid_needs_reauth_{username}"


def store_pending_link(
    session: MutableMapping[str, Any],
    username: str,
    link_token: str,
) -> None:
    """Record a server-issued Link token that must be consumed for exchange."""
    session[pending_link_session_key(username)] = {
        "link_token": link_token,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }


def clear_pending_link(session: MutableMapping[str, Any], username: str) -> None:
    session.pop(pending_link_session_key(username), None)
    # Legacy key from earlier iterations.
    session.pop(f"plaid_link_token_{username}", None)


def get_pending_link_token(
    session: MutableMapping[str, Any], username: str
) -> Optional[str]:
    pending = session.get(pending_link_session_key(username))
    if isinstance(pending, dict):
        token = pending.get("link_token")
        return str(token) if token else None
    return None


def consume_pending_link_for_exchange(
    session: MutableMapping[str, Any],
    username: str,
    *,
    public_token: Optional[str],
    link_session_id: Optional[str],
) -> str:
    """Validate Link result against a single-use pending session, then consume it.

    Returns the consumed link_token. Raises PendingLinkError when exchange must
    be rejected (missing pending session, missing public_token, or missing
    link_session_id). Pending state is popped before return so retries fail closed.
    """
    if not public_token:
        raise PendingLinkError("Missing public token from Plaid Link.")
    if not link_session_id:
        raise PendingLinkError(
            "Missing link session id from Plaid Link. Complete Connect only on "
            "this app."
        )

    key = pending_link_session_key(username)
    pending = session.pop(key, None)
    # Also drop any legacy key so a retry cannot reuse a stale token string.
    session.pop(f"plaid_link_token_{username}", None)

    if not isinstance(pending, dict) or not pending.get("link_token"):
        raise PendingLinkError(
            "No pending Plaid Link session. Start Connect again from this app."
        )
    return str(pending["link_token"])


def clear_plaid_session_keys(session: MutableMapping[str, Any]) -> None:
    """Remove Plaid UI session keys (link pending, filters, re-auth)."""
    prefixes = (
        "plaid_pending_link_",
        "plaid_link_token_",
        "plaid_update_pending_",
        "plaid_needs_reauth_",
        "plaid_filter_start_date_",
        "plaid_filter_end_date_",
        "plaid_apply_filter_",
    )
    for key in list(session.keys()):
        if isinstance(key, str) and key.startswith(prefixes):
            session.pop(key, None)


def _plaid_error_code(error: Exception) -> Optional[str]:
    body = getattr(error, "body", None)
    if not body:
        return None
    try:
        payload = json.loads(body)
    except (TypeError, ValueError):
        return None
    code = payload.get("error_code")
    return str(code) if code else None


def _safe_error_message(error: Exception) -> str:
    """Return useful Plaid error details without exposing request credentials."""
    body = getattr(error, "body", None)
    if body:
        try:
            payload = json.loads(body)
            code = payload.get("error_code")
            message = payload.get("display_message") or payload.get("error_message")
            if code and message:
                return f"{code}: {message}"
            if code:
                return str(code)
        except (TypeError, ValueError):
            pass
    return error.__class__.__name__


def _clear_link_token(username: str) -> None:
    clear_pending_link(st.session_state, username)
    st.session_state.pop(update_link_session_key(username), None)
    st.session_state.pop(needs_reauth_session_key(username), None)


def _parse_metadata_date(value) -> Optional[date]:
    if not value:
        return None
    return date.fromisoformat(str(value)[:10])


def _render_date_filter(username: str, metadata: dict) -> None:
    st.markdown("**Date filter (Plaid import only)**")
    default_start, default_end = calendar_year_date_range()
    saved_start = _parse_metadata_date(metadata.get("filter_start_date"))
    saved_end = _parse_metadata_date(metadata.get("filter_end_date"))
    desired_start = saved_start or default_start
    desired_end = saved_end or default_end

    start_key = f"plaid_filter_start_date_{username}"
    end_key = f"plaid_filter_end_date_{username}"
    apply_key = f"plaid_apply_filter_{username}"

    # Initialize once from saved/default values. Using both value= and key=
    # lets Streamlit keep a stale session value across reruns.
    if start_key not in st.session_state:
        st.session_state[start_key] = desired_start
    if end_key not in st.session_state:
        st.session_state[end_key] = desired_end

    date_col1, date_col2 = st.columns(2)
    with date_col1:
        start_date = st.date_input(
            "Start date",
            key=start_key,
        )
    with date_col2:
        end_date = st.date_input(
            "End date",
            key=end_key,
        )

    if st.button("Apply date filter", use_container_width=True, key=apply_key):
        try:
            if start_date > end_date:
                st.error("Start date must be on or before end date.")
                return
            count = set_date_filter(
                username,
                start_date=start_date,
                end_date=end_date,
            )
            st.success(
                f"Applied date filter ({start_date} → {end_date}). "
                f"Analysis CSV now has {count} transactions."
            )
            st.rerun()
        except Exception as exc:
            st.error(f"Could not apply date filter: {exc}")

    st.caption(f"Active Plaid filter: {desired_start} → {desired_end}.")
    earliest = metadata.get("earliest_transaction_date")
    if earliest and desired_start < _parse_metadata_date(earliest):
        st.caption(
            f"Note: Plaid has no posted transactions before {earliest}, so a "
            "wider start date will not add earlier rows."
        )


def _render_update_mode(
    client,
    settings: PlaidSettings,
    username: str,
) -> None:
    """Re-authenticate an existing Item when the bank requires login again."""
    st.warning(
        "Your bank requires re-authentication before transactions can sync. "
        "Complete Link below — credentials stay with Plaid."
    )
    update_key = update_link_session_key(username)
    if update_key not in st.session_state:
        try:
            access_token = load_access_token(
                username, settings.token_encryption_key
            )
            st.session_state[update_key] = {
                "link_token": create_link_token(
                    client,
                    username,
                    settings.redirect_uri,
                    access_token=access_token,
                ),
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            st.error(f"Plaid re-authentication could not start: {_safe_error_message(exc)}")
            return

    pending = st.session_state.get(update_key) or {}
    link_token = pending.get("link_token") if isinstance(pending, dict) else None
    if not link_token:
        st.session_state.pop(update_key, None)
        return

    result = plaid_link(
        link_token,
        button_text="Re-authenticate account",
        key=f"plaid_update_link_{username}",
    )
    if not result:
        return

    if result.get("error"):
        error = result["error"]
        message = error.get("display_message") or "Plaid Link did not complete."
        st.warning(message)
        return

    # Update mode keeps the existing access_token; do not exchange public_token.
    st.session_state.pop(update_key, None)
    st.session_state.pop(needs_reauth_session_key(username), None)
    try:
        with st.spinner("Re-authenticated. Synchronizing transactions…"):
            sync_result = sync_transactions(
                client,
                username,
                settings.token_encryption_key,
            )
        range_text = ""
        if sync_result.earliest_date and sync_result.latest_date:
            range_text = (
                f" Synced range: {sync_result.earliest_date} to "
                f"{sync_result.latest_date}."
            )
        st.success(
            f"Re-authentication succeeded. Analysis CSV has "
            f"{sync_result.count} posted transactions.{range_text}"
        )
        st.rerun()
    except Exception as exc:
        if _plaid_error_code(exc) == "ITEM_LOGIN_REQUIRED":
            st.session_state[needs_reauth_session_key(username)] = True
        st.error(f"Plaid sync failed after re-authentication: {_safe_error_message(exc)}")


def _render_connected(
    client,
    settings: PlaidSettings,
    username: str,
) -> None:
    metadata = load_metadata(username)
    institution = metadata.get("institution_name", "Connected institution")
    csv_filename = metadata.get("csv_filename")
    st.success(f"Connected to {institution}")
    st.caption("Only one financial institution can be connected at a time.")

    last_sync = metadata.get("last_sync_at")
    earliest = metadata.get("earliest_transaction_date")
    latest = metadata.get("latest_transaction_date")
    if last_sync:
        st.caption(f"Last synchronized: {last_sync}")
    else:
        st.caption("Connected, but transactions have not been synchronized yet.")
    if earliest and latest:
        st.caption(f"Imported posted transactions from {earliest} to {latest}.")
    if csv_filename:
        st.caption(f"Analysis file: `{csv_filename}`")

    days_requested = metadata.get("days_requested")
    if days_requested != MAX_TRANSACTION_HISTORY_DAYS:
        st.warning(
            "This connection was created with Plaid's default history window "
            "(about 90 days). Plaid can provide up to "
            f"{MAX_TRANSACTION_HISTORY_DAYS} days (~2 years), not all-time. "
            "Click Sync again first — older txs often arrive a few minutes after "
            "linking. To request the full 2-year window, Disconnect once and "
            "Connect again (uses one Trial Item)."
        )
    else:
        st.caption(
            f"Plaid history window for this connection: up to "
            f"{MAX_TRANSACTION_HISTORY_DAYS} days (~2 years). Older history "
            "can keep arriving for a few minutes after linking — use Sync again."
        )

    if st.session_state.get(needs_reauth_session_key(username)):
        _render_update_mode(client, settings, username)
        st.divider()
        _render_date_filter(username, metadata)
        return

    sync_column, disconnect_column = st.columns(2)
    with sync_column:
        if st.button(
            "Sync transactions",
            type="primary",
            use_container_width=True,
            key="plaid_sync",
        ):
            try:
                with st.spinner("Synchronizing transactions…"):
                    result = sync_transactions(
                        client,
                        username,
                        settings.token_encryption_key,
                    )
                range_text = ""
                if result.earliest_date and result.latest_date:
                    range_text = (
                        f" Synced range: {result.earliest_date} to "
                        f"{result.latest_date}."
                    )
                st.success(
                    f"Synchronized. Analysis CSV has {result.count} posted "
                    f"transactions.{range_text}"
                )
                st.rerun()
            except Exception as exc:
                if _plaid_error_code(exc) == "ITEM_LOGIN_REQUIRED":
                    st.session_state[needs_reauth_session_key(username)] = True
                    st.warning(
                        "Your bank requires re-authentication. Use the button "
                        "below after the page refreshes."
                    )
                    st.rerun()
                st.error(f"Plaid sync failed: {_safe_error_message(exc)}")

    with disconnect_column:
        if st.button(
            "Disconnect account",
            use_container_width=True,
            key="plaid_disconnect",
        ):
            try:
                with st.spinner("Disconnecting account…"):
                    removed_from_plaid = disconnect(
                        client,
                        username,
                        settings.token_encryption_key,
                    )
                _clear_link_token(username)
                if not removed_from_plaid:
                    st.warning(
                        "Local Plaid data was removed, but Plaid could not be "
                        "reached. Remove the Item in the Plaid Dashboard if it remains."
                    )
                else:
                    st.success(
                        "Account was disconnected and imported Plaid data was removed."
                    )
                st.rerun()
            except Exception as exc:
                st.error(f"Plaid disconnect failed: {_safe_error_message(exc)}")

    st.divider()
    _render_date_filter(username, metadata)


def _render_disconnected(
    client,
    settings: PlaidSettings,
    username: str,
) -> None:
    st.caption(
        "Complete Connect only in this app (same browser origin). Do not paste "
        "tokens from other sites."
    )
    if get_pending_link_token(st.session_state, username) is None:
        try:
            link_token = create_link_token(
                client,
                username,
                settings.redirect_uri,
            )
            store_pending_link(st.session_state, username, link_token)
        except Exception as exc:
            st.error(f"Plaid Link could not start: {_safe_error_message(exc)}")
            return

    link_token = get_pending_link_token(st.session_state, username)
    if not link_token:
        return

    result = plaid_link(
        link_token,
        button_text="Connect account",
        key=f"plaid_link_{username}",
    )
    if not result:
        return

    if result.get("error"):
        error = result["error"]
        message = error.get("display_message") or "Plaid Link did not complete."
        st.warning(message)
        return

    public_token = result.get("public_token")
    metadata = result.get("metadata") or {}
    link_session_id = metadata.get("link_session_id")
    institution = (metadata.get("institution") or {}).get(
        "name", "Connected institution"
    )

    try:
        consume_pending_link_for_exchange(
            st.session_state,
            username,
            public_token=public_token,
            link_session_id=link_session_id,
        )
    except PendingLinkError as exc:
        # Validation failures before consume leave pending intact for retry;
        # a consumed/missing session is already empty.
        st.error(str(exc))
        return

    try:
        with st.spinner("Securing your connection…"):
            access_token, item_id = exchange_public_token(client, public_token)
            save_connection(
                username,
                access_token,
                item_id,
                settings.token_encryption_key,
                institution,
            )
    except Exception as exc:
        clear_pending_link(st.session_state, username)
        st.error(f"Plaid connection failed: {_safe_error_message(exc)}")
        return

    try:
        with st.spinner("Importing transactions…"):
            sync_result = sync_transactions(
                client,
                username,
                settings.token_encryption_key,
            )
        range_text = ""
        if sync_result.earliest_date and sync_result.latest_date:
            range_text = (
                f" Date range: {sync_result.earliest_date} to "
                f"{sync_result.latest_date}."
            )
        st.success(
            f"Connected to {institution}; analysis CSV has "
            f"{sync_result.count} posted transactions.{range_text}"
        )
        st.rerun()
    except Exception as exc:
        if _plaid_error_code(exc) == "ITEM_LOGIN_REQUIRED":
            st.session_state[needs_reauth_session_key(username)] = True
        st.warning(
            f"Connected to {institution}, but the first sync failed "
            f"({_safe_error_message(exc)}). Click **Sync transactions** to retry."
        )
        st.rerun()


def render_plaid_import() -> None:
    """Render the Plaid bank-connection section for the authenticated user."""
    st.subheader("Bank connection (Plaid)")
    st.write(
        "Connect one financial institution through Plaid to import posted "
        "transactions. Your bank credentials are handled by Plaid and are never "
        "sent to Budget Analysis."
    )

    username = get_username()
    if not username:
        st.info("Log in before connecting a bank account.")
        return

    if "plaid" not in st.secrets:
        st.info("Plaid is not configured for this deployment.")
        return

    try:
        settings = PlaidSettings.from_mapping(st.secrets["plaid"])
        client = create_client(settings)
    except PlaidConfigurationError as exc:
        st.error(str(exc))
        return

    if settings.environment == "sandbox":
        st.info(
            "Sandbox mode uses fake banks only. After clicking Connect, use phone "
            "**415-555-0011**, pick a test bank such as **First Platypus Bank**, "
            "then log in with **user_good** / **pass_good** (MFA code **1234** if "
            "asked)."
        )

    if is_connected(username):
        _render_connected(client, settings, username)
    else:
        _render_disconnected(client, settings, username)
