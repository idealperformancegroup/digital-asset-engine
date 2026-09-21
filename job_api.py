import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from providers.base import CreativeJob, CostGateError
from providers.higgsfield import HiggsfieldProvider
from providers.router import route_job


_JOBS = {}
_LOCK = threading.Lock()


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


def _build_test_job(payload):
    prompt = payload.get(
        "prompt",
        "A clean professional abstract gradient background for an advertising test.",
    )
    requested_ceiling = float(payload.get("cost_ceiling_usd", _max_job_cost()))
    ceiling = min(requested_ceiling, _max_job_cost())

    job = CreativeJob(
        objective=payload.get("objective", "bounded production image test"),
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
    server_version = "IPGDigitalAssetEngine/0.1"

    def log_message(self, format, *args):
        print(f"JOB API: {format % args}", flush=True)

    def do_GET(self):
        if self.path == "/health":
            return _json(self, 200, {
                "status": "ok",
                "readiness": "CONTROLLED",
                "generation_interface": True,
                "max_job_cost_usd": _max_job_cost(),
            })
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

        with _LOCK:
            existing = _JOBS.get(job_id)
            if existing is not None:
                return _json(self, 200, existing)
            _JOBS[job_id] = {"job_id": job_id, "status": "RECEIVED"}

        try:
            job, model, params = _build_test_job(payload)
            provider = HiggsfieldProvider()

            estimate = provider.estimate(job, model.endpoint_id, params)
            if job.estimated_cost_usd is None:
                raise CostGateError("No estimate returned.")

            preflight = {
                "job_id": job_id,
                "provider": model.provider,
                "model": model.model_id,
                "estimated_cost_usd": job.estimated_cost_usd,
                "cost_ceiling_usd": job.cost_ceiling_usd,
                "approval_state": job.approval_state,
                "status": "ESTIMATED",
            }

            if payload.get("dry_run", False):
                with _LOCK:
                    _JOBS[job_id] = preflight
                return _json(self, 200, preflight)

            result = provider.submit(job, model.endpoint_id, params)
            response = {
                **preflight,
                "status": job.status,
                "request_id": job.request_id,
                "output_location": job.output_location,
                "actual_cost_usd": job.actual_cost_usd,
                "estimate_credits": estimate.get("credits"),
                "result_keys": sorted(result.keys()) if isinstance(result, dict) else [],
            }
            with _LOCK:
                _JOBS[job_id] = response
            print(
                f"GENERATION COMPLETE job_id={job_id} provider={model.provider} "
                f"model={model.model_id} estimate={job.estimated_cost_usd:.4f} "
                f"request_id={job.request_id} output={job.output_location}",
                flush=True,
            )
            return _json(self, 200, response)

        except CostGateError as exc:
            response = {"job_id": job_id, "status": "BLOCKED", "error": str(exc)}
            with _LOCK:
                _JOBS[job_id] = response
            print(f"GENERATION BLOCKED job_id={job_id}: {exc}", flush=True)
            return _json(self, 409, response)
        except Exception as exc:
            response = {"job_id": job_id, "status": "FAILED", "error": str(exc)}
            with _LOCK:
                _JOBS[job_id] = response
            print(f"GENERATION FAILED job_id={job_id}: {exc}", flush=True)
            return _json(self, 500, response)


def run_job_server():
    port = int(os.getenv("PORT", "8080"))
    if not os.getenv("JOB_API_TOKEN"):
        raise RuntimeError("JOB_API_TOKEN is required before the job API can start.")
    server = ThreadingHTTPServer(("0.0.0.0", port), JobHandler)
    print(
        f"JOB API READY port={port} max_job_cost_usd={_max_job_cost():.4f}",
        flush=True,
    )
    server.serve_forever()
