import os

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select

from src.config.database import get_db
from src.config.settings import ARTIFACT_DIR
from src.models import Report, Delivery
from src.schemas.report import ReportInput
from src.middlewares.auth import current_context, owner_only
from src.services import reports
from src.services.audit import record
from src.utils.serialization import report_dict, delivery_dict

router = APIRouter()


def _get_report(db, report_id: int, branch_id: int):
    r = db.get(Report, report_id)
    if not r or r.branch_id != branch_id:
        raise HTTPException(404, '分发计划不存在')
    return r


@router.get('/reports')
def listing(db=Depends(get_db), ctx=Depends(current_context)):
    rows = db.scalars(
        select(Report).where(Report.branch_id == ctx.branch_id)
        .order_by(Report.id.desc()))
    return [report_dict(r) for r in rows]


@router.post('/reports', status_code=201)
def create(data: ReportInput, db=Depends(get_db), ctx=Depends(owner_only)):
    r = reports.create(db, data, ctx.branch_id)
    record(db, ctx.user.email, 'report.schedule',
           {'id': r.id, 'destination': r.destination}, branch_id=ctx.branch_id)
    db.commit()
    return report_dict(r)


@router.post('/reports/{id}/toggle')
def toggle(id: int, db=Depends(get_db), ctx=Depends(owner_only)):
    r = _get_report(db, id, ctx.branch_id)
    r.enabled = not r.enabled
    record(db, ctx.user.email, 'report.toggle',
           {'id': id, 'enabled': r.enabled}, branch_id=ctx.branch_id)
    db.commit()
    return report_dict(r)


@router.get('/deliveries')
def deliveries(db=Depends(get_db), ctx=Depends(current_context)):
    rows = db.scalars(
        select(Delivery).where(Delivery.branch_id == ctx.branch_id)
        .order_by(Delivery.id.desc()).limit(100))
    return [delivery_dict(d) for d in rows]


@router.get('/deliveries/{id}/download')
def download(id: int, format: str = 'csv', db=Depends(get_db),
             ctx=Depends(current_context)):
    d = db.get(Delivery, id)
    # 归档同样按馆隔离：跨馆下载请求被拒绝（404 不暴露存在性）。
    if not d or d.branch_id != ctx.branch_id:
        raise HTTPException(404, '归档不存在')
    if format not in ('csv', 'json'):
        raise HTTPException(422, '支持 CSV 或 JSON')
    filename = d.filename + ('.json' if format == 'json' else '')
    p = os.path.join(ARTIFACT_DIR, filename)
    if not os.path.exists(p):
        raise HTTPException(404, '归档文件不存在，请重新安排分发')
    return FileResponse(p, filename=filename,
                        media_type='application/json' if format == 'json'
                        else 'text/csv; charset=utf-8')
