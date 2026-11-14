from fastapi import APIRouter, Depends
from sqlalchemy import select, func

from src.config.database import get_db
from src.middlewares.auth import current_context
from src.models import Dataset, Job, Report, Audit
from src.services.business import metadata

router = APIRouter()


@router.get('/meta')
def meta():
    return metadata()


@router.get('/overview')
def overview(db=Depends(get_db), ctx=Depends(current_context)):
    bid = ctx.branch_id
    branch_datasets = db.scalars(select(Dataset).where(Dataset.branch_id == bid)).all()
    return {
        'branch_id': bid,
        'datasets': db.scalar(select(func.count()).select_from(Dataset)
                              .where(Dataset.branch_id == bid)),
        'records': sum(len(d.records) for d in branch_datasets),
        'jobs': db.scalar(select(func.count()).select_from(Job)
                          .where(Job.branch_id == bid)),
        'approved': db.scalar(select(func.count()).select_from(Job)
                              .where(Job.branch_id == bid, Job.approved == True)),  # noqa: E712
        'reports': db.scalar(select(func.count()).select_from(Report)
                             .where(Report.branch_id == bid)),
    }


@router.get('/audits')
def audits(db=Depends(get_db), ctx=Depends(current_context)):
    rows = db.scalars(
        select(Audit).where(Audit.branch_id == ctx.branch_id)
        .order_by(Audit.id.desc()).limit(50))
    return [{'id': a.id, 'actor': a.actor, 'action': a.action,
             'detail': a.detail, 'at': a.at} for a in rows]
