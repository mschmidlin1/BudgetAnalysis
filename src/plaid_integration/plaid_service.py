"""Plaid backend, encrypted token storage, and transaction synchronization."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import io
import logging
import re
from typing import Any, Mapping, Optional

from cryptography.fernet import Fernet, InvalidToken
import pandas as pd
import plaid
from plaid.api import plaid_api
from plaid.exceptions import ApiException
from plaid.model.country_code import CountryCode
from plaid.model.item_public_token_exchange_request import (
    ItemPublicTokenExchangeRequest,
)
from plaid.model.item_remove_request import ItemRemoveRequest
from plaid.model.link_token_create_request import LinkTokenCreateRequest
from plaid.model.link_token_create_request_user import LinkTokenCreateRequestUser
from plaid.model.link_token_transactions import LinkTokenTransactions
from plaid.model.products import Products
from plaid.model.transactions_refresh_request import TransactionsRefreshRequest
from plaid.model.transactions_sync_request import TransactionsSyncRequest

logger = logging.getLogger(__name__)

from analysis.analysis_utils import filter_transactions_by_date
from storage.storage_utils import (
    delete,
    exists,
    get_path_for_config,
    get_path_for_upload,
    load_json,
    read_bytes,
    save_json,
    write_bytes,
    write_text,
)


PLAID_COLUMNS = [
    "Date",
    "Amount",
    "Description",
    "Source",
    "Transaction ID",
]
PLAID_MAPPING = ["Date", "Amount", "Description"]
# Plaid's maximum supported Transactions history window.
MAX_TRANSACTION_HISTORY_DAYS = 730
SUPPORTED_ENVIRONMENTS = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


@dataclass(frozen=True)
class SyncResult:
    count: int
    earliest_date: Optional[str] = None
    latest_date: Optional[str] = None
    refreshed: bool = False
    csv_filename: Optional[str] = None


class PlaidConfigurationError(ValueError):
    """Raised when required Plaid settings are missing or invalid."""


class PlaidTokenError(ValueError):
    """Raised when an encrypted access token cannot be decrypted."""


@dataclass(frozen=True)
class PlaidSettings:
    client_id: str
    secret: str
    environment: str
    token_encryption_key: str
    redirect_uri: Optional[str] = None

    @classmethod
    def from_mapping(cls, values: Mapping[str, Any]) -> "PlaidSettings":
        required = ("client_id", "secret", "token_encryption_key")
        missing = [name for name in required if not str(values.get(name, "")).strip()]
        if missing:
            raise PlaidConfigurationError(
                f"Missing Plaid setting(s): {', '.join(missing)}"
            )

        environment = str(values.get("env", "sandbox")).strip().lower()
        if environment not in SUPPORTED_ENVIRONMENTS:
            raise PlaidConfigurationError(
                "Plaid env must be sandbox or production"
            )

        redirect_uri = str(values.get("redirect_uri", "")).strip() or None
        return cls(
            client_id=str(values["client_id"]).strip(),
            secret=str(values["secret"]).strip(),
            environment=environment,
            token_encryption_key=str(values["token_encryption_key"]).strip(),
            redirect_uri=redirect_uri,
        )


def create_client(settings: PlaidSettings) -> plaid_api.PlaidApi:
    """Create an official Plaid API client for the configured environment."""
    configuration = plaid.Configuration(
        host=SUPPORTED_ENVIRONMENTS[settings.environment],
        api_key={
            "clientId": settings.client_id,
            "secret": settings.secret,
        },
    )
    return plaid_api.PlaidApi(plaid.ApiClient(configuration))


def institution_csv_filename(institution_name: str) -> str:
    """Build `{institution}_plaid.csv` from an institution display name."""
    slug = re.sub(r"[^a-z0-9]+", "_", (institution_name or "").lower()).strip("_")
    if not slug:
        slug = "institution"
    return f"{slug}_plaid.csv"


def calendar_year_date_range(today: Optional[date] = None) -> tuple[date, date]:
    """Return Jan 1 through Dec 31 of the current calendar year (inclusive)."""
    current = today or date.today()
    return date(current.year, 1, 1), date(current.year, 12, 31)


def _metadata_path(username: str) -> str:
    return get_path_for_config(username, "plaid")


def _token_path(username: str) -> str:
    return f"{username}/secrets/plaid_access_token.enc"


def _full_transactions_path(username: str) -> str:
    return f"{username}/configs/{username}_plaid_transactions.json"


def _upload_config_path(username: str) -> str:
    return get_path_for_config(username, "upload_config")


def encrypt_access_token(access_token: str, encryption_key: str) -> bytes:
    """Encrypt an access token using a Fernet key."""
    try:
        return Fernet(encryption_key.encode("utf-8")).encrypt(
            access_token.encode("utf-8")
        )
    except (TypeError, ValueError) as exc:
        raise PlaidConfigurationError("Invalid Plaid token_encryption_key") from exc


def decrypt_access_token(ciphertext: bytes, encryption_key: str) -> str:
    """Decrypt an access token; expose no secret values in errors."""
    try:
        return (
            Fernet(encryption_key.encode("utf-8"))
            .decrypt(ciphertext)
            .decode("utf-8")
        )
    except (InvalidToken, TypeError, ValueError) as exc:
        raise PlaidTokenError(
            "The stored Plaid token could not be decrypted with the configured key"
        ) from exc


def is_connected(username: str) -> bool:
    """Return whether both Plaid metadata and encrypted token exist."""
    return exists(_metadata_path(username)) and exists(_token_path(username))


def load_metadata(username: str) -> dict[str, Any]:
    """Load non-secret Plaid connection metadata."""
    return load_json(_metadata_path(username)) or {}


def load_access_token(username: str, encryption_key: str) -> str:
    """Load and decrypt a user's Plaid access token."""
    ciphertext = read_bytes(_token_path(username))
    if ciphertext is None:
        raise PlaidTokenError("No stored Plaid access token was found")
    return decrypt_access_token(ciphertext, encryption_key)


