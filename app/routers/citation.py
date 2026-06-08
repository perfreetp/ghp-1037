from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Product, Alias, CitationCard, TimelineEvent, VersionNode, FeatureChange, FounderInterview, PriceChange
from app.schemas import CitationCardCreate, CitationCardOut, SearchResult, ProductOut

router = APIRouter(prefix="/citation", tags=["引用"])


@router.post("/products/{product_id}/citation-cards", response_model=CitationCardOut, summary="生成引用卡片")
def create_citation_card(product_id: int, data: CitationCardCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")

    events = db.query(TimelineEvent).filter(TimelineEvent.product_id == product_id).order_by(TimelineEvent.event_date).all()
    launched = next((e for e in events if e.event_type == "launched"), None)
    shutdown = next((e for e in events if e.event_type == "shutdown"), None)

    fmt = data.format_type
    now = datetime.utcnow().strftime("%Y-%m-%d")

    if fmt == "apa":
        launch_year = launched.event_date.strftime("%Y") if launched else "n.d."
        text = f"{product.name}. ({launch_year}). 产品考古馆. Retrieved {now}, from https://archaeology.example.com/products/{product_id}"
    elif fmt == "bibtex":
        launch_year = launched.event_date.strftime("%Y") if launched else "n.d."
        key = product.name.lower().replace(" ", "_")
        text = (
            f"@misc{{{key},\n"
            f"  title = {{{product.name}}},\n"
            f"  year = {{{launch_year}}},\n"
            f"  howpublished = {{产品考古馆}},\n"
            f"  note = {{Retrieved {now}}}\n"
            f"}}"
        )
    else:
        parts = [f"产品名称：{product.name}"]
        if product.category:
            parts.append(f"类别：{product.category}")
        if launched:
            parts.append(f"上线时间：{launched.event_date.strftime('%Y-%m-%d')}")
        if shutdown:
            parts.append(f"停运时间：{shutdown.event_date.strftime('%Y-%m-%d')}")
        parts.append(f"查看详情：https://archaeology.example.com/products/{product_id}")
        text = "\n".join(parts)

    card = CitationCard(
        product_id=product_id,
        citation_text=text,
        format_type=fmt,
    )
    db.add(card)
    db.commit()
    db.refresh(card)
    return card


@router.get("/products/{product_id}/citation-cards", response_model=List[CitationCardOut], summary="获取引用卡片列表")
def list_citation_cards(product_id: int, db: Session = Depends(get_db)):
    return db.query(CitationCard).filter(CitationCard.product_id == product_id).order_by(CitationCard.generated_at.desc()).all()


@router.get("/search", response_model=SearchResult, summary="全文检索")
def full_text_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    alias_sub = db.query(Alias.product_id).filter(Alias.alias_name.contains(q)).subquery()
    products = (
        db.query(Product)
        .filter(
            or_(
                Product.name.contains(q),
                Product.description.contains(q),
                Product.category.contains(q),
                Product.id.in_(alias_sub),
            )
        )
        .offset(skip)
        .limit(limit)
        .all()
    )
    total = (
        db.query(Product)
        .filter(
            or_(
                Product.name.contains(q),
                Product.description.contains(q),
                Product.category.contains(q),
                Product.id.in_(alias_sub),
            )
        )
        .count()
    )
    return SearchResult(products=products, total=total)
