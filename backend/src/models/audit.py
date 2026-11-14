from sqlalchemy import String, Double, JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from src.config.database import Base


class Audit(Base):
    __tablename__ = 'audits'
    id: Mapped[int] = mapped_column(primary_key=True)
    # 审计按馆隔离展示；系统动作（迁移、worker）可留空。
    branch_id: Mapped[int | None] = mapped_column(ForeignKey('branches.id'), nullable=True, index=True)
    actor: Mapped[str] = mapped_column(String(150))
    action: Mapped[str] = mapped_column(String(80))
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    at: Mapped[float] = mapped_column(Double)
