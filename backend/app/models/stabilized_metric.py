from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import PortableJSON


class StabilizedMetric(Base):
    __tablename__ = "stabilized_metrics"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    url_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("urls.url_id", ondelete="CASCADE"), nullable=False, index=True
    )
    window_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    window_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    run_count: Mapped[int] = mapped_column(Integer, nullable=False)

    median_metrics: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)
    variability_metrics: Mapped[dict] = mapped_column(PortableJSON, nullable=False, default=dict)

    flagged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    url: Mapped["Url"] = relationship(back_populates="stabilized_metrics")