def get_csv_filename(username: str, metadata: Optional[Mapping[str, Any]] = None) -> str:
    """Return the analysis CSV filename for the connected institution."""
    meta = dict(metadata or load_metadata(username))
    if meta.get("csv_filename"):
        return str(meta["csv_filename"])
    return institution_csv_filename(str(meta.get("institution_name") or "institution"))


def save_connection(
    username: str,
    access_token: str,
    item_id: str,
    encryption_key: str,
    institution_name: str = "Connected institution",
) -> None:
    """Persist an encrypted access token and non-secret Item metadata."""
    now = datetime.now(timezone.utc).isoformat()
    name = institution_name or "Connected institution"
    csv_filename = institution_csv_filename(name)
    write_bytes(
        _token_path(username),
        encrypt_access_token(access_token, encryption_key),
    )
    start, end = calendar_year_date_range()
    save_json(
        {
            "item_id": item_id,
            "institution_name": name,
            "csv_filename": csv_filename,
            "linked_at": now,
            "last_sync_at": None,
            "cursor": None,
            "days_requested": MAX_TRANSACTION_HISTORY_DAYS,
            "earliest_transaction_date": None,
            "latest_transaction_date": None,
            "filter_start_date": start.isoformat(),
            "filter_end_date": end.isoformat(),
        },
        _metadata_path(username),
    )


def create_link_token(
    client: plaid_api.PlaidApi,
    username: str,
    redirect_uri: Optional[str] = None,
    access_token: Optional[str] = None,
) -> str:
    """Create a Link token for initial connection or update mode."""
    request = LinkTokenCreateRequest(
        client_name="Budget Analysis",
        language="en",
        country_codes=[CountryCode("US")],
        user=LinkTokenCreateRequestUser(client_user_id=username),
        transactions=LinkTokenTransactions(
            days_requested=MAX_TRANSACTION_HISTORY_DAYS
        ),
    )
    if access_token:
        request.access_token = access_token
    else:
        request.products = [Products("transactions")]
    if redirect_uri:
        request.redirect_uri = redirect_uri
    return client.link_token_create(request).link_token


def exchange_public_token(
    client: plaid_api.PlaidApi, public_token: str
) -> tuple[str, str]:
    """Exchange Link's short-lived public token for Item credentials."""
    response = client.item_public_token_exchange(
        ItemPublicTokenExchangeRequest(public_token=public_token)
    )
    return response.access_token, response.item_id


