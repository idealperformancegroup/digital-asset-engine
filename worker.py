import os
import time
from pathlib import Path

TOOLKIT = Path(os.getenv("ARC_TOOLKIT_DIR", "/opt/arcads"))

def check_environment():
    print("IPG Digital Asset Engine starting", flush=True)
    print(f"Arcads toolkit present: {TOOLKIT.exists()}", flush=True)
    print(f"Meta account configured: {bool(os.getenv('META_AD_ACCOUNT_ID'))}", flush=True)
    print(f"Meta token configured: {bool(os.getenv('META_ACCESS_TOKEN'))}", flush=True)
    print(f"Arcads API configured: {bool(os.getenv('ARCADS_API_KEY'))}", flush=True)
    print("Worker ready. Waiting for jobs.", flush=True)

if __name__ == "__main__":
    check_environment()
    while True:
        time.sleep(300)
