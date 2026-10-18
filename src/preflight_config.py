"""Central provisional preflight policy; no filesystem effects on import."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PreflightPolicy:
    """Research controls, not calibrated operational thresholds."""

    max_event_age_days: int = 30
    max_assessment_age_days: int = 30


PREFLIGHT_POLICY = PreflightPolicy()
