# UChicago USG Finance

Permanent, USG-managed system for managing and displaying student organization allocation data. Two components:

- **Internal allocation platform** — committee chairs enter suggestions, College Council reviews, VPSO publishes
- **Public website** — students browse official allocation results, historical data, and rankings

Full product context, roles, data model, and workflow: **[CLAUDE.md](CLAUDE.md)**.

---

## Repo layout

```
uchicagofinance/
├── CLAUDE.md               # product spec, roles, data model, workflow
├── README.md               # this file — setup instructions
├── plan/                   # planning docs
├── backend/                # python — data ingestion + (eventually) API
│   ├── load_sheet.py       # google drive → pandas loader
│   ├── requirements.txt
│   └── onboarding/         # data-pull onboarding (auth, sources, how to add new sheets)
├── frontend/               # vite + react + typescript
├── data/                   # local data artifacts (gitignored)
└── .secrets/               # oauth credentials (gitignored — never commit)
```

---

## Prerequisites

- **Python 3.11+**
- **Node 20+** and **npm 10+**
- **Git**
- A **uchicago.edu Google account** with access to the source spreadsheets (for backend ingestion)
- **`oauth_client.json`** emailed to you by the repo maintainer — see [Backend setup](#backend-setup) below

---

## Clone

```bash
git clone https://github.com/admin-usg-uchicago/uchicagofinance.git
cd uchicagofinance
```

---

## Backend setup

Ingests allocation data from Google Drive spreadsheets into pandas.

### 1. Install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
```

### 2. Get the OAuth client file

The repo maintainer will email you a file named `oauth_client.json`. Do not share this file further — if you need to onboard someone, ask the maintainer to email them directly.

Create the `.secrets/` folder and place the file inside:

```bash
mkdir -p .secrets
# move the emailed oauth_client.json into .secrets/oauth_client.json
```

`.secrets/` is gitignored — the file will never be committed.

### 3. First run

Sheets the loader knows about are listed in [`Accessed_Sheets.md`](Accessed_Sheets.md) (auto-generated from [`backend/sources.yaml`](backend/sources.yaml)). Pull any of them by key:

```bash
# USG Master Log — RSO directory + ongoing event allocations
python3 backend/load_sheet.py master_log

# SGFC Annual Cycle (WIP) — one committee's annual allocation working doc
python3 backend/load_sheet.py sgfc_annual

# Or pull every registered source and dump each tab to data/raw/<key>__<tab>.csv
python3 backend/load_sheet.py --all
```

You can also pass a raw file ID or a full Sheets URL directly. Other useful flags: `--list` (show registry), `--csv` (dump to CSV instead of preview), `--regen-docs` (rebuild `Accessed_Sheets.md` after editing `sources.yaml`).

- On the **first** command a browser opens → sign in with your **uchicago.edu** account → approve Drive read access
- Your personal access token caches to `.secrets/authorized_user.json` (this file is per-user — never share it)
- Subsequent commands reuse the cached token and run silently
- You should see previews of every tab in each file (tab name, row × col count, first 5 rows)

To register a new sheet, see [Adding a new sheet](Accessed_Sheets.md#adding-a-new-sheet). Tab descriptions and known quirks for each source live in [backend/onboarding/README.md § 7](backend/onboarding/README.md#7-current-data-sources).

### More details

Current registered data sources, per-file quirks, troubleshooting, and the procedure for adding new sheets are all in **[backend/onboarding/README.md](backend/onboarding/README.md)**.

### For the maintainer only

If you're setting up the Google Cloud project from scratch (or rotating the OAuth client), see Section 4 of [backend/onboarding/README.md](backend/onboarding/README.md). Everyone else can skip that.

---

## Frontend setup

Vite + React + TypeScript SPA (both internal platform and public site will live here, routed separately).

```bash
cd frontend
npm install
npm run dev
```

Dev server runs at `http://localhost:5173`.

**Other scripts:**

- `npm run build` — production build into `frontend/dist/`
- `npm run preview` — serve the production build locally
- `npm run lint` — ESLint

---

## Daily workflow

```bash
# terminal 1 — frontend
cd frontend && npm run dev

# terminal 2 — backend (ad-hoc data pulls, or later a running API)
source .venv/bin/activate
python backend/load_sheet.py <key>          # pull one registered sheet (see Accessed_Sheets.md)
python backend/load_sheet.py --all          # pull every registered sheet to data/raw/*.csv
```

---

## Contributing

- **Never commit `.secrets/`** — it's gitignored; keep it that way
- Before adding a new spreadsheet data source, read the "Adding a new data source" section in [backend/onboarding/README.md](backend/onboarding/README.md)
- For non-trivial work, follow the workflow protocol in [CLAUDE.md](CLAUDE.md) (discovery → research → planning → execution, tracked under `.claude-project/`)

---

## Useful links

- **Repo:** https://github.com/admin-usg-uchicago/uchicagofinance
- **Product spec:** [CLAUDE.md](CLAUDE.md)
- **Data ingestion onboarding:** [backend/onboarding/README.md](backend/onboarding/README.md)
