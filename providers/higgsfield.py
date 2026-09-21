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
            f"{self.base_url}/estimate/{endpoint_id}",
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

    def submit(self, job: CreativeJob, endpoint_id: str, parameters: dict):
        """Submit one explicitly approved paid generation and wait for its result."""
        enforce_cost_gate(job)
        if not self.api_key:
            raise RuntimeError("HIGGSFIELD_API_KEY is not configured.")

        # The official Python SDK reads HF_KEY. Keep Railway's existing secret
        # name as the source of truth and map it only inside the worker process.
        os.environ["HF_KEY"] = self.api_key
        import higgsfield_client

        request_ids = []

        def on_enqueue(request_id):
            request_ids.append(str(request_id))
            job.request_id = str(request_id)
            job.status = "SUBMITTED"

        job.status = "SUBMITTING"
        result = higgsfield_client.subscribe(
            endpoint_id,
            arguments=parameters,
            on_enqueue=on_enqueue,
        )

        if request_ids and not job.request_id:
            job.request_id = request_ids[-1]
        job.status = "COMPLETED"
        job.metadata["provider_result"] = result

        images = result.get("images") or []
        if images:
            first = images[0]
            if isinstance(first, dict):
                job.output_location = first.get("url")
            elif isinstance(first, str):
                job.output_location = first

        return result
