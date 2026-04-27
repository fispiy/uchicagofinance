# Data Pulling — Onboarding

How to pull USG allocation data from Google Drive spreadsheets into pandas DataFrames inside this repo, and how to add new data sources later.

---

## 1. What this does and why

USG allocation data currently lives in a collection of Google Drive spreadsheets owned by the VPSO / committee chairs. To power the internal platform and the public website described in [CLAUDE.md](../../CLAUDE.md), we need to pull those spreadsheets into pandas, normalize them, and land them in our own database.

This onboarding doc covers the **ingestion layer only** — auth, download, and initial DataFrame load. Normalization, DB schema, and publishing workflow live elsewhere.

---

## 2. Auth approach — OAuth user credentials (not service account)

We use **OAuth user credentials** (desktop client flow), where the script authenticates as a real uchicago.edu user with access to the sheets.

### Why not service accounts?
UChicago's Google Workspace enforces the org policy `iam.disableServiceAccountKeyCreation`, which blocks service account key downloads. Only a UChicago-level Organization Policy Administrator can disable it. OAuth user creds sidestep the policy entirely and are the "more secure alternative" Google itself recommends.

### Why "Desktop" OAuth client type?
The ingestion script is a CLI tool that runs on a developer's machine (or later a server/cron job). It is NOT a user-facing web app. The public website never talks to Google Sheets — it reads from our database, which this script populates.

### Why "Internal" audience?
Only uchicago.edu accounts ever authenticate. Internal skips Google's verification process and has no test-user list to maintain.

---

## 3. Prerequisites

- **Python 3.11+**
- A **uchicago.edu Google account** with access to the source sheets (directly, or as a member of the Shared Drive they live in)
- **Project Owner or Editor** role on the `USG Finance` Google Cloud project (or whichever Cloud project we settle on) — needed to create OAuth credentials
- Node 20+ if you also plan to run the frontend (not required for ingestion)

---

## 4. One-time Google Cloud setup