def _value(obj: Any, name: str, default: Any = None) -> Any:
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _normalize_transaction(
    transaction: Any,
    institution_name: str,
) -> Optional[dict[str, Any]]:
    """Convert a Plaid transaction to the generated CSV schema."""
    if bool(_value(transaction, "pending", False)):
        return None

    transaction_id = str(_value(transaction, "transaction_id", "")).strip()
    if not transaction_id:
        return None

    date_value = _value(transaction, "date")
    merchant_name = _value(transaction, "merchant_name")
    description = merchant_name or _value(transaction, "name") or "Unknown"
    return {
        "Date": date_value.isoformat()
        if hasattr(date_value, "isoformat")
        else str(date_value),
        # Plaid uses positive amounts for card purchases and negative for payments.
        "Amount": float(_value(transaction, "amount", 0)),
        "Description": str(description),
        "Source": institution_name,
        "Transaction ID": transaction_id,
    }


def _load_full_transactions(username: str) -> dict[str, dict[str, Any]]:
    stored = load_json(_full_transactions_path(username))
    if stored and isinstance(stored.get("transactions"), dict):
        return {
            str(key): value
            for key, value in stored["transactions"].items()
            if isinstance(value, dict)
        }

    # Legacy fallback: older installs only had the analysis CSV.
    metadata = load_metadata(username)
    csv_name = get_csv_filename(username, metadata)
    csv_bytes = read_bytes(get_path_for_upload(username, csv_name))
    if not csv_bytes:
        return {}
    dataframe = pd.read_csv(io.BytesIO(csv_bytes), dtype={"Transaction ID": str})
    if "Transaction ID" not in dataframe.columns:
        return {}
    return {
        str(row["Transaction ID"]): row.to_dict()
        for _, row in dataframe.iterrows()
        if pd.notna(row["Transaction ID"])
    }


def _save_full_transactions(
    username: str, transactions: Mapping[str, Mapping[str, Any]]
) -> None:
    save_json(
        {"transactions": dict(transactions)},
        _full_transactions_path(username),
    )


def _parse_optional_date(value: Any) -> Optional[date]:
    if value is None or value == "":
        return None
    return pd.Timestamp(value).date()


def _effective_date_filter(
    metadata: Mapping[str, Any],
) -> tuple[date, date]:
    """Return the active filter, defaulting to the current calendar year."""
    start = _parse_optional_date(metadata.get("filter_start_date"))
    end = _parse_optional_date(metadata.get("filter_end_date"))
    default_start, default_end = calendar_year_date_range()
    return start or default_start, end or default_end


def _save_analysis_csv(
    username: str,
    transactions: Mapping[str, Mapping[str, Any]],
    metadata: Mapping[str, Any],
) -> int:
    """Write the filtered analysis CSV and register its column mapping."""
    csv_filename = get_csv_filename(username, metadata)
    institution_name = str(metadata.get("institution_name") or "Connected institution")
    start_date, end_date = _effective_date_filter(metadata)
    dataframe = pd.DataFrame(list(transactions.values()), columns=PLAID_COLUMNS)
    if not dataframe.empty:
        if "Source" not in dataframe.columns:
            dataframe["Source"] = institution_name
        else:
            dataframe["Source"] = dataframe["Source"].fillna(institution_name)
        dataframe = filter_transactions_by_date(
            dataframe,
            start_date=start_date,
            end_date=end_date,
        )
        if not dataframe.empty:
            dataframe = dataframe.sort_values(
                ["Date", "Transaction ID"], ascending=[False, True]
            )

    write_text(
        get_path_for_upload(username, csv_filename),
        dataframe.to_csv(index=False),
    )

    upload_config = load_json(_upload_config_path(username)) or {}
    mappings = upload_config.get("file_mappings", {})
    # Drop any previous Plaid CSV mapping for this user.
    for existing_name in list(mappings.keys()):
        if str(existing_name).endswith("_plaid.csv"):
            mappings.pop(existing_name, None)
    mappings[csv_filename] = PLAID_MAPPING
    save_json({"file_mappings": mappings}, _upload_config_path(username))
    return len(dataframe)


def _transaction_date_bounds(
    transactions: Mapping[str, Mapping[str, Any]],
) -> tuple[Optional[str], Optional[str]]:
    dates = [str(row.get("Date")) for row in transactions.values() if row.get("Date")]
    if not dates:
        return None, None
    return min(dates), max(dates)


