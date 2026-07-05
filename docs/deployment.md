# Deployment Guide — `budget-analysis.schmidlin.casa`

This guide covers **local development** and **homelab production** for Budget Analysis: a Streamlit app backed by **Google Sheets** and **Google Cloud Storage** (no database server to install).

Production deploys to the same stack as [Valhalla Landing Page](https://github.com/mschmidlin1/ValhallaLandingPage), [Dr. JAM](https://github.com/mschmidlin1/dr-jam), and [Resume Customizer](https://github.com/mschmidlin1/ResumeCustomizer): **self-hosted GitHub Actions runner** on **Valhalla**, **Docker** images on **GHCR**, **k3s** on Valhalla, public HTTPS via the existing **Cloudflare Tunnel** (`cloudflared`).

**Target URL:** `https://budget-analysis.schmidlin.casa`

**Prerequisites (already in place from other homelab apps):**

- k3s cluster running on **Valhalla** with `kubectl` working
- `cloudflared` pod healthy in the `cloudflared` namespace
- `schmidlin.casa` **Active** in Cloudflare with SSL/TLS mode **Full**
- You can SSH to Valhalla and run `kubectl`

For background, see Valhalla docs — especially [Self-Hosting.md](https://github.com/mschmidlin1/ValhallaLandingPage/blob/main/docs/Self-Hosting.md) and [CustomDomainSetup.md](https://github.com/mschmidlin1/ValhallaLandingPage/blob/main/docs/CustomDomainSetup.md).

> **Note:** The app is currently on [Streamlit Community Cloud](https://budgetanalysis-creditcardtransactions.streamlit.app/). This guide moves it to the homelab. Keep Streamlit Cloud until homelab deploy is verified, then retire it.

---

## Summary

| Item | Value |
|------|-------|
| **Public URL** | `https://budget-analysis.schmidlin.casa` |
| **GitHub repo** | `github.com/mschmidlin1/BudgetAnalysis` |
| **Deploy trigger** | Push to `main` (or manual workflow run) |
| **GHCR image** | `ghcr.io/mschmidlin1/budget-analysis` |
| **K8s namespace** | `budget-analysis` |
| **In-cluster Service URL** | `http://budget-analysis.budget-analysis.svc.cluster.local:80` |
| **Container** | Python 3.11 + Streamlit on port **8501** |
| **App host** | **Valhalla** (k3s + runner + tunnel) |
| **Data stores** | **Google Sheets** (users) + **GCS** (configs, uploads) |

**What you add:** a new namespace, GHCR package, self-hosted runner for this repo, and one Cloudflare tunnel hostname.

**What you do not need:** MongoDB, Vanaheim, LAN database routing, or host-IP firewall rules for a database port.

---

## Architecture

```mermaid
flowchart TB
    subgraph git [GitHub]
        main[main branch]
    end

    subgraph valhalla [Valhalla — k3s host]
        runner[Self-hosted runner]
        k3s[k3s cluster]
        ns[namespace budget-analysis]
        pod[Streamlit pod :8501]
    end

    subgraph gcp [Google Cloud]
        sheets[(Google Sheets — users)]
        gcs[(GCS bucket — configs/uploads)]
    end

    subgraph ghcr [GHCR]
        img["ghcr.io/mschmidlin1/budget-analysis"]
    end

    subgraph cf [Cloudflare]
        host[budget-analysis.schmidlin.casa]
        cfd[cloudflared pod]
    end

    main --> runner --> img --> ns --> pod
    pod --> sheets
    pod --> gcs
    host --> cfd --> ns
```

When a visitor opens `https://budget-analysis.schmidlin.casa`:

1. Cloudflare terminates HTTPS and routes through the existing tunnel to `cloudflared` on Valhalla.
2. `cloudflared` forwards to `http://budget-analysis.budget-analysis.svc.cluster.local:80`.
3. The Service (port 80 → pod 8501) routes to the Streamlit pod.
4. Streamlit reads `.streamlit/secrets.toml` (from a K8s Secret in production) and calls Google Sheets and GCS over HTTPS.

---

## Current status

| Item | Location | Notes |
|------|----------|-------|
| **App code** | `main.py`, `*_tab.py`, `user_tools.py`, `gcs_utils.py`, … | Entry point is `main.py` at repo root |
| **Dependencies** | `requirements.txt` | Streamlit, pandas, plotly, gspread, google-cloud-storage |
| **Default configs** | `default_config.json`, `sample_transactions.csv` | Seeded into GCS for new users |
| **Secrets template** | `.streamlit/secrets.toml.example` | GCP, Sheets, GCS, cookie |
| **GitHub repo** | `github.com/mschmidlin1/BudgetAnalysis` | Synced with local |
| **Streamlit Cloud** | `budgetanalysis-creditcardtransactions.streamlit.app` | Existing prod; homelab replaces this |

**Still to do:** Docker files, k8s manifests, CI workflow, runner, tunnel hostname.

**Already in place (Streamlit Cloud):** Google Cloud project, service account, GCS bucket, users Sheet, and `secrets.toml` — reuse the same values for homelab deploy.

### Assumptions

| Topic | Choice |
|-------|--------|
| **App / k3s host** | **Valhalla** |
| **GCP / secrets** | Reuse existing Streamlit Cloud configuration |
| **CI runner** | Self-hosted on Valhalla; `KUBECONFIG: /home/mike/.kube/config` |
| **Secrets in CI** | Single GitHub secret `SECRETS_TOML` (copy from Streamlit Cloud or local `secrets.toml`) |

---

## Phase overview

| Phase | What | Where |
|-------|------|-------|
| **1** | Docker files + local run | This repo |
| **2** | Kubernetes manifests | This repo |
| **3** | Self-hosted runner | Valhalla |
| **4** | GitHub Actions deploy workflow | This repo |
| **5** | GitHub permissions + secrets | GitHub |
| **6** | First deploy + verify | CI → Valhalla |
| **7** | Cloudflare tunnel hostname | Cloudflare |
| **8** | Public URL verification | Browser / CLI |

Phases 1–4 can land on a feature branch and merge to `main`. The workflow only runs after it exists on `main`.

---

## Phase 1 — Local development and Docker

No database container or host-IP wiring — just `secrets.toml` and Streamlit.

### 1.1 Run directly (simplest)

```powershell
cd C:\Users\mschm\source\BudgetAnalysis
.\.venv\Scripts\Activate.ps1
streamlit run main.py
```

Open `http://localhost:8501`. Confirm login, registration, CSV upload, and the sunburst chart work.

### 1.2 Docker files

Add these three files at the repo root. The same image is used locally and in production.

**`Dockerfile`**

```dockerfile
FROM python:3.11-bookworm

WORKDIR /app
RUN mkdir -p /app/.streamlit

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY *.py .
COPY default_config.json sample_transactions.csv example_nested_config.json ./

EXPOSE 8501
CMD ["streamlit", "run", "main.py", "--server.address=0.0.0.0", "--server.port=8501"]
```

**`.dockerignore`**

```gitignore
.git
.venv
__pycache__
**/__pycache__
*.py[cod]
.streamlit/secrets.toml
notebooks
uploaded_files
configs
credentials.yaml
credit-card-analysis-*.json
.env
.env.*
```

**`docker-compose.yml`**

```yaml
services:
  app:
    build: .
    ports:
      - "8501:8501"
    volumes:
      - ./.streamlit/secrets.toml:/app/.streamlit/secrets.toml:ro
```

That's it — no extra env vars. GCP credentials come entirely from the mounted `secrets.toml`.

### 1.3 Run in Docker

From the repo root (WSL or Linux):

```bash
docker compose up --build
```

Open `http://localhost:8501`.

> **WSL tip:** If `docker compose build` fails with a `credsStore: desktop.exe` error, clear WSL's `~/.docker/config.json` to `{}` (leftover from Docker Desktop).

---

## Phase 2 — Kubernetes manifests

Create `k8s/` with four files. Do **not** add `cloudflared` — the tunnel is shared cluster infrastructure.

### 2.1 `k8s/namespace.yaml`

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: budget-analysis
```

### 2.2 `k8s/deployment.yaml`

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: budget-analysis
  namespace: budget-analysis
spec:
  replicas: 1
  selector:
    matchLabels:
      app: budget-analysis
  template:
    metadata:
      labels:
        app: budget-analysis
    spec:
      containers:
        - name: app
          image: ghcr.io/mschmidlin1/budget-analysis:latest
          ports:
            - containerPort: 8501
          volumeMounts:
            - name: streamlit-secrets
              mountPath: /app/.streamlit/secrets.toml
              subPath: secrets.toml
              readOnly: true
          livenessProbe:
            httpGet:
              path: /_stcore/health
              port: 8501
            initialDelaySeconds: 20
            periodSeconds: 15
          readinessProbe:
            httpGet:
              path: /_stcore/health
              port: 8501
            initialDelaySeconds: 10
            periodSeconds: 10
          resources:
            requests:
              cpu: 250m
              memory: 512Mi
            limits:
              cpu: "1"
              memory: 1Gi
      volumes:
        - name: streamlit-secrets
          secret:
            secretName: budget-analysis-secrets
            items:
              - key: secrets.toml
                path: secrets.toml
```

### 2.3 `k8s/service.yaml`

```yaml
apiVersion: v1
kind: Service
metadata:
  name: budget-analysis
  namespace: budget-analysis
spec:
  type: ClusterIP
  selector:
    app: budget-analysis
  ports:
    - port: 80
      targetPort: 8501
```

### 2.4 `k8s/kustomization.yaml`

```yaml
apiVersion: kustomize.config.k8s.io/v1beta1
kind: Kustomization

resources:
  - namespace.yaml
  - deployment.yaml
  - service.yaml
```

### 2.5 Apply once manually (optional)

```bash
kubectl apply -k k8s/
kubectl get all -n budget-analysis
```

`ImagePullBackOff` or `CreateContainerConfigError` before the first CI run is expected.

---

## Phase 3 — Self-hosted GitHub Actions runner on Valhalla

Runners are **per repository**. Register a new one even if Valhalla already has runners for other repos.

1. [github.com/mschmidlin1/BudgetAnalysis/settings/actions/runners](https://github.com/mschmidlin1/BudgetAnalysis/settings/actions/runners) → **New self-hosted runner** → **Linux** → **x64**.
2. On Valhalla:

   ```bash
   mkdir -p ~/actions-runner-budget-analysis && cd ~/actions-runner-budget-analysis
   ```

3. Run GitHub's **Configure** commands exactly (download, extract, `./config.sh`).
4. Accept defaults at prompts, then:

   ```bash
   sudo ./svc.sh install
   sudo ./svc.sh start
   sudo ./svc.sh status
   ```

5. Confirm runner shows **Idle** or **Active** in GitHub settings.

Runner user needs `docker` group membership and `~/.kube/config` (see [Valhalla KubernetesSetup.md §1.3](https://github.com/mschmidlin1/ValhallaLandingPage/blob/main/docs/KubernetesSetup.md)).

---

## Phase 4 — GitHub Actions deploy workflow

Create `.github/workflows/deploy.yml`:

```yaml
name: Deploy

on:
  push:
    branches:
      - main
  workflow_dispatch:

permissions:
  contents: read
  packages: write

jobs:
  deploy:
    runs-on: self-hosted

    env:
      KUBECONFIG: /home/mike/.kube/config

    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Log in to GHCR
        run: echo "${{ secrets.GITHUB_TOKEN }}" | docker login ghcr.io -u "${{ github.actor }}" --password-stdin

      - name: Build and push image
        run: |
          IMAGE=ghcr.io/mschmidlin1/budget-analysis
          docker build -t "${IMAGE}:${{ github.sha }}" -t "${IMAGE}:latest" .
          docker push "${IMAGE}:${{ github.sha }}"
          docker push "${IMAGE}:latest"

      - name: Apply Kubernetes manifests
        run: kubectl apply -k k8s/

      - name: Apply Kubernetes Secret
        env:
          SECRETS_TOML: ${{ secrets.SECRETS_TOML }}
        run: |
          kubectl -n budget-analysis create secret generic budget-analysis-secrets \
            --from-literal=secrets.toml="$SECRETS_TOML" \
            --dry-run=client -o yaml | kubectl apply -f -

      - name: Roll out new image
        run: |
          kubectl set image deployment/budget-analysis \
            app=ghcr.io/mschmidlin1/budget-analysis:${{ github.sha }} \
            -n budget-analysis
          kubectl rollout status deployment/budget-analysis \
            -n budget-analysis \
            --timeout=5m
```

The workflow sets `KUBECONFIG` explicitly because the runner service does not load `~/.bashrc` — see [Valhalla Self-Hosting.md — KUBECONFIG gotcha](https://github.com/mschmidlin1/ValhallaLandingPage/blob/main/docs/Self-Hosting.md#common-gotcha-kubeconfig-in-ci).

---

## Phase 5 — GitHub repository settings

### 5.1 Actions permissions

1. [Settings → Actions](https://github.com/mschmidlin1/BudgetAnalysis/settings/actions) → Actions enabled.
2. **Workflow permissions** → **Read and write permissions** (for GHCR push).

### 5.2 Repository secret

Copy your existing Streamlit Cloud secrets (or local `.streamlit/secrets.toml`) into a GitHub Actions secret:

| Secret | Value |
|--------|-------|
| `SECRETS_TOML` | Full contents of production `secrets.toml` |

From Streamlit Cloud: app → **Settings → Secrets** → copy all sections.

From a local file:

```powershell
Get-Content .streamlit\secrets.toml -Raw | Set-Clipboard
```

### 5.3 GHCR visibility (after first deploy)

Packages → `budget-analysis` → **Package settings** → **Public** (so k3s can pull without `imagePullSecrets`).

---

## Phase 6 — First deploy and verify

1. Commit Phases 1, 2, and 4; push to **`main`**.
2. Watch [Actions → Deploy](https://github.com/mschmidlin1/BudgetAnalysis/actions).
3. On Valhalla:

   ```bash
   kubectl get pods -n budget-analysis
   ```

   Expected: `Running`, `1/1`.

4. In-cluster health check:

   ```bash
   kubectl run curl-test --rm -it --restart=Never --image=curlimages/curl -- \
     curl -s -o /dev/null -w "HTTP %{http_code}\n" \
     http://budget-analysis.budget-analysis.svc.cluster.local:80/_stcore/health
   ```

   Expected: `HTTP 200`.

5. Check logs if GCP calls fail:

   ```bash
   kubectl logs -n budget-analysis deploy/budget-analysis --tail=50
   ```

---

## Phase 7 — Cloudflare Tunnel route

Add a **Public Hostname** on the **existing** homelab tunnel (do not create a second tunnel).

1. [Cloudflare Zero Trust](https://one.dash.cloudflare.com/) → **Networks** → **Tunnels** → your tunnel → **Public Hostname** → **Add**.

| Field | Value |
|-------|-------|
| **Subdomain** | `budget-analysis` |
| **Domain** | `schmidlin.casa` |
| **Path** | *(empty)* |
| **Type** | `HTTP` |
| **URL** | `http://budget-analysis.budget-analysis.svc.cluster.local:80` |

2. Confirm DNS record **`budget-analysis`** (proxied) exists under `schmidlin.casa`.

---

## Phase 8 — Verify the public URL

```bash
curl -I https://budget-analysis.schmidlin.casa
```

Expected: `HTTP/2 200` with a valid cert.

Open **`https://budget-analysis.schmidlin.casa`** and confirm login, registration, CSV upload, and visualization.

### Retire Streamlit Cloud (optional)

1. [share.streamlit.io](https://share.streamlit.io/) → delete or pause the app.
2. Update `README.md` to point at `https://budget-analysis.schmidlin.casa`.

### Link from Valhalla (optional)

Add `url: "https://budget-analysis.schmidlin.casa"` to [Valhalla `links.js`](https://github.com/mschmidlin1/ValhallaLandingPage/blob/main/src/js/links.js).

---

## Local development vs production

| | Local | Production |
|---|-------|------------|
| **Run** | `streamlit run main.py` or `docker compose up --build` | k8s pod on Valhalla |
| **URL** | `http://localhost:8501` | `https://budget-analysis.schmidlin.casa` |
| **Secrets** | `.streamlit/secrets.toml` on disk | K8s Secret mounted in pod |
| **Updates** | Save → refresh | Push to `main` |

---

## Day-to-day operations

| Task | How |
|------|-----|
| Deploy | Push to **`main`** |
| Watch deploy | [Actions → Deploy](https://github.com/mschmidlin1/BudgetAnalysis/actions) |
| Pod health | `kubectl get pods -n budget-analysis` |
| Logs | `kubectl logs -n budget-analysis deploy/budget-analysis -f` |
| Roll back | `kubectl rollout undo deployment/budget-analysis -n budget-analysis` |
| Update secrets | Change `SECRETS_TOML`, re-run **Deploy** |

---

## Troubleshooting

### Google Sheets errors

| Symptom | Fix |
|---------|-----|
| Permission denied | Share Sheet with service account as Editor |
| Sheet not found | Check `[connections.gsheets] spreadsheet` URL |
| API disabled | Enable Google Sheets API |
| Missing tab | Worksheet must be named `users` |

### GCS errors

| Symptom | Fix |
|---------|-----|
| 403 | Grant `Storage Object Admin` on bucket |
| Bucket not found | Check `[gcs] bucket_name` |
| Client error | Add `universe_domain = "googleapis.com"` under `[gcp_service_account]` |

### Deploy / k8s

| Symptom | Fix |
|---------|-----|
| Workflow missing | File must be on `main` |
| Runner idle | [Check runners](https://github.com/mschmidlin1/BudgetAnalysis/settings/actions/runners) |
| `ImagePullBackOff` | GHCR package public; tag exists |
| KUBECONFIG error | Workflow needs `KUBECONFIG: /home/mike/.kube/config` |
| Tunnel 502 | `kubectl get pods -n cloudflared` |
| Wrong site | Tunnel URL must be `http://budget-analysis.budget-analysis.svc.cluster.local:80` |
| DNS NXDOMAIN | Check Cloudflare for `budget-analysis` record |

Test outbound HTTPS from a pod:

```bash
kubectl run net-test --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s -o /dev/null -w "HTTP %{http_code}\n" https://www.googleapis.com
```

---

## Completion checklist

- [ ] `SECRETS_TOML` copied from Streamlit Cloud (or local `secrets.toml`)
- [ ] `Dockerfile`, `.dockerignore`, `docker-compose.yml` committed
- [ ] `k8s/` manifests committed
- [ ] Self-hosted runner on Valhalla (Idle/Active)
- [ ] `.github/workflows/deploy.yml` on `main`
- [ ] GitHub secret `SECRETS_TOML` set; GHCR package public
- [ ] Deploy workflow green; pod `Running 1/1`
- [ ] Cloudflare hostname `budget-analysis.schmidlin.casa` → in-cluster Service
- [ ] `curl -I https://budget-analysis.schmidlin.casa` → 200
- [ ] Browser smoke test passes
- [ ] *(Optional)* Streamlit Cloud retired; Valhalla link added

---

## See also

- [Resume Customizer deployment.md](https://github.com/mschmidlin1/ResumeCustomizer/blob/main/docs/deployment.md)
- [Dr. JAM Deployment.md](https://github.com/mschmidlin1/dr-jam/blob/main/docs/Deployment.md)
- [Valhalla Self-Hosting.md](https://github.com/mschmidlin1/ValhallaLandingPage/blob/main/docs/Self-Hosting.md)
- [Streamlit GSheets connection](https://github.com/streamlit/gsheets-connection)
