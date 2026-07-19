# GCS → NFS data migration

One-off copy of user configs and uploads from the old Google Cloud Storage bucket into the NFS share used by Budget Analysis.

**Layout (unchanged):**

```
gs://<bucket>/{username}/configs/...
gs://<bucket>/{username}/uploads/...
        ↓
/srv/budget-analysis/{username}/configs/...
/srv/budget-analysis/{username}/uploads/...
```

The app already reads this layout via `storage_utils.py` (`/data` in the pod = NFS export).

**Do not overwrite** files that already exist on NFS (e.g. a newly created test account). The script skips existing files by default.

---

## Prerequisites

- Local `.streamlit/secrets.toml` still contains leftover `[gcs]` (`bucket_name`) and `[gcp_service_account]`
- Python venv in the repo (`.venv`)
- For automated copy to the live share: write access to `/srv/budget-analysis` on **vanaheim.lan** (or stage elsewhere and `rsync`/`scp`)

Install migration-only dependency (not part of app `requirements.txt`):

```bash
cd ~/source/BudgetAnalysis
source .venv/bin/activate
pip install -r scripts/requirements-migrate.txt
```

---

## Phase A — Probe (required first)

```bash
.venv/bin/python scripts/migrate_gcs_to_nfs.py --probe
```

| Result | Meaning |
|--------|---------|
| Prints `OK: bucket reachable` + object list | Automated path is viable → Phase B |
| `FAIL` / 403 / billing / not found | Stop automation → **Phase C (manual)** |

Do not run a full copy until probe succeeds.

---

## Phase B — Automated migrate (probe OK only)

### Dry-run

```bash
# Staging dir on Valhalla (safe review)
mkdir -p /tmp/budget-analysis-migrate
.venv/bin/python scripts/migrate_gcs_to_nfs.py \
  --dry-run \
  --dest /tmp/budget-analysis-migrate
```

Or target the live share if you are on Vanaheim (or have it mounted):

```bash
.venv/bin/python scripts/migrate_gcs_to_nfs.py \
  --dry-run \
  --dest /srv/budget-analysis
```

### Optional: one user first

```bash
.venv/bin/python scripts/migrate_gcs_to_nfs.py \
  --dest /srv/budget-analysis \
  --prefix '<username>/'
```

### Full copy (skip existing)

```bash
.venv/bin/python scripts/migrate_gcs_to_nfs.py \
  --dest /srv/budget-analysis
```

Overwrite is off by default. Only use `--no-skip-existing` if you intentionally want to replace NFS files.

**Do not delete GCS objects yet** — keep the bucket as backup until you verify in the app.

### Verify

On Vanaheim:

```bash
find /srv/budget-analysis -type f | sort
```

In the app: log in as a migrated user and confirm configs + CSVs.

---

## Phase C — Manual fallback (probe failed)

If the GCP free trial expired or the SA cannot list the bucket, copy a few users by hand.

1. Open [Google Cloud Console](https://console.cloud.google.com/) → **Cloud Storage** → your budget bucket.
2. For each username folder, download `configs/` and `uploads/` (zip or individual files).
3. On **vanaheim.lan**, place files with the same names:

```bash
sudo mkdir -p /srv/budget-analysis/<username>/configs
sudo mkdir -p /srv/budget-analysis/<username>/uploads

# Example after scp'ing files to the server:
sudo cp <username>_config.json /srv/budget-analysis/<username>/configs/
sudo cp <username>_upload_config.json /srv/budget-analysis/<username>/configs/
sudo cp *.csv /srv/budget-analysis/<username>/uploads/
```

4. Permissions: `755` dirs / `644` files under root ownership is fine with the current `no_root_squash` export.
5. Skip any path that already exists for accounts created after the NFS cutover.
6. Verify by logging into the app as a migrated user.

If the Console also cannot open the bucket, data may already be gone from GCP — recover from any personal backups you have, or re-seed users via the app.

---

## Checklist

- [ ] `pip install -r scripts/requirements-migrate.txt`
- [ ] `--probe` succeeded **or** decided on manual fallback
- [ ] Dry-run reviewed (automated path)
- [ ] Copy completed with skip-existing (or manual place)
- [ ] `find /srv/budget-analysis -type f` looks right
- [ ] Migrated user login + data OK in the app
- [ ] Fake / post-cutover accounts unchanged
- [ ] GCS left intact as backup until you are satisfied

---

## Script reference

| Flag | Purpose |
|------|---------|
| `--probe` | Test SA + bucket access only |
| `--dry-run` | Plan copies; write nothing |
| `--dest PATH` | Destination root (required except `--probe`) |
| `--prefix USER/` | Limit to one user prefix |
| `--no-skip-existing` | Overwrite existing dest files |
| `--secrets PATH` | Alternate secrets.toml (default: `.streamlit/secrets.toml`) |
