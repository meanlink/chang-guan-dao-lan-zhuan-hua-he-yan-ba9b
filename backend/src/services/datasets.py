import math
import time

from fastapi import HTTPException
from sqlalchemy import select

from src.models import Dataset
from src.services.business import metadata
from src.utils.serialization import checksum


def create(db, data, branch_id: int):
    name = data.name.strip()
    if len(name) < 2:
        raise HTTPException(422, '批次名称去除空格后至少需要两个字符')
    # 唯一性按馆判定：同名批次允许在不同馆独立建立。
    if db.scalar(select(Dataset).where(
            Dataset.branch_id == branch_id, Dataset.name == name)):
        raise HTTPException(409, '该数据批次名在当前馆已存在，请修改名称')
    for index, row in enumerate(data.records):
        for c in metadata()['columns']:
            value = row.get(c['key'])
            if value is None or value == '':
                raise HTTPException(422, f'第 {index+1} 行缺少字段 {c["label"]}')
            if c['type'] == 'number':
                try:
                    if isinstance(value, bool) or not math.isfinite(float(value)):
                        raise ValueError()
                    row[c['key']] = float(value)
                except (TypeError, ValueError, OverflowError):
                    raise HTTPException(422, f'第 {index+1} 行 {c["label"]} 必须为有限数值')
    d = Dataset(branch_id=branch_id, name=name, source=data.source,
                records=data.records, checksum=checksum(data.records), created_at=time.time())
    db.add(d)
    db.flush()
    return d
