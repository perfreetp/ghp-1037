from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, Subscription, UpdateEvent, UpdateReadStatus
from app.schemas import SubscriptionCreate, SubscriptionOut, UpdateEventOut

router = APIRouter(prefix="/subscription", tags=["订阅"])


def _create_update_event(product_id: int, event_type: str, description: str, db: Session):
    evt = UpdateEvent(product_id=product_id, event_type=event_type, description=description)
    db.add(evt)
    db.flush()
    subs = db.query(Subscription).filter(Subscription.product_id == product_id).all()
    for sub in subs:
        rs = UpdateReadStatus(
            update_event_id=evt.id,
            subscriber_email=sub.subscriber_email,
            is_read=False,
        )
        db.add(rs)
    db.commit()
    db.refresh(evt)
    return evt


@router.post("/products/{product_id}/subscribe", response_model=SubscriptionOut, summary="订阅更新")
def subscribe(product_id: int, data: SubscriptionCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    existing = db.query(Subscription).filter(
        Subscription.product_id == product_id,
        Subscription.subscriber_email == data.subscriber_email,
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="已订阅该产品")
    sub = Subscription(product_id=product_id, subscriber_email=data.subscriber_email)
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


@router.delete("/products/{product_id}/subscribe", summary="取消订阅")
def unsubscribe(product_id: int, email: str, db: Session = Depends(get_db)):
    sub = db.query(Subscription).filter(
        Subscription.product_id == product_id,
        Subscription.subscriber_email == email,
    ).first()
    if not sub:
        raise HTTPException(status_code=404, detail="订阅记录不存在")
    db.delete(sub)
    db.commit()
    return {"detail": "已取消订阅"}


@router.get("/subscribers/{email}", response_model=List[SubscriptionOut], summary="获取用户订阅列表")
def list_subscriptions_by_email(email: str, db: Session = Depends(get_db)):
    return db.query(Subscription).filter(Subscription.subscriber_email == email).all()


@router.get("/products/{product_id}/subscribers", response_model=List[SubscriptionOut], summary="获取产品订阅者列表")
def list_subscribers(product_id: int, db: Session = Depends(get_db)):
    return db.query(Subscription).filter(Subscription.product_id == product_id).all()


@router.post("/products/{product_id}/update-events", response_model=UpdateEventOut, summary="手动触发更新事件")
def trigger_update_event(
    product_id: int,
    event_type: str = Query(..., description="事件类型: timeline/version/material/price/appeal"),
    description: str = Query("", description="事件描述"),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    evt = _create_update_event(product_id, event_type, description, db)
    return evt


@router.get("/feed/{email}", response_model=List[UpdateEventOut], summary="获取订阅更新流")
def get_update_feed(
    email: str,
    only_unread: bool = Query(False, description="仅未读"),
    product_id: Optional[int] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=100),
    db: Session = Depends(get_db),
):
    sub_product_ids = [r[0] for r in db.query(Subscription.product_id).filter(
        Subscription.subscriber_email == email
    ).all()]
    if not sub_product_ids:
        return []

    q = db.query(UpdateEvent).filter(UpdateEvent.product_id.in_(sub_product_ids))
    if product_id:
        q = q.filter(UpdateEvent.product_id == product_id)

    events = q.order_by(UpdateEvent.created_at.desc()).offset(skip).limit(limit).all()

    result = []
    for evt in events:
        rs = db.query(UpdateReadStatus).filter(
            UpdateReadStatus.update_event_id == evt.id,
            UpdateReadStatus.subscriber_email == email,
        ).first()
        is_read = rs.is_read if rs else True
        if only_unread and is_read:
            continue
        out = UpdateEventOut(
            id=evt.id,
            product_id=evt.product_id,
            event_type=evt.event_type,
            description=evt.description,
            created_at=evt.created_at,
            is_read=is_read,
        )
        result.append(out)
    return result


@router.patch("/feed/{email}/read/{event_id}", summary="标记更新事件为已读")
def mark_event_read(email: str, event_id: int, db: Session = Depends(get_db)):
    rs = db.query(UpdateReadStatus).filter(
        UpdateReadStatus.update_event_id == event_id,
        UpdateReadStatus.subscriber_email == email,
    ).first()
    if not rs:
        raise HTTPException(status_code=404, detail="更新记录不存在或未订阅")
    rs.is_read = True
    rs.read_at = datetime.utcnow()
    db.commit()
    return {"detail": "已标记为已读"}


@router.patch("/feed/{email}/read-all", summary="全部标记为已读")
def mark_all_read(email: str, product_id: Optional[int] = None, db: Session = Depends(get_db)):
    sub_product_ids = [r[0] for r in db.query(Subscription.product_id).filter(
        Subscription.subscriber_email == email
    ).all()]
    if not sub_product_ids:
        return {"detail": "无订阅", "count": 0}

    q = db.query(UpdateReadStatus).filter(
        UpdateReadStatus.subscriber_email == email,
        UpdateReadStatus.is_read == False,
    )
    if product_id:
        evt_ids = [r[0] for r in db.query(UpdateEvent.id).filter(
            UpdateEvent.product_id == product_id
        ).all()]
        q = q.filter(UpdateReadStatus.update_event_id.in_(evt_ids))

    now = datetime.utcnow()
    count = 0
    for rs in q.all():
        rs.is_read = True
        rs.read_at = now
        count += 1
    db.commit()
    return {"detail": f"已标记{count}条为已读", "count": count}


@router.get("/feed/{email}/unread-count", summary="未读更新数量")
def get_unread_count(email: str, db: Session = Depends(get_db)):
    sub_product_ids = [r[0] for r in db.query(Subscription.product_id).filter(
        Subscription.subscriber_email == email
    ).all()]
    if not sub_product_ids:
        return {"total": 0, "by_product": {}}

    unread = db.query(UpdateReadStatus).filter(
        UpdateReadStatus.subscriber_email == email,
        UpdateReadStatus.is_read == False,
    ).all()

    evt_ids = [rs.update_event_id for rs in unread]
    by_product = {}
    if evt_ids:
        evts = db.query(UpdateEvent).filter(UpdateEvent.id.in_(evt_ids)).all()
        for e in evts:
            by_product[e.product_id] = by_product.get(e.product_id, 0) + 1

    return {"total": len(unread), "by_product": by_product}
