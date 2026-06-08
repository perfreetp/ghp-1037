import csv
import io
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import (
    Product, Alias, TimelineEvent, VersionNode, Screenshot,
    FeatureChange, CompetitorComparison, FounderInterview,
    PriceChange, CorrectionAppeal, SourceCredibility,
)
from app.schemas import (
    CorrectionAppealCreate, CorrectionAppealOut, CorrectionAppealReview,
    SourceCredibilityCreate, SourceCredibilityOut,
)

router = APIRouter(prefix="/review", tags=["审核"])


@router.post("/products/{product_id}/appeals", response_model=CorrectionAppealOut, summary="提交纠错申诉")
def create_appeal(product_id: int, data: CorrectionAppealCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    appeal = CorrectionAppeal(product_id=product_id, **data.model_dump())
    db.add(appeal)
    db.commit()
    db.refresh(appeal)
    return appeal


@router.get("/products/{product_id}/appeals", response_model=List[CorrectionAppealOut], summary="获取纠错申诉列表")
def list_appeals(product_id: int, status: Optional[str] = None, db: Session = Depends(get_db)):
    q = db.query(CorrectionAppeal).filter(CorrectionAppeal.product_id == product_id)
    if status:
        q = q.filter(CorrectionAppeal.status == status)
    return q.order_by(CorrectionAppeal.created_at.desc()).all()


@router.patch("/appeals/{appeal_id}", response_model=CorrectionAppealOut, summary="审核纠错申诉")
def review_appeal(appeal_id: int, data: CorrectionAppealReview, db: Session = Depends(get_db)):
    appeal = db.query(CorrectionAppeal).filter(CorrectionAppeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="申诉不存在")
    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")
    appeal.status = data.status
    if data.status == "approved":
        product = db.query(Product).filter(Product.id == appeal.product_id).first()
        if product and hasattr(product, appeal.field_name):
            setattr(product, appeal.field_name, appeal.proposed_value)
    db.commit()
    db.refresh(appeal)
    return appeal


@router.post("/products/{product_id}/source-credibility", response_model=SourceCredibilityOut, summary="标记来源可信度")
def create_source_credibility(product_id: int, data: SourceCredibilityCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    if data.credibility_level not in ("high", "medium", "low"):
        raise HTTPException(status_code=400, detail="可信度级别必须是 high/medium/low")
    sc = SourceCredibility(product_id=product_id, **data.model_dump())
    db.add(sc)
    db.commit()
    db.refresh(sc)
    return sc


@router.get("/products/{product_id}/source-credibility", response_model=List[SourceCredibilityOut], summary="获取来源可信度列表")
def list_source_credibility(product_id: int, db: Session = Depends(get_db)):
    return db.query(SourceCredibility).filter(SourceCredibility.product_id == product_id).all()


@router.delete("/source-credibility/{sc_id}", summary="删除来源可信度标记")
def delete_source_credibility(sc_id: int, db: Session = Depends(get_db)):
    sc = db.query(SourceCredibility).filter(SourceCredibility.id == sc_id).first()
    if not sc:
        raise HTTPException(status_code=404, detail="来源可信度记录不存在")
    db.delete(sc)
    db.commit()
    return {"detail": "已删除"}


@router.get("/export", summary="批量导出")
def export_products(
    format: str = Query("json", description="导出格式: json 或 csv"),
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if category:
        q = q.filter(Product.category == category)
    if is_public is not None:
        q = q.filter(Product.is_public == is_public)
    products = q.all()

    rows = []
    for p in products:
        aliases = [a.alias_name for a in p.aliases]
        events = [
            {"type": e.event_type, "date": e.event_date.isoformat(), "desc": e.description}
            for e in p.timeline_events
        ]
        versions = [
            {"name": v.version_name, "date": v.release_date.isoformat(), "summary": v.changes_summary}
            for v in p.version_nodes
        ]
        prices = [
            {"plan": pc.plan_name, "old": pc.old_price, "new": pc.new_price, "date": pc.effective_date.isoformat()}
            for pc in p.price_changes
        ]
        rows.append({
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "website": p.website,
            "is_public": p.is_public,
            "aliases": aliases,
            "timeline_events": events,
            "version_nodes": versions,
            "price_changes": prices,
            "created_at": p.created_at.isoformat(),
            "updated_at": p.updated_at.isoformat(),
        })

    if format == "csv":
        output = io.StringIO()
        flat_rows = []
        for r in rows:
            flat_rows.append({
                "id": r["id"],
                "name": r["name"],
                "description": r["description"],
                "category": r["category"],
                "website": r["website"],
                "is_public": r["is_public"],
                "aliases": "; ".join(r["aliases"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            })
        if flat_rows:
            writer = csv.DictWriter(output, fieldnames=flat_rows[0].keys())
            writer.writeheader()
            writer.writerows(flat_rows)
        output.seek(0)
        return StreamingResponse(
            iter([output.getvalue()]),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=products_export.csv"},
        )

    content = json.dumps(rows, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=products_export.json"},
    )
