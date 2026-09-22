import os
from datetime import datetime, timezone

import requests


class DurableState:
    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "").rstrip("/")
        self.key = os.getenv("SUPABASE_SECRET_KEY", "")
        self.bucket = os.getenv("ASSET_BUCKET", "digital-asset-engine-assets")

    @property
    def configured(self):
        return bool(self.url and self.key)

    def headers(self, extra=None):
        h = {"apikey": self.key, "Authorization": f"Bearer {self.key}"}
        if extra:
            h.update(extra)
        return h

    def claim(self, job_id, objective, prompt, ceiling, approval_state):
        payload = {
            "job_id": job_id,
            "objective": objective,
            "prompt": prompt,
            "cost_ceiling_usd": ceiling,
            "approval_state": approval_state,
            "status": "CLAIMED",
        }
        r = requests.post(
            f"{self.url}/rest/v1/digital_asset_engine_jobs",
            headers=self.headers({
                "Content-Type": "application/json",
                "Prefer": "return=representation",
            }),
            json=payload,
            timeout=30,
        )
        if r.status_code == 409:
            return False, self.get(job_id)
        if not r.ok:
            raise RuntimeError(f"durable claim failed status={r.status_code}: {r.text[:300]}")
        return True, r.json()[0] if r.json() else payload

    def get(self, job_id):
        r = requests.get(
            f"{self.url}/rest/v1/digital_asset_engine_jobs",
            headers=self.headers(),
            params={"job_id": f"eq.{job_id}", "select": "*"},
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"durable lookup failed status={r.status_code}: {r.text[:300]}")
        rows = r.json()
        return rows[0] if rows else None

    def update(self, job_id, **fields):
        fields["updated_at"] = datetime.now(timezone.utc).isoformat()
        r = requests.patch(
            f"{self.url}/rest/v1/digital_asset_engine_jobs",
            headers=self.headers({
                "Content-Type": "application/json",
                "Prefer": "return=minimal",
            }),
            params={"job_id": f"eq.{job_id}"},
            json=fields,
            timeout=30,
        )
        if not r.ok:
            raise RuntimeError(f"durable update failed status={r.status_code}: {r.text[:300]}")

    def archive_output(self, job_id, provider_url):
        r = requests.get(provider_url, timeout=120)
        r.raise_for_status()
        content_type = r.headers.get("Content-Type", "application/octet-stream").split(";")[0]
        ext = {
            "image/png": "png",
            "image/jpeg": "jpg",
            "image/webp": "webp",
        }.get(content_type, "bin")
        path = f"{job_id}/output.{ext}"
        u = requests.post(
            f"{self.url}/storage/v1/object/{self.bucket}/{path}",
            headers=self.headers({
                "Content-Type": content_type,
                "x-upsert": "false",
            }),
            data=r.content,
            timeout=120,
        )
        if not u.ok:
            raise RuntimeError(f"asset archive failed status={u.status_code}: {u.text[:300]}")
        return self.bucket, path
