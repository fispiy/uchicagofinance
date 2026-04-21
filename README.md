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

`<FILE_ID>` is the long string between `/d/` and `/edit` in a Drive spreadsheet URL. For a first-run sanity check, try the USG Master Log:

```bash
python backend/load_sheet.py 1SI-IWAXx3h7mfdqbJ3oiPXFJq0CcMPEV
```

- A browser opens → sign in with your **uchicago.edu** account → approve Drive read access
- Your personal access token caches to `.secrets/authorized_user.json` (this file is per-user — never share it)
- You should see previews of the `Yearly Allocations`, `Annual Allocations`, and `RSO Directory` tabs
- Subsequent runs are silent

**Currently registered sources:**

| File | ID |
|---|---|
| USG Master Log (RSO directory + ongoing allocations) | `1SI-IWAXx3h7mfdqbJ3oiPXFJq0CcMPEV` |
| SGFC Annual Cycle (WIP) | `1SdUHg38eCHeE1RcBiX7Exvs2Xnob50LB` |

Full source catalog, tab descriptions, and known quirks: [backend/onboarding/README.md § 7](backend/onboarding/README.md#7-current-data-sources).

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
python backend/load_sheet.py <FILE_ID>
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
