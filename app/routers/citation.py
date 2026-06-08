from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import (
    Product, Alias, CitationCard, TimelineEvent, VersionNode,
    FeatureChange, FounderInterview, PriceChange, SourceCredibility,
)
from app.schemas import (
    CitationCardCreate, CitationCardOut, SearchResult, ProductOut,
    SearchHit, CrossSearchResult,
)

router = APIRouter(prefix="/citation", tags=["引用"])

SNIPPET_LEN = 120


def _make_snippet(text: str, keyword: str) -> str:
    idx = text.lower().find(keyword.lower())
    if idx < 0:
        return text[:SNIPPET_LEN]
    start = max(0, idx - 30)
    end = min(len(text), idx + len(keyword) + 90)
    prefix = "..." if start > 0 else ""
    suffix = "..." if end < len(text) else ""
    return prefix + text[start:end] + suffix


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


@router.get("/search", response_model=SearchResult, summary="产品搜索(旧版)")
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


@router.get("/search/cross", response_model=CrossSearchResult, summary="全文检索(跨所有实体)")
def cross_entity_search(
    q: str = Query(..., min_length=1, description="搜索关键词"),
    hit_type: Optional[str] = Query(None, description="限定资料类型: product/timeline/version/feature/interview/price/source/citation"),
    skip: int = Query(0, ge=0),
    limit: int = Query(30, ge=1, le=200),
    db: Session = Depends(get_db),
):
    hits: List[SearchHit] = []
    kw = f"%{q}%"

    product_map = {}
    all_products = db.query(Product).all()
    for p in all_products:
        product_map[p.id] = p.name

    if not hit_type or hit_type == "product":
        for p in all_products:
            matched = False
            snippet = ""
            if q.lower() in p.name.lower():
                snippet = _make_snippet(f"名称：{p.name}", q)
                matched = True
            elif q.lower() in (p.description or "").lower():
                snippet = _make_snippet(f"描述：{p.description}", q)
                matched = True
            elif q.lower() in (p.category or "").lower():
                snippet = _make_snippet(f"分类：{p.category}", q)
                matched = True
            if matched:
                hits.append(SearchHit(
                    hit_type="product", product_id=p.id,
                    product_name=p.name, snippet=snippet,
                    hit_time=p.created_at.isoformat() if p.created_at else None,
                ))

    if not hit_type or hit_type == "product":
        for a in db.query(Alias).filter(Alias.alias_name.ilike(kw)).all():
            hits.append(SearchHit(
                hit_type="alias", product_id=a.product_id,
                product_name=product_map.get(a.product_id, ""),
                snippet=_make_snippet(f"别名：{a.alias_name}", q),
                hit_time=None,
            ))

    if not hit_type or hit_type == "timeline":
        for e in db.query(TimelineEvent).filter(TimelineEvent.description.ilike(kw)).all():
            hits.append(SearchHit(
                hit_type="timeline", product_id=e.product_id,
                product_name=product_map.get(e.product_id, ""),
                snippet=_make_snippet(f"[{e.event_type}] {e.description}", q),
                hit_time=e.event_date.isoformat() if e.event_date else None,
            ))

    if not hit_type or hit_type == "version":
        ver_filter = or_(
            VersionNode.version_name.ilike(kw),
            VersionNode.description.ilike(kw),
            VersionNode.changes_summary.ilike(kw),
        )
        for v in db.query(VersionNode).filter(ver_filter).all():
            text = f"{v.version_name}: {v.changes_summary or v.description or ''}"
            hits.append(SearchHit(
                hit_type="version", product_id=v.product_id,
                product_name=product_map.get(v.product_id, ""),
                snippet=_make_snippet(text, q),
                hit_time=v.release_date.isoformat() if v.release_date else None,
            ))

    if not hit_type or hit_type == "feature":
        fc_filter = or_(
            FeatureChange.feature_name.ilike(kw),
            FeatureChange.description.ilike(kw),
        )
        for fc in db.query(FeatureChange).filter(fc_filter).all():
            hits.append(SearchHit(
                hit_type="feature", product_id=fc.product_id,
                product_name=product_map.get(fc.product_id, ""),
                snippet=_make_snippet(f"[{fc.change_type}] {fc.feature_name}: {fc.description}", q),
                hit_time=None,
            ))

    if not hit_type or hit_type == "interview":
        iv_filter = or_(
            FounderInterview.interviewee_name.ilike(kw),
            FounderInterview.summary.ilike(kw),
        )
        for iv in db.query(FounderInterview).filter(iv_filter).all():
            hits.append(SearchHit(
                hit_type="interview", product_id=iv.product_id,
                product_name=product_map.get(iv.product_id, ""),
                snippet=_make_snippet(f"{iv.interviewee_name}: {iv.summary}", q),
                hit_time=iv.interview_date.isoformat() if iv.interview_date else None,
            ))

    if not hit_type or hit_type == "price":
        for pc in db.query(PriceChange).all():
            old_str = str(pc.old_price) if pc.old_price is not None else "N/A"
            new_str = str(pc.new_price)
            searchable = f"{pc.plan_name} {old_str} {new_str} {pc.currency}"
            if q.lower() not in searchable.lower():
                continue
            text = f"{pc.plan_name}: {old_str} -> {new_str} {pc.currency} (生效: {pc.effective_date.strftime('%Y-%m-%d') if pc.effective_date else 'N/A'})"
            hits.append(SearchHit(
                hit_type="price", product_id=pc.product_id,
                product_name=product_map.get(pc.product_id, ""),
                snippet=_make_snippet(text, q),
                hit_time=pc.effective_date.isoformat() if pc.effective_date else None,
            ))

    if not hit_type or hit_type == "source":
        sc_filter = or_(
            SourceCredibility.source_name.ilike(kw),
            SourceCredibility.notes.ilike(kw),
        )
        for sc in db.query(SourceCredibility).filter(sc_filter).all():
            pid = sc.product_id
            hits.append(SearchHit(
                hit_type="source", product_id=pid or 0,
                product_name=product_map.get(pid, "") if pid else "",
                snippet=_make_snippet(f"[{sc.credibility_level}] {sc.source_name}: {sc.notes}", q),
                hit_time=None,
            ))

    if not hit_type or hit_type == "citation":
        for cc in db.query(CitationCard).filter(CitationCard.citation_text.ilike(kw)).all():
            hits.append(SearchHit(
                hit_type="citation", product_id=cc.product_id,
                product_name=product_map.get(cc.product_id, ""),
                snippet=_make_snippet(cc.citation_text, q),
                hit_time=cc.generated_at.isoformat() if cc.generated_at else None,
            ))

    total = len(hits)
    hits = hits[skip:skip + limit]
    return CrossSearchResult(hits=hits, total=total)
