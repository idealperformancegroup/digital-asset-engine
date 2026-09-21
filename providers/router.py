from .base import CreativeJob
from .registry import MODEL_REGISTRY, ModelSpec


class RoutingError(RuntimeError):
    pass


def route_job(job: CreativeJob) -> ModelSpec:
    candidates = [
        spec for spec in MODEL_REGISTRY.values()
        if spec.asset_type == job.asset_type
    ]

    if job.selected_provider:
        candidates = [
            spec for spec in candidates
            if spec.provider == job.selected_provider
        ]

    if job.selected_model:
        candidates = [
            spec for spec in candidates
            if spec.model_id == job.selected_model
        ]

    if not candidates:
        raise RoutingError(
            f"No registered model satisfies asset_type={job.asset_type!r}, "
            f"provider={job.selected_provider!r}, model={job.selected_model!r}."
        )

    # Phase 1 policy: explicit, deterministic routing. Add quality/cost scoring
    # only after multiple providers are connected and benchmarked.
    return candidates[0]
