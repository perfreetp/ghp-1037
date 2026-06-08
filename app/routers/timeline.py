from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import extract
from app.database import get_db
from app.models import Product, TimelineEvent, VersionNode
from app.schemas import TimelineEventCreate, TimelineEventOut, VersionNodeCreate, VersionNodeOut
from app.services.update_feed import create_update_event

router = APIRouter(prefix="/timeline", tags=["时间线"])


@router.post("/products/{product_id}/events", response_model=TimelineEventOut, summary="记录时间线事件")
def create_event(product_id: int, data: TimelineEventCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    event = TimelineEvent(product_id=product_id, **data.model_dump())
    db.add(event)
    db.flush()
    create_update_event(
        product_id, "timeline",
        f"新增时间线事件 [{data.event_type}]: {data.description}",
        db,
    )
    db.commit()
    db.refresh(event)
    return event


@router.get("/products/{product_id}/events", response_model=List[TimelineEventOut], summary="获取产品时间线")
def list_events(product_id: int, db: Session = Depends(get_db)):
    return (
        db.query(TimelineEvent)
        .filter(TimelineEvent.product_id == product_id)
        .order_by(TimelineEvent.event_date)
        .all()
    )


@router.delete("/events/{event_id}", summary="删除时间线事件")
def delete_event(event_id: int, db: Session = Depends(get_db)):
    event = db.query(TimelineEvent).filter(TimelineEvent.id == event_id).first()
    if not event:
        raise HTTPException(status_code=404, detail="事件不存在")
    create_update_event(
        event.product_id, "timeline",
        f"删除时间线事件 [{event.event_type}]: {event.description}",
        db,
    )
    db.delete(event)
    db.commit()
    return {"detail": "已删除"}


@router.post("/products/{product_id}/versions", response_model=VersionNodeOut, summary="标注版本节点")
def create_version(product_id: int, data: VersionNodeCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    version = VersionNode(product_id=product_id, **data.model_dump())
    db.add(version)
    db.flush()
    create_update_event(
        product_id, "version",
        f"新增版本节点 [{data.version_name}]: {data.changes_summary or data.description}",
        db,
    )
    db.commit()
    db.refresh(version)
    return version


@router.get("/products/{product_id}/versions", response_model=List[VersionNodeOut], summary="获取版本节点列表")
def list_versions(product_id: int, db: Session = Depends(get_db)):
    return (
        db.query(VersionNode)
        .filter(VersionNode.product_id == product_id)
        .order_by(VersionNode.release_date)
        .all()
    )


@router.put("/versions/{version_id}", response_model=VersionNodeOut, summary="更新版本节点")
def update_version(version_id: int, data: VersionNodeCreate, db: Session = Depends(get_db)):
    version = db.query(VersionNode).filter(VersionNode.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本节点不存在")
    for key, value in data.model_dump().items():
        setattr(version, key, value)
    db.flush()
    create_update_event(
        version.product_id, "version",
        f"更新版本节点 [{data.version_name}]: {data.changes_summary or data.description}",
        db,
    )
    db.commit()
    db.refresh(version)
    return version


@router.delete("/versions/{version_id}", summary="删除版本节点")
def delete_version(version_id: int, db: Session = Depends(get_db)):
    version = db.query(VersionNode).filter(VersionNode.id == version_id).first()
    if not version:
        raise HTTPException(status_code=404, detail="版本节点不存在")
    create_update_event(
        version.product_id, "version",
        f"删除版本节点 [{version.version_name}]",
        db,
    )
    db.delete(version)
    db.commit()
    return {"detail": "已删除"}


@router.get("/filter/by-year", response_model=List[TimelineEventOut], summary="按年代筛选事件")
def filter_by_year(
    year: int = Query(..., description="年份"),
    event_type: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(TimelineEvent).filter(extract("year", TimelineEvent.event_date) == year)
    if event_type:
        q = q.filter(TimelineEvent.event_type == event_type)
    return q.order_by(TimelineEvent.event_date).offset(skip).limit(limit).all()
