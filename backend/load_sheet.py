"""Pull Google Drive spreadsheets (native Sheets or uploaded .xlsx) into pandas.

Sheets are registered in backend/sources.yaml. The CLI accepts a registry key,
a raw file ID, or a full Sheets URL.

First run opens a browser to authorize; token caches to .secrets/authorized_user.json.

Usage:
    python backend/load_sheet.py <key|file_id|url> [WORKSHEET_NAME]
    python backend/load_sheet.py <key|file_id|url> --csv
    python backend/load_sheet.py --all
    python backend/load_sheet.py --list
    python backend/load_sheet.py --regen-docs
"""
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

import pandas as pd
import requests
import yaml
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

REPO_ROOT = Path(__file__).resolve().parent.parent
SECRETS = REPO_ROOT / ".secrets"
CLIENT_SECRETS = SECRETS / "oauth_client.json"
TOKEN_CACHE = SECRETS / "authorized_user.json"
SOURCES_YAML = REPO_ROOT / "backend" / "sources.yaml"
ACCESSED_SHEETS_MD = REPO_ROOT / "Accessed_Sheets.md"
DATA_DIR = REPO_ROOT / "data" / "raw"

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
NATIVE_SHEET_MIME = "application/vnd.google-apps.spreadsheet"

FILE_ID_IN_URL = re.compile(r"/d/([a-zA-Z0-9_-]+)")
SAFE_FILENAME = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class Source:
    key: str
    url: str
    description: str
    committee: str | None = None

    @property
    def file_id(self) -> str:
        m = FILE_ID_IN_URL.search(self.url)
        if not m:
            raise ValueError(f"source {self.key!r} has no /d/<file_id>/ in url: {self.url}")
        return m.group(1)


def load_sources() -> list[Source]:
    if not SOURCES_YAML.exists():
        return []
    raw = yaml.safe_load(SOURCES_YAML.read_text()) or {}
    entries = raw.get("sources", []) or []
    sources = [
        Source(
            key=e["key"],
            url=e["url"],
            description=e.get("description", ""),
            committee=e.get("committee"),
        )
        for e in entries
    ]
    keys = [s.key for s in sources]
    dupes = {k for k in keys if keys.count(k) > 1}
    if dupes:
        raise ValueError(f"duplicate keys in sources.yaml: {sorted(dupes)}")
    return sources


def resolve(arg: str, sources: list[Source]) -> tuple[Source | None, str]:
    """Return (Source or None, file_id) for a CLI argument that may be a key, ID, or URL."""
    m = FILE_ID_IN_URL.search(arg)
    if m:
        file_id = m.group(1)
        for s in sources:
            if s.file_id == file_id:
                return s, file_id
        return None, file_id
    for s in sources:
        if s.key == arg:
            return s, s.file_id
    return None, arg


def get_creds() -> Credentials:
    if not CLIENT_SECRETS.exists():
        raise FileNotFoundError(f"Missing OAuth client at {CLIENT_SECRETS}")

    creds: Credentials | None = None
    if TOKEN_CACHE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_CACHE), SCOPES)

    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_CACHE.write_text(creds.to_json())
        return creds

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS), SCOPES)
    creds = flow.run_local_server(port=0)
    TOKEN_CACHE.write_text(creds.to_json())
    return creds


def _get_mime(file_id: str, token: str) -> str:
    r = requests.get(
        f"https://www.googleapis.com/drive/v3/files/{file_id}",
        params={"fields": "mimeType,name", "supportsAllDrives": "true"},
        headers={"Authorization": f"Bearer {token}"},
    )
    if r.status_code == 404:
        raise RuntimeError(
            f"File {file_id} not visible to the authenticated account. "
            "Check: (1) you signed in with the uchicago.edu account that has access, "
            "(2) the file is shared with that account, "
            "(3) if it's in a Shared Drive, that you're a member."
        )
    r.raise_for_status()
    return r.json()["mimeType"]


def _download_xlsx_bytes(file_id: str, token: str) -> bytes:
    mime = _get_mime(file_id, token)
    headers = {"Authorization": f"Bearer {token}"}
    common = {"supportsAllDrives": "true"}
    if mime == NATIVE_SHEET_MIME:
        r = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}/export",
            params={"mimeType": XLSX_MIME, **common},
            headers=headers,
        )
    else:
        r = requests.get(
            f"https://www.googleapis.com/drive/v3/files/{file_id}",
            params={"alt": "media", **common},
            headers=headers,
        )
    r.raise_for_status()
    return r.content


def load_sheet(file_id: str, worksheet: str | None = None) -> pd.DataFrame | dict[str, pd.DataFrame]:
    creds = get_creds()
    data = _download_xlsx_bytes(file_id, creds.token)
    return pd.read_excel(BytesIO(data), sheet_name=worksheet)


def _safe_filename(s: str) -> str:
    cleaned = SAFE_FILENAME.sub("_", s).strip("_")
    return cleaned or "untitled"


def dump_to_csv(key: str, tabs: dict[str, pd.DataFrame]) -> list[tuple[Path, int, int]]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    written: list[tuple[Path, int, int]] = []
    for tab_name, df in tabs.items():
        out = DATA_DIR / f"{_safe_filename(key)}__{_safe_filename(tab_name)}.csv"
        df.to_csv(out, index=False)
        written.append((out, len(df), len(df.columns)))
    return written


