import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from durable_state import DurableState
from providers.base import CreativeJob, CostGateError
from providers.higgsfield import HiggsfieldProvider
from providers.router import route_job


def _json(handler, status, payload):
    body = json.dumps(payload).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _max_job_cost():
    return float(os.getenv("MAX_JOB_COST_USD", "0.01"))


def _authorized(handler):
    expected = os.getenv("JOB_API_TOKEN")
    provided = handler.headers.get("X-Job-Token")
    return bool(expected) and provided == expected


def _build_job(payload):
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt_required")
    requested_ceiling = float(payload.get("cost_ceiling_usd", _max_job_cost()))
    if requested_ceiling <= 0:
        raise ValueError("positive_cost_ceiling_required")
    ceiling = min(requested_ceiling, _max_job_cost())
    job = CreativeJob(
        objective=payload.get("objective", "owner submitted creative job"),
        asset_type="image",
        prompt=prompt,
        cost_ceiling_usd=ceiling,
        approval_state=payload.get("approval_state", "NOT_APPROVED"),
    )
    model = route_job(job)
    params = {
        "prompt": job.prompt,
        "batch_size": 1,
        "resolution": payload.get("resolution", "720p"),
        "aspect_ratio": payload.get("aspect_ratio", "1:1"),
        "enhance_prompt": bool(payload.get("enhance_prompt", False)),
    }
    return job, model, params


class JobHandler(BaseHTTPRequestHandler):
    server_version = "IPGDigitalAssetEngine/0.2"

    def log_message(self, format, *args):
        print(f"JOB API: {format % args}", flush=True)

    def do_GET(self):
        if self.path == "/health":
            state = DurableState()
            return _json(self, 200, {
                "status": "ok",
                "readiness": "CONTROLLED",
                "generation_interface": True,
                "durable_state": state.configured,
                "max_job_cost_usd": _max_job_cost(),
            })
        if self.path.startswith("/jobs/"):
            if not _authorized(self):
                return _json(self, 401, {"error": "unauthorized"})
            job_id = self.path[len("/jobs/"):].strip()
            if not job_id:
                return _json(self, 400, {"error": "job_id_required"})
            try:
                row = DurableState().get(job_id)
                return _json(self, 200 if row else 404, {"job": row})
            except Exception as exc:
                return _json(self, 500, {"error": str(exc)})
        return _json(self, 404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/generate":
            return _json(self, 404, {"error": "not_found"})
        if not _authorized(self):
            return _json(self, 401, {"error": "unauthorized"})

        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
        except Exception:
            return _json(self, 400, {"error": "invalid_json"})

        job_id = str(payload.get("job_id") or "").strip()
        if not job_id:
            return _json(self, 400, {"error": "job_id_required"})

        state = DurableState()
        if not state.configured:
            return _json(self, 503, {"job_id": job_id, "status": "BLOCKED", "error": "durable_state_not_configured"})

        approval = str(payload.get("approval_state", "NOT_APPROVED"))
        dry_run = bool(payload.get("dry_run", True))

        try:
            job, model, params = _build_job(payload)
            claimed, existing = state.claim(job_id, job.objective, job.prompt, job.cost_ceiling_usd, approval)
            if not claimed:
                return _json(self, 409, {"job_id": job_id, "status": "DUPLICATE_BLOCKED", "existing": existing})

            provider = HiggsfieldProvider()
            if not provider.configured:
                state.update(job_id, status="FAILED", error="provider_not_configured")
                return _json(self, 503, {"job_id": job_id, "status": "FAILED", "error": "provider_not_configured"})

            estimate = provider.estimate(job, model.endpoint_id, params)
            if job.estimated_cost_usd is None:
                raise CostGateError("No estimate returned.")
            state.update(
                job_id,
                provider=model.provider,
                model=model.model_id,
                estimated_cost_usd=job.estimated_cost_usd,
                status="ESTIMATED",
            )

            preflight = {
                "job_id": job_id,
                "provider": model.provider,
                "model": model.model_id,
                "estimated_cost_usd": job.estimated_cost_usd,
                "cost_ceiling_usd": job.cost_ceiling_usd,
                "approval_state": approval,
                "status": "ESTIMATED",
            }

            if dry_run:
                state.update(job_id, status="DRY_RUN_COMPLETE")
                return _json(self, 200, {**preflight, "status": "DRY_RUN_COMPLETE"})

            if approval != "APPROVED":
                state.update(job_id, status="BLOCKED_NOT_APPROVED", error="explicit_approval_required")
                return _json(self, 409, {**preflight, "status": "BLOCKED_NOT_APPROVED", "error": "explicit_approval_required"})

            state.update(job_id, status="SUBMITTING")
            result = provider.submit(job, model.endpoint_id, params)
            state.update(
                job_id,
                request_id=job.request_id,
                provider_output_url=job.output_location,
                actual_cost_usd=job.actual_cost_usd,
                status=job.status,
            )

            bucket = None
            path = None
            if job.output_location:
                bucket, path = state.archive_output(job_id, job.output_location)
                state.update(job_id, asset_bucket=bucket, asset_path=path, status="ARCHIVED")

            response = {
                **preflight,
                "status": "ARCHIVED" if path else job.status,
                "request_id": job.request_id,
                "provider_output_location": job.output_location,
                "asset_bucket": bucket,
                "asset_path": path,
                "actual_cost_usd": job.actual_cost_usd,
                "estimate_credits": estimate.get("credits"),
                "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
            }
            print(
                f"GENERATION COMPLETE job_id={job_id} provider={model.provider} "
                f"model={model.model_id} estimate={job.estimated_cost_usd:.4f} "
                f"request_id={job.request_id} asset={bucket}/{path}",
                flush=True,
            )
            return _json(self, 200, response)

        except CostGateError as exc:
            try:
                state.update(job_id, status="BLOCKED", error=str(exc))
            except Exception:
                pass
            return _json(self, 409, {"job_id": job_id, "status": "BLOCKED", "error": str(exc)})
        except Exception as exc:
            try:
                state.update(job_id, status="FAILED", error=str(exc))
            except Exception:
                pass
            print(f"GENERATION FAILED job_id={job_id}: {exc}", flush=True)
            return _json(self, 500, {"job_id": job_id, "status": "FAILED", "error": str(exc)})


def run_job_server():
    port = int(os.getenv("PORT", "8080"))
    if not os.getenv("JOB_API_TOKEN"):
        raise RuntimeError("JOB_API_TOKEN is required before the job API can start.")
    if not DurableState().configured:
        raise RuntimeError("Durable state bridge is required before the job API can start.")
    server = ThreadingHTTPServer(("0.0.0.0", port), JobHandler)
    print(f"JOB API READY port={port} durable_state=true max_job_cost_usd={_max_job_cost():.4f}", flush=True)
    server.serve_forever()
