from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from src.config.database import get_db
from src.models import Job
from src.schemas.job import JobInput
from src.middlewares.auth import current_context, can_write, owner_only
from src.services import jobs
from src.services.audit import record
from src.utils.serialization import job_dict

router = APIRouter(prefix='/jobs')


def _get_scoped(db, job_id: int, branch_id: int):
    j = db.get(Job, job_id)
    if not j or j.branch_id != branch_id:
        raise HTTPException(404, '分析任务不存在')
    return j


@router.get('')
def listing(db=Depends(get_db), ctx=Depends(current_context)):
    rows = db.scalars(
        select(Job).where(Job.branch_id == ctx.branch_id)
        .order_by(Job.id.desc()).limit(100))
    return [job_dict(j) for j in rows]


@router.post('', status_code=201)
def create(data: JobInput, db=Depends(get_db), ctx=Depends(can_write)):
    j = jobs.create(db, data, ctx)
    record(db, ctx.user.email, 'job.create',
           {'id': j.id, 'params': j.params}, branch_id=ctx.branch_id)
    db.commit()
    jobs.enqueue(j.id)
    return job_dict(j)


@router.get('/{id}')
def detail(id: int, db=Depends(get_db), ctx=Depends(current_context)):
    return job_dict(_get_scoped(db, id, ctx.branch_id))


@router.post('/{id}/approve')
def approve(id: int, db=Depends(get_db), ctx=Depends(owner_only)):
    j = _get_scoped(db, id, ctx.branch_id)
    if j.status != 'completed':
        raise HTTPException(409, '仅已完成结果可以批准')
    j.approved = True
    record(db, ctx.user.email, 'job.approve', {'id': id}, branch_id=ctx.branch_id)
    db.commit()
    return job_dict(j)
