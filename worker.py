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


def verify_higgsfield_read_only():
    """Verify Higgsfield credentials without submitting a billable generation."""
    key = os.getenv("HIGGSFIELD_API_KEY")
    print(f"Higgsfield API configured: {bool(key)}", flush=True)
    if not key:
        print("HIGGSFIELD VERIFY: skipped - credentials missing", flush=True)
        return

    # Higgsfield's authenticated request-status endpoint returns:
    # 401 for invalid credentials, and 404 when the request ID does not exist
    # (or belongs to another account). Using a random UUID therefore proves
    # authentication without creating a generation or consuming credits.
    probe_id = "00000000-0000-0000-0000-000000000000"
    url = f"https://api.higgsfield.ai/requests/{probe_id}/status"
    try:
        response = requests.get(
            url,
            headers={"Authorization": f"Key {key}"},
            timeout=30,
        )
        if response.status_code == 404:
            print("HIGGSFIELD VERIFY: SUCCESS", flush=True)
            print("HIGGSFIELD VERIFY MODE: authenticated non-generation probe", flush=True)
        elif response.status_code == 401:
            print("HIGGSFIELD VERIFY: FAILED", flush=True)
            print("HIGGSFIELD ERROR: invalid or unauthorized API credentials", flush=True)
        else:
            print(f"HIGGSFIELD VERIFY: INCONCLUSIVE status={response.status_code}", flush=True)
            print(f"HIGGSFIELD RESPONSE: {response.text[:300]}", flush=True)
    except Exception as exc:
        print("HIGGSFIELD VERIFY: FAILED", flush=True)
        print(f"HIGGSFIELD ERROR: {exc}", flush=True)

def meta_get(path, token, params=None):
    api_version = os.getenv("META_API_VERSION", "v23.0")
    url = f"https://graph.facebook.com/{api_version}/{path}"
    safe_params = dict(params or {})
    safe_params["access_token"] = token
    response = requests.get(url, params=safe_params, timeout=30)
    data = response.json()
    if not response.ok or "error" in data:
        err = data.get("error", {})
        raise RuntimeError(f"{err.get('type')} code={err.get('code')}: {err.get('message')}")
    return data

def verify_meta_read_only():
    token = os.getenv("META_ACCESS_TOKEN")
    account_id = os.getenv("META_AD_ACCOUNT_ID")
    if not token or not account_id:
        print("META VERIFY: skipped - credentials missing", flush=True)
        return
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"
    try:
        data = meta_get(account_id, token, {
            "fields": "id,name,account_status,currency,timezone_name"
        })
        print("META VERIFY: SUCCESS", flush=True)
        print(f"META ACCOUNT ID: {data.get('id')}", flush=True)
        print(f"META ACCOUNT NAME: {data.get('name')}", flush=True)
        print(f"META ACCOUNT STATUS: {data.get('account_status')}", flush=True)
        print(f"META ACCOUNT CURRENCY: {data.get('currency')}", flush=True)
        print(f"META ACCOUNT TIMEZONE: {data.get('timezone_name')}", flush=True)
    except Exception as exc:
        print("META VERIFY: FAILED", flush=True)
        print(f"META ERROR: {exc}", flush=True)

def read_meta_operation():
    token = os.getenv("META_ACCESS_TOKEN")
    account_id = os.getenv("META_AD_ACCOUNT_ID")
    if not token or not account_id:
        return
    if not account_id.startswith("act_"):
        account_id = f"act_{account_id}"
    try:
        campaigns = meta_get(f"{account_id}/campaigns", token, {
            "fields": "id,name,status,effective_status,objective",
            "limit": 10,
        }).get("data", [])
        print(f"META OPERATION: CAMPAIGNS READ SUCCESS ({len(campaigns)} returned)", flush=True)
        for c in campaigns:
            print(f"CAMPAIGN: {c.get('name')} | status={c.get('effective_status') or c.get('status')} | objective={c.get('objective')}", flush=True)

        insights = meta_get(f"{account_id}/insights", token, {
            "level": "ad",
            "fields": "ad_id,ad_name,campaign_name,adset_name,spend,impressions,clicks,ctr,cpc,cpm,actions,action_values",
            "date_preset": "maximum",
            "limit": 100,
        }).get("data", [])
        print(f"META OPERATION: AD INSIGHTS READ SUCCESS ({len(insights)} rows returned)", flush=True)

        spend_total = sum(float(r.get("spend", 0) or 0) for r in insights)
        impressions_total = sum(int(r.get("impressions", 0) or 0) for r in insights)
        clicks_total = sum(int(r.get("clicks", 0) or 0) for r in insights)
        purchases = 0.0
        purchase_value = 0.0
        for row in insights:
            for action in row.get("actions", []) or []:
                if action.get("action_type") == "purchase":
                    purchases += float(action.get("value", 0) or 0)
            for value in row.get("action_values", []) or []:
                if value.get("action_type") == "purchase":
                    purchase_value += float(value.get("value", 0) or 0)

        print(f"META TOTAL SPEND: {spend_total:.2f}", flush=True)
        print(f"META TOTAL IMPRESSIONS: {impressions_total}", flush=True)
        print(f"META TOTAL CLICKS: {clicks_total}", flush=True)
        print(f"META TOTAL PURCHASES: {purchases:g}", flush=True)
        print(f"META TOTAL PURCHASE VALUE: {purchase_value:.2f}", flush=True)

        ranked = sorted(insights, key=lambda r: float(r.get("spend", 0) or 0), reverse=True)[:5]
        for r in ranked:
            print(
                f"AD: {r.get('ad_name')} | campaign={r.get('campaign_name')} | "
                f"spend={r.get('spend','0')} | impressions={r.get('impressions','0')} | "
                f"clicks={r.get('clicks','0')} | ctr={r.get('ctr','0')} | cpc={r.get('cpc','0')}",
                flush=True,
            )
    except Exception as exc:
        print("META OPERATION: READ FAILED", flush=True)
        print(f"META OPERATION ERROR: {exc}", flush=True)

if __name__ == "__main__":
    check_environment()
    verify_higgsfield_read_only()
    verify_meta_read_only()
    read_meta_operation()
    print("Worker ready. Waiting for jobs.", flush=True)
    while True:
        time.sleep(300)
