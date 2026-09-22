import os
import requests


class DurableState:
    def __init__(self):
        self.url = os.getenv("STATE_BRIDGE_URL", "").rstrip("/")
        self.token = os.getenv("STATE_BRIDGE_TOKEN", "")

    @property
    def configured(self):
        return bool(self.url and self.token)

    def _call(self, payload, timeout=120):
        r = requests.post(
            self.url,
            headers={
                "x-bridge-token": self.token,
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
        if not r.ok:
            raise RuntimeError(
                f"durable state bridge failed status={r.status_code}: {r.text[:300]}"
            )
        return r.json()

    def claim(self, job_id, objective, prompt, ceiling, approval_state):
        data = self._call({
            "action": "claim",
            "job_id": job_id,
            "objective": objective,
            "prompt": prompt,
            "cost_ceiling_usd": ceiling,
            "approval_state": approval_state,
        })
        return bool(data.get("claimed")), data.get("row") or data.get("existing")

    def get(self, job_id):
        return self._call({"action": "get", "job_id": job_id}).get("row")

    def update(self, job_id, **fields):
        self._call({"action": "update", "job_id": job_id, "fields": fields})

    def archive_output(self, job_id, provider_url):
        data = self._call(
            {"action": "archive", "job_id": job_id, "provider_url": provider_url},
            timeout=180,
        )
        return data.get("bucket"), data.get("path")
