#!/usr/bin/env python3
import argparse
import json
import logging
import os
import sys
import traceback
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv

import gspread
from google.oauth2.service_account import Credentials

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)

META_API_VERSION = "v22.0"
META_BASE_URL = f"https://graph.facebook.com/{META_API_VERSION}"

PERU_TZ = timezone(timedelta(hours=-5))

HEADERS = [
    "Date", "Campaign", "Ad Set",
    "Spend", "Impressions", "Clicks", "CTR", "Reach", "Conversions",
]


def main():
    parser = argparse.ArgumentParser(description="Sync Meta Ads insights to Google Sheets")
    parser.add_argument("--test-sheet", action="store_true",
                        help="Write a test row to verify sheet write access (skips Meta API)")
    args = parser.parse_args()

    load_dotenv()

    meta_token = os.environ.get("META_ACCESS_TOKEN")
    ad_account_id = os.environ.get("META_AD_ACCOUNT_ID")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")
    creds_file = os.environ.get("GOOGLE_CREDENTIALS_FILE")

    missing = [
        name for name, val in [
            ("META_ACCESS_TOKEN", meta_token),
            ("META_AD_ACCOUNT_ID", ad_account_id),
        ]
        if not val
    ]
    if missing:
        log.error("[ENV] ❌ Missing required Meta vars: %s", ", ".join(missing))
        sys.exit(1)

    google_missing = []
    if not sheet_id:
        google_missing.append("GOOGLE_SHEET_ID")
    if not creds_json and not creds_file:
        google_missing.append("GOOGLE_CREDENTIALS_JSON or GOOGLE_CREDENTIALS_FILE")
    if google_missing:
        log.error("[ENV] ❌ Missing required Google vars: %s", ", ".join(google_missing))
        sys.exit(1)

    log.info("[ENV] All required env vars present ✅")

    # --- Connect to Google Sheets (always needed) ---
    log.info("[GOOGLE] 🔄 Connecting to Sheets ...")
    try:
        if creds_json:
            creds_dict = json.loads(creds_json)
        else:
            with open(creds_file) as f:
                creds_dict = json.load(f)
        creds = Credentials.from_service_account_info(
            creds_dict,
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        ws = sh.sheet1
        log.info("[GOOGLE] ✅ Connected to sheet '%s' (ID: %s)", sh.title, sheet_id)
    except json.JSONDecodeError as e:
        log.error("[GOOGLE] ❌ Invalid credentials JSON: %s", e)
        sys.exit(1)
    except gspread.exceptions.APIError as e:
        log.error("[GOOGLE] ❌ API error (check sheet permissions): %s", e)
        sys.exit(1)
    except FileNotFoundError:
        log.error("[GOOGLE] ❌ Credentials file not found: %s", creds_file)
        sys.exit(1)
    except Exception:
        log.error("[GOOGLE] ❌ Connection failed:\n%s", traceback.format_exc())
        sys.exit(1)

    # --- Test mode: write a dummy row to verify write access ---
    if args.test_sheet:
        run_test_sheet(ws, sh)
        return

    # --- Normal mode: Meta Ads API ---
    yesterday = (datetime.now(PERU_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    log.info("[META] 🔄 Fetching insights for %s ...", yesterday)
    insights = fetch_meta_insights(meta_token, ad_account_id, yesterday)
    log.info("[META] ✅ Connected — got %d insight row(s)", len(insights))

    if not insights:
        log.info("[META] ℹ️  No ads data for %s — nothing to write.", yesterday)
        log.info("[GOOGLE] ℹ️  No data to append (sheet is ready for future data).")
        log.info("=== ✅ Pipeline validation complete: Meta ✅ | Google ✅ ===")
        return

    # --- Ensure headers exist ---
    existing = ws.get_all_values()
    if not existing:
        log.info("[GOOGLE] Sheet is empty — writing header row.")
        ws.append_row(HEADERS)

    # --- Build rows and write ---
    rows = []
    for row in insights:
        actions = row.get("actions") or []
        conversions = sum(int(a.get("value", 0)) for a in actions)
        rows.append([
            yesterday,
            row.get("campaign_name", ""),
            row.get("adset_name", ""),
            float(row.get("spend", 0)),
            int(row.get("impressions", 0)),
            int(row.get("clicks", 0)),
            float(row.get("ctr", 0)),
            int(row.get("reach", 0)),
            conversions,
        ])

    try:
        ws.append_rows(rows, value_input_option="USER_ENTERED")
        log.info("[GOOGLE] ✅ Wrote %d row(s) to sheet '%s'", len(rows), sh.title)
    except Exception:
        log.error("[GOOGLE] ❌ Failed to append rows:\n%s", traceback.format_exc())
        sys.exit(1)

    log.info("=== ✅ Sync complete: %d row(s) written ===", len(rows))


def run_test_sheet(ws, sh):
    now = datetime.now(PERU_TZ).strftime("%Y-%m-%d %H:%M")
    existing = ws.get_all_values()
    if not existing:
        log.info("[TEST] Sheet is empty — writing header row.")
        ws.append_row(HEADERS)

    row = [now, "[TEST] Verificación", "test", 1.23, 100, 5, 0.05, 80, 2]
    try:
        ws.append_row(row, value_input_option="USER_ENTERED")
        log.info("[TEST] ✅ Row written to sheet '%s' — delete it manually when done.", sh.title)
    except Exception:
        log.error("[TEST] ❌ Failed to write test row:\n%s", traceback.format_exc())
        sys.exit(1)


def fetch_meta_insights(token: str, ad_account_id: str, date: str) -> list[dict]:
    if not ad_account_id.startswith("act_"):
        ad_account_id = f"act_{ad_account_id}"

    url = f"{META_BASE_URL}/{ad_account_id}/insights"
    params = {
        "access_token": token,
        "level": "adset",
        "fields": "campaign_name,adset_name,spend,impressions,clicks,ctr,reach,actions,date_start",
        "time_range": json.dumps({"since": date, "until": date}),
        "limit": 500,
    }

    results = []
    next_url = None

    while True:
        try:
            resp = requests.get(next_url or url, params=params if not next_url else {})
            resp.raise_for_status()
        except requests.RequestException:
            log.exception("[META] ❌ HTTP request failed")
            sys.exit(1)

        body = resp.json()
        if "error" in body:
            log.error(
                "[META] ❌ API error [%s]: %s",
                body["error"].get("code", "?"),
                body["error"].get("message", ""),
            )
            sys.exit(1)

        results.extend(body.get("data", []))
        next_url = body.get("paging", {}).get("next")
        if not next_url:
            break

    return results


if __name__ == "__main__":
    main()