Skip this section if someone else already configured the Cloud project and shared the OAuth client JSON with you — jump to [Section 5](#5-one-time-local-setup).

### 4.1 Enable APIs
Google Cloud Console → **APIs & Services → Library** → enable:
- **Google Drive API** (required — we download via Drive)
- **Google Sheets API** (optional — only needed if we add per-cell edits later)

### 4.2 Configure OAuth consent screen
**APIs & Services → OAuth consent screen**

- **User Type:** Internal
- **App name:** e.g., `USG Finance Ingestion`
- **Support email:** your uchicago.edu email
- **Developer contact:** your uchicago.edu email
- **Scopes → Add or Remove Scopes** — add:
  - `https://www.googleapis.com/auth/drive.readonly`

### 4.3 Create OAuth client ID
**APIs & Services → Credentials → Create Credentials → OAuth client ID**

- **Application type:** Desktop app
- **Name:** e.g., `usg-finance-cli`
- Click **Create** → **Download JSON**

The downloaded file has a name like `client_secret_<longid>.apps.googleusercontent.com.json`.

---

## 5. One-time local setup

### 5.1 Place the OAuth client JSON
Rename the downloaded file to exactly `oauth_client.json` and move it to `.secrets/` in the repo root:

```
/Users/<you>/.../uchicagofinance/.secrets/oauth_client.json
```

`.secrets/` is gitignored. **Never commit this file.** The file contains your `client_secret` — if it leaks, revoke it immediately in Cloud Console → Credentials.

### 5.2 Python environment
From the repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 5.3 First run — authorize
```bash
python backend/load_sheet.py <FILE_ID>
```

- A browser opens (or a URL is printed — paste it into your browser)
- Sign in with your **uchicago.edu** account (not personal Gmail)
- Approve the `Drive read-only` consent
- Page confirms "The authentication flow has completed"
- Token caches to `.secrets/authorized_user.json` — subsequent runs are silent

---

## 6. Running the loader

### Command

```bash
source .venv/bin/activate
python backend/load_sheet.py <FILE_ID> [WORKSHEET_NAME]
```

### Finding `FILE_ID`
From the Drive URL:
```
https://docs.google.com/spreadsheets/d/<FILE_ID>/edit?gid=...
```
Grab the string between `/d/` and `/edit`.

### Behavior
- If `WORKSHEET_NAME` is omitted, every tab is loaded and a preview of each is printed
- If provided, only that tab is returned as a single DataFrame
- Works for **both** native Google Sheets AND .xlsx files uploaded to Drive (the loader detects which and picks the right Drive API endpoint)
- Supports files in **Shared Drives** (not just My Drive) via `supportsAllDrives=true`

### Programmatic use
```python
from backend.load_sheet import load_sheet

df = load_sheet("<FILE_ID>", "Sheet1")               # one tab
all_tabs = load_sheet("<FILE_ID>")                   # dict[tab_name, DataFrame]
```

---

## 7. Current data sources

The canonical list of registered sheets (key, URL, description) lives in [`backend/sources.yaml`](../sources.yaml) and is rendered into [`Accessed_Sheets.md`](../../Accessed_Sheets.md) at the repo root. This section adds the editorial content the registry doesn't carry: role within the data model, per-tab notes, and known quirks.

| Key | Role | Notes |
|---|---|---|
| **`sgfc_annual`** (SGFC Annual Cycle, WIP) | One committee's working doc for one annual allocation cycle | .xlsx. 4 tabs trace workflow: `ORIGINAL No cuts; pre-appeal` → `Example` → `No cuts; post-appeal` → `FINAL w cuts; post appeals`. Scratchpad cells mixed with data. |
| **`master_log`** (USG Master Log) | Canonical ongoing records | .xlsx. 3 tabs: `Yearly Allocations` (event-based decisions, 277 rows), `Annual Allocations` (empty — likely where finalized cycles will land), `RSO Directory (8-6-25)` (master RSO list, 447 rows). |

### Known quirks per file
- **`Yearly Allocations`** — real headers are on row 1 of the xlsx (row 0 is a title). Use `pd.read_excel(..., header=1)` or drop the first data row after loading.
- **File 1 `FINAL` tab** — contains scratchpad cells ("Proposed Flat-Rate Cut Factor:", "Sum with Above Rates:") interleaved with real rows. Needs row-level filtering during normalization.
- **File 1 `Example` tab** — likely a template, not production data. Exclude from ingestion.
- **`Annual Allocations` tab is currently empty.** Confirm with VPSO whether this is the target destination for finalized annual results from committee working docs.

### Mapping to the data model in [CLAUDE.md](../../CLAUDE.md)
| Entity | Source |
|---|---|
| **RSO** (master) | File 2 → `RSO Directory (8-6-25)` |
| **Allocation — event-based** | File 2 → `Yearly Allocations` |
| **Allocation — annual, in-progress** | File 1 → all four committee tabs |
| **Allocation — annual, canonical** | File 2 → `Annual Allocations` (once populated) |

---

## 8. Adding a new data source

Follow this checklist whenever a new spreadsheet needs to be ingested (e.g., PCC's annual working doc, a new fiscal year's master log, a standalone committee sheet).

### 8.1 Confirm access
1. Open the sheet URL in your browser signed in as **the same uchicago.edu account** used for the OAuth token (`.secrets/authorized_user.json`)
2. If you see "Request access," ask the owner to share with you (or add you to the Shared Drive)
3. Copy the full sheet URL (or just the Drive ID — the registry accepts either)

### 8.2 Smoke-test with the existing loader
```bash
python backend/load_sheet.py <NEW_URL_OR_FILE_ID>
```
This prints every tab's shape and first 5 rows. Verify:
- All expected tabs appear
- Data isn't empty
- Headers look right (first data row should be real data, not a title / merged cell)

### 8.3 Register the sheet
Add an entry to [`backend/sources.yaml`](../sources.yaml) with a short snake_case `key`, the full URL, and a one-line description (and `committee:` if applicable). Then regenerate the human-readable index:

```bash
python backend/load_sheet.py --regen-docs
```

This rewrites [`Accessed_Sheets.md`](../../Accessed_Sheets.md) at the repo root. Commit `sources.yaml` and `Accessed_Sheets.md` together.

### 8.4 Decide how it fits the data model
Document the file in [Section 7 above](#7-current-data-sources) with:
- Role (master / working doc / historical archive / etc.)
- Per-tab description
- Which entity from [CLAUDE.md](../../CLAUDE.md) each tab feeds
- Known quirks (header row offset, scratchpad cells, empty tabs, etc.)

### 8.5 Handle per-file quirks in the normalization layer
**Do not modify [load_sheet.py](../load_sheet.py) for file-specific logic.** The loader is a generic downloader. Per-file parsing belongs in a separate module (`backend/normalize/<source>.py` or similar), which:
- Takes the raw DataFrame/dict from `load_sheet()`
- Selects the right tab
- Applies header offset, row filtering, column renames
- Returns a DataFrame conforming to the canonical entity schema

This keeps the ingestion layer generic and keeps quirks discoverable and testable.

### 8.6 Wire into scheduled pulls
Once we have a scheduler (cron / GitHub Actions / Cloud Scheduler — TBD), it should call `python backend/load_sheet.py --all` on the daily refresh cadence the public site expects. Because the registry is the single source of truth, registering a sheet in `sources.yaml` is all it takes for the scheduled job to start pulling it. Per-source extras the scheduler may eventually need (normalizer module path, target entity, refresh frequency override) can be added as new optional fields on the `sources.yaml` entry.

---

## 9. Troubleshooting

### `404 Client Error: Not Found` when fetching file metadata
The authenticated account can't see the file. Check in order:
1. Open the Drive URL in your browser — does it open, or does it say "Request access"?
2. Are you signed in with the right account? Verify:
   ```bash
   python -c "import json; print(json.load(open('.secrets/authorized_user.json')).get('account','?'))"
   ```
3. Force a re-auth if the cached token is for the wrong account:
   ```bash
   rm .secrets/authorized_user.json
   python backend/load_sheet.py <FILE_ID>
   ```
4. If the file is in a Shared Drive, confirm you're a member of that drive. (`supportsAllDrives=true` is already set in the loader.)

### `redirect_uri_mismatch` during OAuth
Cloud Console → Credentials → your OAuth client → **Authorized redirect URIs** → add `http://localhost`. Desktop clients sometimes need this explicitly.

### `Insufficient Permission` / `403` on download
The OAuth consent screen doesn't include the Drive scope. Go to OAuth consent screen → Scopes → add `https://www.googleapis.com/auth/drive.readonly`. Then delete `.secrets/authorized_user.json` and re-auth to refresh the granted scopes.

### Token works but downloads are empty
- Check whether the tab you named actually has data — the loader returns an empty DataFrame for empty tabs (e.g., `Annual Allocations` is currently empty by design)
- If every tab is empty, the file may have been replaced or cleared upstream

### `cryptography` import hangs on first run
Cold-start import of `cryptography`'s Rust bindings can take several seconds on some Macs. Wait — it completes. Not an error.

### The first data row looks like column headers
The source xlsx has a title row or merged cells above the real headers. Either:
- Pass `header=1` to `pd.read_excel` in the normalizer for that source, OR
- Drop the first row after load and reset column names

Example quirk: File 2's `Yearly Allocations` tab.

---

## 10. Security

- **Never commit `.secrets/`** — it's gitignored, keep it that way
- **Never log `oauth_client.json` or `authorized_user.json` contents** — both contain credentials
- **If `oauth_client.json` leaks:** Cloud Console → Credentials → your OAuth client → **Reset secret** (invalidates the leaked secret) → download new JSON → replace in `.secrets/`
- **If `authorized_user.json` leaks:** Revoke the token at [myaccount.google.com/permissions](https://myaccount.google.com/permissions) (find the OAuth app, remove access) → delete the local file → re-auth
- **Scope is read-only.** The loader cannot modify source spreadsheets. If we later add write operations, add `drive.file` or `sheets` scopes deliberately and re-consent.
- **Tokens expire.** Access tokens are short-lived; the refresh token in `authorized_user.json` is used automatically. If the refresh token is revoked (e.g., password reset, admin action), the next run will reopen the browser for re-auth.

---

## 11. File layout reference

```
uchicagofinance/
├── .secrets/                       # gitignored; OAuth client + cached token
│   ├── oauth_client.json
│   └── authorized_user.json        # created on first run
├── backend/
│   ├── load_sheet.py               # generic Drive → pandas loader
│   ├── requirements.txt
│   └── onboarding/
│       └── README.md               # this file
├── frontend/                       # Vite + React + TS (separate concern)
└── CLAUDE.md                       # product + data model context
```
