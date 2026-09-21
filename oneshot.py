import os
import json

from providers.base import CreativeJob
from providers.higgsfield import HiggsfieldProvider
from providers.router import route_job


EXPECTED_JOB_ID = "ipg-first-production-image-20260921"


def main():
    approved = os.getenv("ONE_SHOT_APPROVED", "").lower() == "true"
    job_id = os.getenv("ONE_SHOT_JOB_ID", "")
    ceiling = float(os.getenv("MAX_JOB_COST_USD", "0.01"))

    if not approved:
        print("ONE SHOT: NOT APPROVED - exiting without generation", flush=True)
        return 2
    if job_id != EXPECTED_JOB_ID:
        print("ONE SHOT: INVALID JOB ID - exiting without generation", flush=True)
        return 3
    if ceiling > 0.01:
        print("ONE SHOT: CEILING TOO HIGH - exiting without generation", flush=True)
        return 4

    provider = HiggsfieldProvider()
    if not provider.configured:
        print("ONE SHOT: HIGGSFIELD NOT CONFIGURED", flush=True)
        return 5

    job = CreativeJob(
        objective="first bounded production image test",
        asset_type="image",
        prompt="A clean professional abstract gradient background for an advertising test.",
        cost_ceiling_usd=ceiling,
        approval_state="APPROVED",
    )
    model = route_job(job)
    params = {
        "prompt": job.prompt,
        "batch_size": 1,
        "resolution": "720p",
        "aspect_ratio": "1:1",
        "enhance_prompt": False,
    }

    estimate = provider.estimate(job, model.endpoint_id, params)
    print(
        f"ONE SHOT ESTIMATE: provider={model.provider} model={model.model_id} "
        f"usd={job.estimated_cost_usd:.4f} ceiling={job.cost_ceiling_usd:.4f}",
        flush=True,
    )
    if job.estimated_cost_usd is None or job.estimated_cost_usd > ceiling:
        print("ONE SHOT: BLOCKED BY COST CEILING", flush=True)
        return 6

    result = provider.submit(job, model.endpoint_id, params)
    safe = {
        "job_id": job_id,
        "provider": model.provider,
        "model": model.model_id,
        "estimated_cost_usd": job.estimated_cost_usd,
        "actual_cost_usd": job.actual_cost_usd,
        "request_id": job.request_id,
        "status": job.status,
        "output_location": job.output_location,
        "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
        "estimate_credits": estimate.get("credits"),
    }
    print("ONE SHOT RESULT: " + json.dumps(safe, sort_keys=True), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
