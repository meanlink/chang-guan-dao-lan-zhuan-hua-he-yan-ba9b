from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select

from src.config.database import get_db
from src.models import User, Branch, BranchMembership
from src.utils.security import verify_password, token_for
from src.middlewares.auth import current_user
from src.services.audit import record
from src.services.branches import memberships_for

router = APIRouter(prefix='/auth')


class Login(BaseModel):
    email: str = Field(max_length=150)
    password: str = Field(max_length=200)


class SwitchBranch(BaseModel):
    branch_id: int


@router.post('/login')
def login(data: Login, db=Depends(get_db)):
    u = db.scalar(select(User).where(User.email == data.email))
    if not u or not verify_password(data.password, u.password):
        raise HTTPException(401, '账号或密码不正确')
    memberships = memberships_for(db, u.id)
    if not memberships:
        # 账号存在但没有任何馆资格：不允许进入系统
        raise HTTPException(403, '账号尚未获得任何场馆资格，请联系负责人')
    record(db, u.email, 'auth.login', {'branches': [m['branch_id'] for m in memberships]})
    db.commit()
    # 令牌只证明身份（user_id）；馆与职责每次请求按 membership 实时判定，
    # 因此切馆无需换发令牌，撤销资格也能即时生效。
    return {
        'access_token': token_for(u),
        'user': {'name': u.name, 'email': u.email},
        'memberships': memberships,
    }


@router.get('/me')
def me(u: User = Depends(current_user), db=Depends(get_db)):
    return {'name': u.name, 'email': u.email, 'memberships': memberships_for(db, u.id)}


@router.get('/branches')
def my_branches(u: User = Depends(current_user), db=Depends(get_db)):
    """登录后可切换的馆清单（仅含本人仍有资格的馆）。"""
    return memberships_for(db, u.id)


@router.post('/switch-branch')
def switch_branch(data: SwitchBranch, u: User = Depends(current_user), db=Depends(get_db)):
    """切馆：服务端复核目标馆资格，返回当前馆与职责，供页面核对。"""
    branch = db.get(Branch, data.branch_id)
    if branch is None:
        raise HTTPException(404, '场馆不存在')
    membership = db.scalar(select(BranchMembership).where(
        BranchMembership.user_id == u.id, BranchMembership.branch_id == branch.id))
    if membership is None:
        raise HTTPException(403, '无权切换到该馆：馆内资格缺失或已撤销')
    record(db, u.email, 'auth.switch_branch', {'branch_id': branch.id, 'role': membership.role})
    db.commit()
    return {'branch_id': branch.id, 'code': branch.code, 'name': branch.name,
            'role': membership.role}
