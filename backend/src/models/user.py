from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.config.database import Base


class User(Base):
    __tablename__ = 'users'
    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(150), unique=True)
    name: Mapped[str] = mapped_column(String(80))
    password: Mapped[str] = mapped_column(String(300))
    # 全局 role 已取消：账号没有全局职责，职责逐馆授予，见 BranchMembership。
    memberships: Mapped[list['BranchMembership']] = relationship(  # noqa: F821
        back_populates='user', cascade='all, delete-orphan', lazy='selectin')
