from sqlalchemy import select

from src.models import Branch, BranchMembership


def memberships_for(db, user_id: int):
    """账号在各馆的资格，按馆 id 排序；只返回仍有效的资格。"""
    rows = db.execute(
        select(BranchMembership, Branch)
        .join(Branch, Branch.id == BranchMembership.branch_id)
        .where(BranchMembership.user_id == user_id)
        .order_by(Branch.id)).all()
    return [
        {'branch_id': branch.id, 'code': branch.code, 'name': branch.name, 'role': m.role}
        for m, branch in rows
    ]


def branch_dict(branch: Branch):
    return {'id': branch.id, 'code': branch.code, 'name': branch.name}
