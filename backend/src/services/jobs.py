import time

from fastapi import HTTPException
from redis import Redis

from src.config.settings import REDIS_URL
from src.models import Dataset, Job
from src.services.business import metadata


def create(db, data, ctx):
    dataset = db.get(Dataset, data.dataset_id)
    if not dataset:
        raise HTTPException(404, '数据批次不存在')
    # 跨馆引用必须拒绝：只能基于当前馆的批次发起分析。
    if dataset.branch_id != ctx.branch_id:
        raise HTTPException(403, '不能引用其他馆的数据批次')
    allowed = {p['key']: p for p in metadata().get('parameters', [])}
    if set(data.params) - set(allowed):
        raise HTTPException(422, '包含未知分析参数')
    params = {k: p['default'] for k, p in allowed.items()}
    params.update(data.params)
    for key, p in allowed.items():
        v = params[key]
        if p['type'] == 'number':
            try:
                v = float(v)
                if not (p.get('min', -1e9) <= v <= p.get('max', 1e9)):
                    raise ValueError()
                params[key] = v
            except (ValueError, TypeError):
                raise HTTPException(422, f'{p["label"]} 超出范围或非数值')
        elif str(v) not in [str(o['value']) for o in p.get('options', [])]:
            raise HTTPException(422, f'{p["label"]} 不是有效选项')
    # 归属馆在此固化；之后账号切馆不影响该任务，worker 也按 branch_id 识别。
    j = Job(branch_id=ctx.branch_id, name=data.name, dataset_id=dataset.id, params=params,
            created_by=ctx.user.id, created_at=time.time(), status='queued')
    db.add(j)
    db.flush()
    return j


def enqueue(job_id):
    try:
        r = Redis.from_url(REDIS_URL)
        r.rpush('analysis:queue', job_id)
        r.close()
    except Exception:
        pass  # SQL queued status is the durable fallback
