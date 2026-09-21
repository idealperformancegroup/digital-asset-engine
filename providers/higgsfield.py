import os
import requests

from .base import CreativeJob, enforce_cost_gate


class HiggsfieldProvider:
    name = "higgsfield"
    base_url = "https://api.higgsfield.ai"

    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("HIGGSFIELD_API_KEY")

    @property
    def configured(self):
        return bool(self.api_key)

    def headers(self):
        if not self.api_key:
            raise RuntimeError("HIGGSFIELD_API_KEY is not configured.")
        return {"Authorization": f"Key {self.api_key}"}

    def verify(self):
        probe_id = "00000000-0000-0000-0000-000000000000"
        response = requests.get(
            f"{self.base_url}/requests/{probe_id}/status",
            headers=self.headers(),
            timeout=30,
        )
        return response.status_code == 404, response.status_code

    def estimate(self, job: CreativeJob, endpoint_id: str, parameters: dict):
        response = requests.post(
            f"{self.base_url}/{endpoint_id}/estimate",
            headers={**self.headers(), "Content-Type": "application/json"},
            json=parameters,
            timeout=30,
        )
        if not response.ok:
            raise RuntimeError(
                f"Higgsfield estimate failed status={response.status_code}: "
                f"{response.text[:300]}"
            )
        data = response.json()
        job.estimated_cost_usd = float(data["usd"])
        job.metadata["estimate_credits"] = data.get("credits")
        job.metadata["estimate_endpoint"] = endpoint_id
        return data

    def submit(self, job: CreativeJob):
        # Deliberately blocked until a model-specific request builder and
        # provider cost estimator are implemented and a job is approved.
        enforce_cost_gate(job)
        raise NotImplementedError(
            "Higgsfield paid generation is intentionally disabled until "
            "model-specific request construction and cost estimation are installed."
        )
