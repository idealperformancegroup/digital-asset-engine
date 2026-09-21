from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ModelSpec:
    provider: str
    model_id: str
    endpoint_id: str
    asset_type: str
    capabilities: tuple[str, ...]
    status: str = "PRIMARY"
    notes: str = ""


MODEL_REGISTRY: Dict[str, ModelSpec] = {
    "higgsfield:soul-2-standard": ModelSpec(
        provider="higgsfield",
        model_id="soul-2-standard",
        endpoint_id="higgsfield-ai/soul/v2/standard",
        asset_type="image",
        capabilities=("text-to-image", "portrait", "ad-creative"),
        status="PRIMARY",
        notes="Verified Higgsfield REST endpoint; use estimate endpoint before submission.",
    ),
}


def get_model(model_key: str) -> Optional[ModelSpec]:
    return MODEL_REGISTRY.get(model_key)


def list_models(asset_type: Optional[str] = None):
    values = list(MODEL_REGISTRY.values())
    if asset_type:
        values = [m for m in values if m.asset_type == asset_type]
    return values
