from sqlalchemy import String, ForeignKey, UniqueConstraint, Double
from sqlalchemy.orm import Mapped, mapped_column, relationship
from src.config.database import Base


class Branch(Base):
    """场馆（分馆）。数据批次、分析任务、分发计划全部按馆隔离。"""
    __tablename__ = 'branches'
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(120), unique=True)
    created_at: Mapped[float] = mapped_column(Double)
    memberships: Mapped[list['BranchMembership']] = relationship(
        back_populates='branch', cascade='all, delete-orphan', lazy='selectin')


class BranchMembership(Base):
    """账号在某一馆内的资格。同一账号在不同馆可拥有不同职责；
    撤销某馆资格（删除本行）后，旧登录凭据立即失去该馆访问权，
    因为每次请求都按当前馆实时查询资格，不依赖令牌内缓存的角色。"""
    __tablename__ = 'branch_memberships'
    __table_args__ = (UniqueConstraint('user_id', 'branch_id', name='uq_membership_user_branch'),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey('users.id'))
    branch_id: Mapped[int] = mapped_column(ForeignKey('branches.id'))
    role: Mapped[str] = mapped_column(String(20))  # owner / analyst / viewer
    user: Mapped['User'] = relationship(back_populates='memberships')  # noqa: F821
    branch: Mapped['Branch'] = relationship(back_populates='memberships')
