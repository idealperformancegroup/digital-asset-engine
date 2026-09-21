import os
import time
from pathlib import Path

import requests

TOOLKIT = Path(os.getenv("ARC_TOOLKIT_DIR", "/opt/arcads"))

def check_environment():
    print("IPG Digital Asset Engine starting", flush=True)
    print(f"Arcads toolkit present: {TOOLKIT.exists()}", flush=True)
    print(f"Meta account configured: {bool(os.getenv('META_AD_ACCOUNT_ID'))}", flush=True)
    print(f"Meta token configured: {bool(os.getenv('META_ACCESS_TOKEN'))}", flush=True)
    print(f"Arcads API configured: {bool(os.getenv('ARCADS_API_KEY'))}", flush=True)

def verify_meta_read_only():
    token = os.getenv("META_ACCESS_TOKEN")
    account_id = os.getenv("META_AD_ACCOUNT_ID")
    api_version = os.getenv("META_API_VERSION", "v23.0")

    if not token or not account_id:
        print("META VERIFY: skipped - credentials missing", flush=True)
        return

    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"

    url = f"https://graph.facebook.com/{api_version}/{account_id}"
    params = {
        "access_token": token,
        "fields": "id,name,account_status,currency,timezone_name",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        data = response.json()
        if response.ok and "error" not in data:
            print("META VERIFY: SUCCESS", flush=True)
            print(f"META ACCOUNT ID: {data.get('id')}", flush=True)
            print(f"META ACCOUNT NAME: {data.get('name')}", flush=True)
            print(f"META ACCOUNT STATUS: {data.get('account_status')}", flush=True)
            print(f"META ACCOUNT CURRENCY: {data.get('currency')}", flush=True)
            print(f"META ACCOUNT TIMEZONE: {data.get('timezone_name')}", flush=True)
        else:
            err = data.get("error", {})
            print("META VERIFY: FAILED", flush=True)
            print(f"META ERROR TYPE: {err.get('type')}", flush=True)
            print(f"META ERROR CODE: {err.get('code')}", flush=True)
            print(f"META ERROR MESSAGE: {err.get('message')}", flush=True)
    except Exception as exc:
        print("META VERIFY: FAILED", flush=True)
        print(f"META EXCEPTION: {type(exc).__name__}: {exc}", flush=True)

if __name__ == "__main__":
    check_environment()
    verify_meta_read_only()
    print("Worker ready. Waiting for jobs.", flush=True)
    while True:
        time.sleep(300)
