from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import PortableJSON


class LlmRecommendation(Base):
    __tablename__ = "llm_recommendations"

    recommendation_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("urls.url_id", ondelete="CASCADE"), nullable=False, index=True
    )
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )

    # List of {root_cause, summary, evidence[], impact, ease_of_fix,
    # confidence, suggested_fix, affected_audits[], priority} - see
    # app/schemas/recommendation.py for the validated shape.
    root_cause_groups: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)

    # Overall best (lowest/most urgent) priority rank across the group, e.g. "P1".
    priority_rank: Mapped[str] = mapped_column(String(8), nullable=False, default="P3")

    source_run_ids: Mapped[list] = mapped_column(PortableJSON, nullable=False, default=list)
    model_name: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)

    validation_status: Mapped[str] = mapped_column(String(16), nullable=False, default="needs_review")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    url: Mapped["Url"] = relationship(back_populates="recommendations")