def set_date_filter(
    username: str,
    start_date: date,
    end_date: date,
) -> int:
    """Persist a Plaid-only date filter and rewrite the analysis CSV."""
    metadata = load_metadata(username)
    if not metadata:
        raise PlaidConfigurationError("No Plaid connection metadata was found")
    if start_date > end_date:
        raise ValueError("Start date must be on or before end date")

    metadata["filter_start_date"] = start_date.isoformat()
    metadata["filter_end_date"] = end_date.isoformat()
    save_json(metadata, _metadata_path(username))

    transactions = _load_full_transactions(username)
    return _save_analysis_csv(username, transactions, metadata)


def sync_transactions(
    client: plaid_api.PlaidApi,
    username: str,
    encryption_key: str,
) -> SyncResult:
    """Incrementally sync Plaid transactions and update the generated CSV."""
    metadata = load_metadata(username)
    institution_name = str(metadata.get("institution_name") or "Connected institution")
    if not metadata.get("csv_filename"):
        metadata["csv_filename"] = institution_csv_filename(institution_name)
    access_token = load_access_token(username, encryption_key)
    cursor = metadata.get("cursor")
    transactions = _load_full_transactions(username)

    refreshed = False
    try:
        # Ask Plaid to pull any newly available history from the institution
        # before reading the sync cursor (historical updates can arrive late).
        client.transactions_refresh(TransactionsRefreshRequest(access_token=access_token))
        refreshed = True
    except ApiException as exc:
        # Refresh can be unavailable or still warming up; sync what we have.
        logger.warning(
            "Plaid transactions_refresh failed: %s", type(exc).__name__
        )
        refreshed = False

    while True:
        request = TransactionsSyncRequest(access_token=access_token)
        if cursor:
            request.cursor = cursor
        response = client.transactions_sync(request)

        for transaction in response.added:
            normalized = _normalize_transaction(transaction, institution_name)
            if normalized:
                transactions[normalized["Transaction ID"]] = normalized
        for transaction in response.modified:
            transaction_id = str(_value(transaction, "transaction_id", ""))
            normalized = _normalize_transaction(transaction, institution_name)
            if normalized:
                transactions[transaction_id] = normalized
            else:
                transactions.pop(transaction_id, None)
        for removed in response.removed:
            transactions.pop(str(_value(removed, "transaction_id", "")), None)

        cursor = response.next_cursor
        if not response.has_more:
            break

    _save_full_transactions(username, transactions)
    count = _save_analysis_csv(username, transactions, metadata)
    earliest_date, latest_date = _transaction_date_bounds(transactions)
    metadata["cursor"] = cursor
    metadata["last_sync_at"] = datetime.now(timezone.utc).isoformat()
    metadata["earliest_transaction_date"] = earliest_date
    metadata["latest_transaction_date"] = latest_date
    metadata["days_requested"] = metadata.get(
        "days_requested", MAX_TRANSACTION_HISTORY_DAYS
    )
    save_json(metadata, _metadata_path(username))
    return SyncResult(
        count=count,
        earliest_date=earliest_date,
        latest_date=latest_date,
        refreshed=refreshed,
        csv_filename=get_csv_filename(username, metadata),
    )


def disconnect(
    client: plaid_api.PlaidApi,
    username: str,
    encryption_key: str,
) -> bool:
    """Remove the Plaid Item and all locally retained Plaid data."""
    metadata = load_metadata(username)
    csv_filename = get_csv_filename(username, metadata) if metadata else None
    removed_from_plaid = True
    try:
        if exists(_token_path(username)):
            access_token = load_access_token(username, encryption_key)
            client.item_remove(ItemRemoveRequest(access_token=access_token))
    except (ApiException, PlaidTokenError) as exc:
        logger.warning("Plaid item_remove failed: %s", type(exc).__name__)
        removed_from_plaid = False
    finally:
        # Consent revocation must remove retained transaction data even if Plaid
        # cannot be reached. A later Plaid Dashboard cleanup may still be needed.
        delete(_token_path(username))
        delete(_metadata_path(username))
        delete(_full_transactions_path(username))
        if csv_filename:
            delete(get_path_for_upload(username, csv_filename))

        upload_config = load_json(_upload_config_path(username)) or {}
        mappings = upload_config.get("file_mappings", {})
        for existing_name in list(mappings.keys()):
            if str(existing_name).endswith("_plaid.csv"):
                mappings.pop(existing_name, None)
        save_json({"file_mappings": mappings}, _upload_config_path(username))
    return removed_from_plaid
