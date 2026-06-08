from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, Subscription
from app.schemas import SubscriptionCreate, SubscriptionOut

router = APIRouter(prefix="/subscription", tags=["订阅"])


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
