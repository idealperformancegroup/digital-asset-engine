from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass
class CreativeJob:
    objective: str
    asset_type: str
    prompt: str
    references: list[str] = field(default_factory=list)
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[int] = None
    quality: Optional[str] = None
    cost_ceiling_usd: Optional[float] = None
    selected_provider: Optional[str] = None
    selected_model: Optional[str] = None
    estimated_cost_usd: Optional[float] = None
    approval_state: str = "NOT_APPROVED"
    request_id: Optional[str] = None
    actual_cost_usd: Optional[float] = None
    output_location: Optional[str] = None
    status: str = "DRAFT"
    metadata: Dict[str, Any] = field(default_factory=dict)


class CostGateError(RuntimeError):
    pass


def enforce_cost_gate(job: CreativeJob) -> None:
    if job.cost_ceiling_usd is None:
        raise CostGateError("No cost ceiling is set.")
    if job.estimated_cost_usd is None:
        raise CostGateError("No estimated cost is available.")
    if job.estimated_cost_usd > job.cost_ceiling_usd:
        raise CostGateError(
            f"Estimated cost {job.estimated_cost_usd:.4f} exceeds ceiling "
            f"{job.cost_ceiling_usd:.4f}."
        )
    if job.approval_state != "APPROVED":
        raise CostGateError("Paid generation is not explicitly approved.")
