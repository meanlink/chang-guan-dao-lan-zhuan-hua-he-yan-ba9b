"""按馆隔离的认证与授权。

请求上下文：登录后前端在每个请求携带 X-Branch-Id 声明当前工作馆。
服务端不相信令牌里缓存的角色，而是用 user_id + branch_id 实时查询
branch_memberships：
- 不是任何馆成员 / 馆不存在      -> 403（越权访问被拒绝）
- 馆资格被撤销（membership 删除）-> 旧登录凭据立即失去该馆访问权
- 馆存在但本账号无资格          -> 403，前端引导切回有权限的馆
"""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import select

from src.config.database import get_db
from src.models import User, Branch, BranchMembership
from src.utils.security import decode_token

bearer = HTTPBearer(auto_error=False)


@dataclass
class BranchContext:
    user: User
    branch: Branch
    role: str  # owner / analyst / viewer，仅代表“当前馆”内的职责

    @property
    def branch_id(self) -> int:
        return self.branch.id


def current_user(
    token: HTTPAuthorizationCredentials | None = Depends(bearer),
    db=Depends(get_db),
):
    try:
        user = db.get(User, decode_token(token.credentials))
        if user is None:
            raise ValueError('missing user')
        return user
    except Exception:
        raise HTTPException(401, '登录已过期，请重新登录')


def current_context(
    x_branch_id: int | None = Header(default=None, alias='X-Branch-Id'),
    user: User = Depends(current_user),
    db=Depends(get_db),
):
    if x_branch_id is None:
        raise HTTPException(400, '缺少当前馆标识，请重新选择工作馆')
    branch = db.get(Branch, x_branch_id)
    if branch is None:
        raise HTTPException(404, '场馆不存在或已停用')
    membership = db.scalar(select(BranchMembership).where(
        BranchMembership.user_id == user.id,
        BranchMembership.branch_id == branch.id))
    if membership is None:
        # 撤销馆内资格后，即使拿着仍未过期的旧令牌也会在此被拒。
        raise HTTPException(403, '无权访问该馆或馆内资格已被撤销')
    return BranchContext(user=user, branch=branch, role=membership.role)


def can_write(ctx: BranchContext = Depends(current_context)):
    if ctx.role not in ('owner', 'analyst'):
        raise HTTPException(403, '当前馆内为只读职责，无法写入')
    return ctx


def owner_only(ctx: BranchContext = Depends(current_context)):
    if ctx.role != 'owner':
        raise HTTPException(403, '当前馆内需要负责人职责')
    return ctx
