#!/usr/bin/env python3
"""
One-off GCS → NFS migration helper.

Reads bucket + service account from Streamlit secrets.toml (leftover [gcs] and
[gcp_service_account] sections). Does not modify the running app.

Examples:
  python scripts/migrate_gcs_to_nfs.py --probe
  python scripts/migrate_gcs_to_nfs.py --dry-run --dest /srv/budget-analysis
  python scripts/migrate_gcs_to_nfs.py --dest /srv/budget-analysis --prefix alice/
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Pure helpers (unit-tested; no network)
# ---------------------------------------------------------------------------


def destination_path(dest_root: Path, blob_name: str) -> Path:
    """Map a GCS object name to a path under dest_root."""
    normalized = blob_name.replace("\\", "/").lstrip("/")
    if not normalized or any(part == ".." for part in Path(normalized).parts):
        raise ValueError(f"Unsafe blob name: {blob_name!r}")
    return dest_root / normalized


def should_skip(dest: Path, skip_existing: bool) -> bool:
    """Return True if an existing dest file should be left alone."""
    return skip_existing and dest.is_file()


def summarize_plan(
    blob_names: Iterable[str],
    dest_root: Path,
    skip_existing: bool,
) -> Tuple[List[str], List[str], List[str]]:
    """
    Classify blobs into copy / skip / invalid lists (by blob name).
    Does not touch the network or write files.
    """
    to_copy: List[str] = []
    to_skip: List[str] = []
    invalid: List[str] = []
    for name in blob_names:
        # GCS "directory" placeholders end with /
        if name.endswith("/"):
            to_skip.append(name)
            continue
        try:
            dest = destination_path(dest_root, name)
        except ValueError:
            invalid.append(name)
            continue
        if should_skip(dest, skip_existing):
            to_skip.append(name)
        else:
            to_copy.append(name)
    return to_copy, to_skip, invalid


# ---------------------------------------------------------------------------
# Secrets / GCS
# ---------------------------------------------------------------------------


def load_toml(path: Path) -> Dict[str, Any]:
    try:
        import tomllib
    except ImportError:  # Python < 3.11
        import tomli as tomllib  # type: ignore

    with path.open("rb") as f:
        return tomllib.load(f)


def load_gcs_settings(secrets_path: Path) -> Tuple[str, Dict[str, Any]]:
    data = load_toml(secrets_path)
    if "gcs" not in data or "bucket_name" not in data["gcs"]:
        raise SystemExit(
            f"Missing [gcs] bucket_name in {secrets_path}. "
            "Cannot probe or migrate without the old bucket name."
        )
    if "gcp_service_account" not in data:
        raise SystemExit(
            f"Missing [gcp_service_account] in {secrets_path}. "
            "Cannot authenticate to GCS."
        )
    bucket_name = str(data["gcs"]["bucket_name"]).strip()
    if not bucket_name:
        raise SystemExit("gcs.bucket_name is empty")
    return bucket_name, dict(data["gcp_service_account"])


def build_storage_client(sa_info: Dict[str, Any]):
    try:
        from google.cloud import storage
        from google.oauth2 import service_account
    except ImportError as exc:
        raise SystemExit(
            "google-cloud-storage is not installed. Run:\n"
            "  .venv/bin/pip install -r scripts/requirements-migrate.txt"
        ) from exc

    credentials = service_account.Credentials.from_service_account_info(sa_info)
    project = sa_info.get("project_id")
    return storage.Client(credentials=credentials, project=project)


def format_gcs_error(exc: BaseException) -> str:
    text = str(exc)
    lower = text.lower()
    hints = []
    if "403" in text or "forbidden" in lower or "access denied" in lower:
        hints.append("Permission denied — SA may lack Storage access, or billing/trial ended.")
    if "billing" in lower or "accountDisabled" in text or "disabled" in lower:
        hints.append("Billing / free trial may be disabled for this GCP project.")
    if "404" in text or "not found" in lower or "No such bucket" in text:
        hints.append("Bucket not found — check [gcs] bucket_name.")
    if not hints:
        hints.append("See the error above; if access is dead, use the manual fallback in docs/migrate_gcs_to_nfs.md.")
    return f"{type(exc).__name__}: {text}\n" + "\n".join(f"  → {h}" for h in hints)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_probe(client, bucket_name: str, sample: int = 20) -> int:
    print(f"Probing bucket: {bucket_name}")
    try:
        bucket = client.bucket(bucket_name)
        if not bucket.exists():
            print("FAIL: bucket.exists() returned False", file=sys.stderr)
            print("  → Bucket missing or SA cannot see it. Use manual fallback.", file=sys.stderr)
            return 1

        blobs = list(client.list_blobs(bucket_name, max_results=sample))
        # Also get a fuller count (capped)
        all_names = [b.name for b in client.list_blobs(bucket_name)]
        prefixes = sorted(
            {name.split("/", 1)[0] + "/" for name in all_names if "/" in name}
        )

        print(f"OK: bucket reachable")
        print(f"  objects (listed): {len(all_names)}")
        print(f"  top-level prefixes: {len(prefixes)}")
        for p in prefixes[:30]:
            print(f"    {p}")
        if len(prefixes) > 30:
            print(f"    ... ({len(prefixes) - 30} more)")
        print("Sample objects:")
        for b in blobs[:sample]:
            print(f"    {b.name}  ({b.size} bytes)")
        return 0
    except Exception as exc:
        print("FAIL: could not access bucket", file=sys.stderr)
        print(format_gcs_error(exc), file=sys.stderr)
        print(
            "\nAutomated migration is not viable. Follow Phase C (manual) in docs/migrate_gcs_to_nfs.md.",
            file=sys.stderr,
        )
        return 1


def iter_blob_names(client, bucket_name: str, prefix: Optional[str]) -> List[str]:
    kwargs = {}
    if prefix:
        kwargs["prefix"] = prefix
    return [b.name for b in client.list_blobs(bucket_name, **kwargs)]


def cmd_migrate(
    client,
    bucket_name: str,
    dest_root: Path,
    *,
    dry_run: bool,
    skip_existing: bool,
    prefix: Optional[str],
) -> int:
    try:
        names = iter_blob_names(client, bucket_name, prefix)
    except Exception as exc:
        print("FAIL: listing blobs", file=sys.stderr)
        print(format_gcs_error(exc), file=sys.stderr)
        return 1

    to_copy, to_skip, invalid = summarize_plan(names, dest_root, skip_existing)

    print(f"Bucket: {bucket_name}")
    print(f"Dest:   {dest_root}")
    print(f"Prefix: {prefix or '(all)'}")
    print(f"Mode:   {'DRY-RUN' if dry_run else 'COPY'}")
    print(f"Skip existing: {skip_existing}")
    print(f"Plan: {len(to_copy)} copy, {len(to_skip)} skip, {len(invalid)} invalid")

    if invalid:
        print("Invalid blob names:")
        for name in invalid:
            print(f"  ! {name}")

    if dry_run:
        for name in to_copy:
            dest = destination_path(dest_root, name)
            print(f"  COPY  {name} -> {dest}")
        for name in to_skip:
            print(f"  SKIP  {name}")
        print("Dry-run complete (no files written).")
        return 0 if not invalid else 2

    bucket = client.bucket(bucket_name)
    copied = skipped = failed = 0
    for name in to_skip:
        print(f"  SKIP  {name}")
        skipped += 1

    for name in to_copy:
        dest = destination_path(dest_root, name)
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            bucket.blob(name).download_to_filename(str(dest))
            print(f"  COPY  {name} -> {dest}")
            copied += 1
        except Exception as exc:
            print(f"  FAIL  {name}: {exc}", file=sys.stderr)
            failed += 1

    print(f"Summary: copied={copied} skipped={skipped} failed={failed}")
    return 0 if failed == 0 and not invalid else 1


def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description="Migrate GCS user blobs to NFS filesystem layout")
    parser.add_argument(
        "--secrets",
        type=Path,
        default=repo_root / ".streamlit" / "secrets.toml",
        help="Path to secrets.toml with [gcs] and [gcp_service_account]",
    )
    parser.add_argument(
        "--probe",
        action="store_true",
        help="Only test GCS access and list sample objects",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List planned copies without writing",
    )
    parser.add_argument(
        "--dest",
        type=Path,
        help="Destination root (e.g. /srv/budget-analysis or a staging dir)",
    )
    parser.add_argument(
        "--prefix",
        default=None,
        help="Only migrate blobs under this prefix (e.g. alice/)",
    )
    parser.add_argument(
        "--no-skip-existing",
        action="store_true",
        help="Overwrite files that already exist at dest",
    )
    return parser.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not args.probe and args.dest is None:
        print("Error: --dest is required unless using --probe", file=sys.stderr)
        return 2

    if not args.secrets.is_file():
        print(f"Secrets file not found: {args.secrets}", file=sys.stderr)
        return 2

    bucket_name, sa_info = load_gcs_settings(args.secrets)
    client = build_storage_client(sa_info)

    if args.probe:
        return cmd_probe(client, bucket_name)

    skip_existing = not args.no_skip_existing
    return cmd_migrate(
        client,
        bucket_name,
        args.dest.resolve(),
        dry_run=args.dry_run,
        skip_existing=skip_existing,
        prefix=args.prefix,
    )


if __name__ == "__main__":
    sys.exit(main())
