from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from src.config.database import get_db
from src.models import Dataset
from src.schemas.dataset import DatasetInput
from src.middlewares.auth import current_context, can_write
from src.services import datasets
from src.services.audit import record
from src.utils.serialization import dataset_dict

router = APIRouter(prefix='/datasets')


def _get_scoped(db, dataset_id: int, branch_id: int):
    d = db.get(Dataset, dataset_id)
    # 外馆资源对当前馆不可见：统一 404，避免泄露外馆是否存在该 id。
    if not d or d.branch_id != branch_id:
        raise HTTPException(404, '数据批次不存在')
    return d


@router.get('')
def listing(db=Depends(get_db), ctx=Depends(current_context)):
    rows = db.scalars(
        select(Dataset).where(Dataset.branch_id == ctx.branch_id)
        .order_by(Dataset.id.desc()))
    return [dataset_dict(d) for d in rows]


@router.post('', status_code=201)
def create(data: DatasetInput, db=Depends(get_db), ctx=Depends(can_write)):
    d = datasets.create(db, data, ctx.branch_id)
    record(db, ctx.user.email, 'dataset.create',
           {'id': d.id, 'rows': len(d.records)}, branch_id=ctx.branch_id)
    db.commit()
    return dataset_dict(d)


@router.get('/{id}')
def detail(id: int, db=Depends(get_db), ctx=Depends(current_context)):
    d = _get_scoped(db, id, ctx.branch_id)
    return {**dataset_dict(d), 'records': d.records}
