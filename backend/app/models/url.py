from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Url(Base):
    __tablename__ = "urls"

    url_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    site_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("sites.site_id", ondelete="CASCADE"), nullable=False, index=True
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    url_category: Mapped[str] = mapped_column(String(64), nullable=False, default="other")
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )

    site: Mapped["Site"] = relationship(back_populates="urls")
    runs: Mapped[list["PsiRun"]] = relationship(back_populates="url", cascade="all, delete-orphan")
    stabilized_metrics: Mapped[list["StabilizedMetric"]] = relationship(
        back_populates="url", cascade="all, delete-orphan"
    )
    recommendations: Mapped[list["LlmRecommendation"]] = relationship(
        back_populates="url", cascade="all, delete-orphan"
    )
