#!/usr/bin/env python3
import json
import logging
import os
import sys
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
    load_dotenv()

    meta_token = os.environ.get("META_ACCESS_TOKEN")
    ad_account_id = os.environ.get("META_AD_ACCOUNT_ID")
    sheet_id = os.environ.get("GOOGLE_SHEET_ID")
    creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON")

    missing = [
        name for name, val in [
            ("META_ACCESS_TOKEN", meta_token),
            ("META_AD_ACCOUNT_ID", ad_account_id),
            ("GOOGLE_SHEET_ID", sheet_id),
            ("GOOGLE_CREDENTIALS_JSON", creds_json),
        ]
        if not val
    ]
    if missing:
        log.error("Missing required env vars: %s", ", ".join(missing))
        sys.exit(1)

    yesterday = (datetime.now(PERU_TZ) - timedelta(days=1)).strftime("%Y-%m-%d")
    log.info("Fetching Meta Ads insights for %s ...", yesterday)

    insights = fetch_meta_insights(meta_token, ad_account_id, yesterday)
    if not insights:
        log.info("No insights for %s — nothing to write. Exiting.", yesterday)
        return

    log.info("Retrieved %d insight row(s) from Meta API", len(insights))

    log.info("Connecting to Google Sheets ...")
    try:
        creds = Credentials.from_service_account_info(
            json.loads(creds_json),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(sheet_id)
        ws = sh.sheet1
    except Exception as e:
        log.error("Google Sheets connection failed: %s", e)
        sys.exit(1)

    existing = ws.get_all_values()
    if not existing:
        log.info("Sheet is empty — writing header row: %s", HEADERS)
        ws.append_row(HEADERS)

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
    except Exception as e:
        log.error("Failed to append rows to sheet: %s", e)
        sys.exit(1)

    log.info("Wrote %d row(s) to sheet '%s'", len(rows), sh.title)


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
        except requests.RequestException as e:
            log.error("Meta API request failed: %s", e)
            sys.exit(1)

        body = resp.json()
        if "error" in body:
            log.error(
                "Meta API error: [%s] %s",
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
