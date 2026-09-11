"""
Import every model here so that a single `from app.models import *` (or just
importing this package) registers all tables on Base.metadata - this is what
Alembic's env.py and the test fixtures rely on.
"""
from app.models.site import Site  # noqa: F401
from app.models.url import Url  # noqa: F401
from app.models.psi_run import PsiRun  # noqa: F401
from app.models.stabilized_metric import StabilizedMetric  # noqa: F401
from app.models.llm_recommendation import LlmRecommendation  # noqa: F401

__all__ = ["Site", "Url", "PsiRun", "StabilizedMetric", "LlmRecommendation"]
