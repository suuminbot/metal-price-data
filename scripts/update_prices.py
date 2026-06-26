#!/usr/bin/env python3
"""
MetalPriceTracker – price fetcher

Usage:
  python scripts/update_prices.py             # daily update
  python scripts/update_prices.py --backfill  # initial 3-year backfill
"""

import argparse
import json
import os
from datetime import date, timedelta
from pathlib import Path

import requests

API_KEY         = os.environ["METAL_API_KEY"]
BASE_URL        = "https://api.metalpriceapi.com/v1"
DATA_PATH       = Path("data/prices.json")
TROY_OZ_TO_GRAM = 31.1035
BACKFILL_YEARS  = 3


def jpy_per_gram(rate_value: float) -> float:
    """rate_value = XAU (or XPT) per 1 JPY  →  return JPY per gram."""
    jpy_per_oz = 1.0 / rate_value
    return round(jpy_per_oz / TROY_OZ_TO_GRAM, 1)


def fetch_latest() -> list[dict]:
    resp = requests.get(f"{BASE_URL}/latest", params={
        "api_key":    API_KEY,
        "base":       "JPY",
        "currencies": "XAU,XPT",
    }, timeout=30)
    resp.raise_for_status()
    data  = resp.json()
    today = date.today().isoformat()
    rates = data["rates"]
    print(f"Fetched latest: {today}", flush=True)
    return [{
        "date":               today,
        "gold_jpy_per_g":     jpy_per_gram(rates["XAU"]),
        "platinum_jpy_per_g": jpy_per_gram(rates["XPT"]),
    }]


def fetch_timeframe(start: date, end: date) -> list[dict]:
    resp = requests.get(f"{BASE_URL}/timeframe", params={
        "api_key":    API_KEY,
        "base":       "JPY",
        "currencies": "XAU,XPT",
        "start_date": start.isoformat(),
        "end_date":   end.isoformat(),
    }, timeout=30)
    resp.raise_for_status()
    data    = resp.json()
    entries = []
    for date_str, rates in data["rates"].items():
        entries.append({
            "date":               date_str,
            "gold_jpy_per_g":     jpy_per_gram(rates["XAU"]),
            "platinum_jpy_per_g": jpy_per_gram(rates["XPT"]),
        })
    return entries


def backfill() -> list[dict]:
    today   = date.today()
    entries = []
    for i in range(BACKFILL_YEARS, 0, -1):
        start = today - timedelta(days=365 * i)
        end   = min(today - timedelta(days=365 * (i - 1) - 1), today)
        print(f"Fetching {start} → {end} …", flush=True)
        entries.extend(fetch_timeframe(start, end))
    entries.sort(key=lambda e: e["date"], reverse=True)
    return entries


def load_existing() -> list[dict]:
    if DATA_PATH.exists():
        return json.loads(DATA_PATH.read_text())["history"]
    return []


def save(history: list[dict]) -> None:
    DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "updated_at": date.today().isoformat() + "T00:00:00Z",
        "history":    history,
    }
    DATA_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"Saved {len(history)} entries to {DATA_PATH}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backfill", action="store_true",
                        help="Fetch full 3-year history (run once at initial setup)")
    args = parser.parse_args()

    if args.backfill:
        history = backfill()
    else:
        new_entries    = fetch_latest()
        existing       = load_existing()
        existing_dates = {e["date"] for e in existing}
        merged         = [e for e in new_entries if e["date"] not in existing_dates] + existing
        cutoff         = (date.today() - timedelta(days=365 * BACKFILL_YEARS)).isoformat()
        history        = [e for e in merged if e["date"] >= cutoff]

    save(history)


if __name__ == "__main__":
    main()