def render_markdown(sources: list[Source]) -> str:
    lines = [
        "<!-- AUTO-GENERATED FROM backend/sources.yaml — DO NOT EDIT BY HAND -->",
        "<!-- To update: edit backend/sources.yaml, then run `python backend/load_sheet.py --regen-docs` -->",
        "",
        "# Accessed Sheets",
        "",
        "Google Sheets registered with the loader. Pull any of them with:",
        "",
        "```bash",
        "python backend/load_sheet.py <key>",
        "```",
        "",
        "> **Listing a sheet here does not grant Google Drive access.** Each contributor's",
        "> uchicago.edu account must be share-listed on the actual file in Drive before they",
        "> can pull it. The registry only tells the loader where to look — Google enforces",
        "> who can read what.",
        "",
        "## Registered sources",
        "",
        "| Key | Description | Committee | Link |",
        "| --- | --- | --- | --- |",
    ]
    for s in sources:
        committee = s.committee or "—"
        lines.append(f"| `{s.key}` | {s.description} | {committee} | [open]({s.url}) |")
    lines.extend(
        [
            "",
            "## Adding a new sheet",
            "",
            "1. Share the Google Sheet with every uchicago.edu account that needs access (read is enough).",
            "2. Add an entry to [`backend/sources.yaml`](backend/sources.yaml) with a short `key`, the full URL, and a one-line description.",
            "3. Regenerate this file:",
            "",
            "   ```bash",
            "   python backend/load_sheet.py --regen-docs",
            "   ```",
            "",
            "4. Verify the loader can reach it:",
            "",
            "   ```bash",
            "   python backend/load_sheet.py <your-new-key>",
            "   ```",
            "",
        ]
    )
    return "\n".join(lines)


def cmd_list(sources: list[Source]) -> int:
    if not sources:
        print(f"No sources registered in {SOURCES_YAML.relative_to(REPO_ROOT)}")
        return 0
    print(f"{len(sources)} registered source(s):\n")
    width = max(len(s.key) for s in sources)
    for s in sources:
        print(f"  {s.key.ljust(width)}  {s.description}")
        print(f"  {' ' * width}  {s.url}")
    return 0


def cmd_regen_docs(sources: list[Source]) -> int:
    ACCESSED_SHEETS_MD.write_text(render_markdown(sources))
    rel = ACCESSED_SHEETS_MD.relative_to(REPO_ROOT)
    print(f"Wrote {rel} ({len(sources)} sources)")
    return 0


def cmd_pull_all(sources: list[Source]) -> int:
    if not sources:
        print(f"No sources registered in {SOURCES_YAML.relative_to(REPO_ROOT)}")
        return 1
    failures: list[tuple[str, str]] = []
    for s in sources:
        print(f"\n── {s.key} ── {s.url}")
        try:
            tabs = load_sheet(s.file_id)
            assert isinstance(tabs, dict)
            for path, rows, cols in dump_to_csv(s.key, tabs):
                print(f"  wrote {path.relative_to(REPO_ROOT)}  ({rows} rows × {cols} cols)")
        except Exception as e:  # noqa: BLE001
            print(f"  FAILED: {e}")
            failures.append((s.key, str(e)))
    if failures:
        print(f"\n{len(failures)} source(s) failed:")
        for k, msg in failures:
            print(f"  {k}: {msg}")
        return 1
    return 0


def cmd_pull_one(arg: str, worksheet: str | None, want_csv: bool, sources: list[Source]) -> int:
    source, file_id = resolve(arg, sources)
    key = source.key if source else file_id

    if want_csv:
        tabs = load_sheet(file_id)
        assert isinstance(tabs, dict)
        for path, rows, cols in dump_to_csv(key, tabs):
            print(f"wrote {path.relative_to(REPO_ROOT)}  ({rows} rows × {cols} cols)")
        return 0

    result = load_sheet(file_id, worksheet)
    if isinstance(result, dict):
        print(f"Loaded {len(result)} tabs:")
        for name, df in result.items():
            print(f"\n── {name} ── {len(df)} rows × {len(df.columns)} cols")
            print(df.head())
    else:
        print(f"Loaded {len(result)} rows × {len(result.columns)} cols")
        print(result.head())
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pull Google Sheets registered in backend/sources.yaml into pandas / CSV.",
    )
    parser.add_argument(
        "source",
        nargs="?",
        help="registry key (e.g. master_log), raw file ID, or full Sheets URL",
    )
    parser.add_argument("worksheet", nargs="?", help="optional tab name; previews that tab only")
    parser.add_argument("--list", action="store_true", help="print the registry and exit")
    parser.add_argument("--all", action="store_true", help="pull every registered source and dump each tab to data/raw/<key>__<tab>.csv")
    parser.add_argument("--csv", action="store_true", help="dump every tab of <source> to data/raw/<key>__<tab>.csv instead of previewing")
    parser.add_argument("--regen-docs", action="store_true", help="regenerate Accessed_Sheets.md from sources.yaml and exit")
    args = parser.parse_args()

    sources = load_sources()

    if args.list:
        return cmd_list(sources)
    if args.regen_docs:
        return cmd_regen_docs(sources)
    if args.all:
        return cmd_pull_all(sources)
    if not args.source:
        parser.print_usage()
        return 1
    return cmd_pull_one(args.source, args.worksheet, args.csv, sources)


if __name__ == "__main__":
    sys.exit(main())
