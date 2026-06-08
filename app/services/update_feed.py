from sqlalchemy.orm import Session
from app.models import Subscription, UpdateEvent, UpdateReadStatus


def create_update_event(product_id: int, event_type: str, description: str, db: Session):
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
    db.flush()
    return evt
