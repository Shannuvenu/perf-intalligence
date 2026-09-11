from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import PortableJSON


class PsiRun(Base):
    __tablename__ = "psi_runs"

    run_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("urls.url_id", ondelete="CASCADE"), nullable=False, index=True
    )
    run_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False, index=True
    )
    strategy: Mapped[str] = mapped_column(String(16), nullable=False, default="mobile")

    # Path/key to the full raw PSI JSON on disk (or S3 later) - never the raw
    # blob itself in a relational column.
    raw_storage_key: Mapped[str | None] = mapped_column(String(1024), nullable=True)

    # Normalized, queryable summaries extracted from the raw response.
    category_scores: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    core_web_vitals: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    # Normalized audit evidence (unused JS, images, third-party, a11y, etc.)
    # kept alongside the summary so evidence extraction doesn't need to
    # re-read the raw file for every stabilization/recommendation pass.
    normalized_audits: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    run_status: Mapped[str] = mapped_column(String(16), nullable=False, default="success")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    url: Mapped["Url"] = relationship(back_populates="runs")
