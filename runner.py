import json
import os

from durable_state import DurableState
from providers.base import CreativeJob
from providers.higgsfield import HiggsfieldProvider
from providers.router import route_job


def env_bool(name, default=False):
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def main():
    job_id = os.getenv("RUN_JOB_ID", "").strip()
    prompt = os.getenv("RUN_PROMPT", "").strip()
    objective = os.getenv("RUN_OBJECTIVE", "bounded creative generation").strip()
    approval = os.getenv("RUN_APPROVED", "").strip().lower() == "true"
    dry_run = env_bool("RUN_DRY_RUN", True)
    ceiling = float(os.getenv("MAX_JOB_COST_USD", "0.01"))
    max_ceiling = float(os.getenv("ABSOLUTE_MAX_JOB_COST_USD", "0.05"))
    resolution = os.getenv("RUN_RESOLUTION", "720p")
    aspect_ratio = os.getenv("RUN_ASPECT_RATIO", "1:1")
    enhance_prompt = env_bool("RUN_ENHANCE_PROMPT", False)

    if not job_id:
        print("RUNNER: BLOCKED - RUN_JOB_ID required", flush=True)
        return 2
    if not prompt:
        print("RUNNER: BLOCKED - RUN_PROMPT required", flush=True)
        return 3
    if ceiling <= 0 or ceiling > max_ceiling:
        print(f"RUNNER: BLOCKED - ceiling {ceiling:.4f} outside allowed range (absolute max {max_ceiling:.4f})", flush=True)
        return 4

    state = DurableState()
    if not state.configured:
        print("RUNNER: BLOCKED - durable state not configured", flush=True)
        return 8

    claimed, existing = state.claim(
        job_id, objective, prompt, ceiling,
        "APPROVED" if approval else "NOT_APPROVED",
    )
    if not claimed:
        print(
            "RUNNER: DUPLICATE BLOCKED - durable job_id already exists "
            f"job_id={job_id} status={(existing or {}).get('status')}",
            flush=True,
        )
        return 9

    provider = HiggsfieldProvider()
    if not provider.configured:
        state.update(job_id, status="BLOCKED", error="HIGGSFIELD_API_KEY not configured")
        print("RUNNER: BLOCKED - HIGGSFIELD_API_KEY not configured", flush=True)
        return 5

    try:
        job = CreativeJob(
            objective=objective,
            asset_type="image",
            prompt=prompt,
            cost_ceiling_usd=ceiling,
            approval_state="APPROVED" if approval else "NOT_APPROVED",
        )
        model = route_job(job)
        params = {
            "prompt": job.prompt,
            "batch_size": 1,
            "resolution": resolution,
            "aspect_ratio": aspect_ratio,
            "enhance_prompt": enhance_prompt,
        }

        estimate = provider.estimate(job, model.endpoint_id, params)
        state.update(
            job_id,
            provider=model.provider,
            model=model.model_id,
            estimated_cost_usd=job.estimated_cost_usd,
            status="ESTIMATED",
        )
        print(
            f"RUNNER ESTIMATE: job_id={job_id} provider={model.provider} "
            f"model={model.model_id} usd={job.estimated_cost_usd:.4f} "
            f"ceiling={job.cost_ceiling_usd:.4f} dry_run={dry_run} approved={approval}",
            flush=True,
        )

        if job.estimated_cost_usd is None or job.estimated_cost_usd > ceiling:
            state.update(job_id, status="BLOCKED_COST")
            print("RUNNER: BLOCKED BY COST CEILING", flush=True)
            return 6

        if dry_run:
            state.update(job_id, status="DRY_RUN_COMPLETE")
            print("RUNNER DRY RUN: estimate passed; no generation submitted", flush=True)
            return 0

        if not approval:
            state.update(job_id, status="BLOCKED_APPROVAL")
            print("RUNNER: BLOCKED - paid generation not explicitly approved", flush=True)
            return 7

        state.update(job_id, status="SUBMITTING")
        result = provider.submit(job, model.endpoint_id, params)
        state.update(
            job_id,
            request_id=job.request_id,
            provider_output_url=job.output_location,
            actual_cost_usd=job.actual_cost_usd,
            status=job.status,
        )

        bucket = path = None
        if job.output_location:
            bucket, path = state.archive_output(job_id, job.output_location)
            state.update(
                job_id,
                asset_bucket=bucket,
                asset_path=path,
                status="ARCHIVED",
                completed_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            )

        safe = {
            "job_id": job_id,
            "objective": objective,
            "provider": model.provider,
            "model": model.model_id,
            "estimated_cost_usd": job.estimated_cost_usd,
            "cost_ceiling_usd": job.cost_ceiling_usd,
            "actual_cost_usd": job.actual_cost_usd,
            "request_id": job.request_id,
            "status": "ARCHIVED" if path else job.status,
            "provider_output_location": job.output_location,
            "asset_bucket": bucket,
            "asset_path": path,
            "estimate_credits": estimate.get("credits"),
            "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
        }
        print("RUNNER RESULT: " + json.dumps(safe, sort_keys=True), flush=True)
        return 0
    except Exception as exc:
        state.update(job_id, status="FAILED", error=str(exc)[:1000])
        print(f"RUNNER: FAILED - {type(exc).__name__}: {str(exc)[:300]}", flush=True)
        return 10


if __name__ == "__main__":
    raise SystemExit(main())
