import csv
import io
import json
import zipfile
from typing import List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import extract, func
from app.database import get_db
from app.models import (
    Product, Alias, TimelineEvent, VersionNode, Screenshot,
    FeatureChange, CompetitorComparison, FounderInterview,
    PriceChange, CorrectionAppeal, SourceCredibility, AuditLog,
)
from app.schemas import (
    CorrectionAppealCreate, CorrectionAppealOut, CorrectionAppealReview,
    SourceCredibilityCreate, SourceCredibilityOut,
    AuditLogOut, CredibilityScoreOut,
)
from app.services.update_feed import create_update_event

router = APIRouter(prefix="/review", tags=["审核"])


@router.post("/products/{product_id}/appeals", response_model=CorrectionAppealOut, summary="提交纠错申诉")
def create_appeal(product_id: int, data: CorrectionAppealCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    appeal = CorrectionAppeal(product_id=product_id, **data.model_dump())
    db.add(appeal)
    db.flush()
    create_update_event(
        product_id, "appeal",
        f"新增纠错申诉 [{data.field_name}]: {data.proposed_value}",
        db,
    )
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
def review_appeal(
    appeal_id: int,
    data: CorrectionAppealReview,
    reviewed_by: str = Query("", description="审核人"),
    db: Session = Depends(get_db),
):
    appeal = db.query(CorrectionAppeal).filter(CorrectionAppeal.id == appeal_id).first()
    if not appeal:
        raise HTTPException(status_code=404, detail="申诉不存在")
    if data.status not in ("approved", "rejected"):
        raise HTTPException(status_code=400, detail="状态必须是 approved 或 rejected")

    old_value = appeal.current_value
    new_value = appeal.proposed_value

    appeal.status = data.status
    if data.status == "approved":
        product = db.query(Product).filter(Product.id == appeal.product_id).first()
        if product and hasattr(product, appeal.field_name):
            actual_old = str(getattr(product, appeal.field_name) or "")
            setattr(product, appeal.field_name, appeal.proposed_value)
            old_value = actual_old
            new_value = appeal.proposed_value

    log = AuditLog(
        product_id=appeal.product_id,
        appeal_id=appeal.id,
        action=f"appeal_{data.status}",
        field_name=appeal.field_name,
        old_value=old_value,
        new_value=new_value,
        reviewed_by=reviewed_by,
    )
    db.add(log)
    db.flush()
    create_update_event(
        appeal.product_id, "appeal",
        f"申诉审核{data.status} [{appeal.field_name}]: '{old_value}' -> '{new_value}'",
        db,
    )
    db.commit()
    db.refresh(appeal)
    return appeal


@router.get("/products/{product_id}/audit-logs", response_model=List[AuditLogOut], summary="获取审核记录(变更前后对照)")
def list_audit_logs(product_id: int, db: Session = Depends(get_db)):
    return db.query(AuditLog).filter(AuditLog.product_id == product_id).order_by(AuditLog.created_at.desc()).all()


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


@router.get("/products/{product_id}/credibility-score", response_model=CredibilityScoreOut, summary="来源可信度汇总分")
def credibility_score(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    rows = db.query(SourceCredibility).filter(SourceCredibility.product_id == product_id).all()
    high_c = sum(1 for r in rows if r.credibility_level == "high")
    med_c = sum(1 for r in rows if r.credibility_level == "medium")
    low_c = sum(1 for r in rows if r.credibility_level == "low")
    total = len(rows)
    score = (high_c * 3 + med_c * 2 + low_c * 1) / total if total > 0 else 0.0
    return CredibilityScoreOut(
        product_id=product_id,
        product_name=product.name,
        score=round(score, 2),
        high_count=high_c,
        medium_count=med_c,
        low_count=low_c,
        total_sources=total,
    )


@router.get("/public/products", response_model=List[dict], summary="公开接口-仅查看公开条目")
def list_public_products(
    category: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Product).filter(Product.is_public == True)
    if category:
        q = q.filter(Product.category == category)
    products = q.offset(skip).limit(limit).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "website": p.website,
            "aliases": [a.alias_name for a in p.aliases],
        }
        for p in products
    ]


@router.get("/internal/products", response_model=List[dict], summary="内部接口-含未公开和待处理资料")
def list_internal_products(
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    has_pending_appeals: bool = Query(False, description="仅含待处理申诉"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if category:
        q = q.filter(Product.category == category)
    if is_public is not None:
        q = q.filter(Product.is_public == is_public)
    products = q.offset(skip).limit(limit).all()

    if has_pending_appeals:
        pending_ids = set(
            r[0] for r in db.query(CorrectionAppeal.product_id)
            .filter(CorrectionAppeal.status == "pending").all()
        )
        products = [p for p in products if p.id in pending_ids]

    result = []
    for p in products:
        item = {
            "id": p.id,
            "name": p.name,
            "description": p.description,
            "category": p.category,
            "website": p.website,
            "is_public": p.is_public,
            "aliases": [a.alias_name for a in p.aliases],
            "pending_appeals_count": sum(1 for a in p.correction_appeals if a.status == "pending"),
            "audit_logs_count": len(p.audit_logs),
        }
        result.append(item)
    return result


def _build_product_export(p, include_screenshots, include_features, include_comparisons,
                           include_interviews, include_sources, include_citations):
    row = {
        "id": p.id,
        "name": p.name,
        "description": p.description,
        "category": p.category,
        "website": p.website,
        "is_public": p.is_public,
        "aliases": [a.alias_name for a in p.aliases],
        "timeline_events": [
            {"id": e.id, "type": e.event_type, "date": e.event_date.isoformat(), "desc": e.description}
            for e in p.timeline_events
        ],
        "version_nodes": [
            {"id": v.id, "name": v.version_name, "date": v.release_date.isoformat(),
             "desc": v.description, "summary": v.changes_summary}
            for v in p.version_nodes
        ],
        "price_changes": [
            {"id": pc.id, "plan": pc.plan_name, "old": pc.old_price, "new": pc.new_price,
             "date": pc.effective_date.isoformat(), "currency": pc.currency}
            for pc in p.price_changes
        ],
        "created_at": p.created_at.isoformat(),
        "updated_at": p.updated_at.isoformat(),
    }
    if include_screenshots:
        row["screenshots"] = [
            {"id": s.id, "product_id": s.product_id, "version_node_id": s.version_node_id,
             "file_path": s.file_path, "caption": s.caption,
             "uploaded_at": s.uploaded_at.isoformat()}
            for s in p.screenshots
        ]
    if include_features:
        row["feature_changes"] = [
            {"id": fc.id, "feature": fc.feature_name, "type": fc.change_type,
             "desc": fc.description, "version_node_id": fc.version_node_id}
            for fc in p.feature_changes
        ]
    if include_comparisons:
        comps = []
        for c in getattr(p, '_comparisons', []):
            comps.append({
                "id": c.id, "competitor_id": c.competitor_product_id,
                "dimension": c.dimension, "product_value": c.product_value,
                "competitor_value": c.competitor_value,
            })
        row["competitor_comparisons"] = comps
    if include_interviews:
        row["founder_interviews"] = [
            {"id": iv.id, "name": iv.interviewee_name, "url": iv.interview_url,
             "date": iv.interview_date.isoformat() if iv.interview_date else None,
             "summary": iv.summary}
            for iv in p.founder_interviews
        ]
    if include_sources:
        row["source_credibilities"] = [
            {"id": sc.id, "source": sc.source_name, "url": sc.source_url,
             "level": sc.credibility_level, "notes": sc.notes}
            for sc in p.source_credibilities
        ]
    if include_citations:
        row["citation_cards"] = [
            {"id": cc.id, "text": cc.citation_text, "format": cc.format_type,
             "generated_at": cc.generated_at.isoformat()}
            for cc in p.citation_cards
        ]
    return row


@router.get("/export", summary="批量导出(增强版)")
def export_products(
    format: str = Query("json", description="导出格式: json / csv / zip"),
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    year: Optional[int] = Query(None, description="按年代筛选(时间线事件在该年)"),
    include_screenshots: bool = Query(False, description="是否包含截图文件信息"),
    include_features: bool = Query(True, description="是否包含功能变迁"),
    include_comparisons: bool = Query(True, description="是否包含竞品对比"),
    include_interviews: bool = Query(True, description="是否包含访谈"),
    include_sources: bool = Query(True, description="是否包含来源可信度"),
    include_citations: bool = Query(True, description="是否包含引用卡片"),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if category:
        q = q.filter(Product.category == category)
    if is_public is not None:
        q = q.filter(Product.is_public == is_public)

    if year is not None:
        pids_with_year = set(
            r[0] for r in db.query(TimelineEvent.product_id)
            .filter(extract("year", TimelineEvent.event_date) == year).all()
        )
        q = q.filter(Product.id.in_(pids_with_year))

    products = q.all()

    for p in products:
        p._comparisons = db.query(CompetitorComparison).filter(
            CompetitorComparison.product_id == p.id
        ).all()

    rows = [
        _build_product_export(p, include_screenshots, include_features,
                              include_comparisons, include_interviews,
                              include_sources, include_citations)
        for p in products
    ]

    if format == "csv":
        return _export_csv_zip(rows, include_screenshots, include_features, include_comparisons,
                               include_interviews, include_sources, include_citations)

    if format == "zip":
        return _export_zip(rows)

    content = json.dumps(rows, ensure_ascii=False, indent=2)
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=products_export.json"},
    )


def _export_csv_zip(rows, include_screenshots, include_features, include_comparisons,
                     include_interviews, include_sources, include_citations):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        products_csv = io.StringIO()
        if rows:
            writer = csv.DictWriter(products_csv, fieldnames=[
                "id", "name", "description", "category", "website", "is_public",
                "aliases", "created_at", "updated_at",
            ])
            writer.writeheader()
            for r in rows:
                writer.writerow({
                    "id": r["id"], "name": r["name"], "description": r["description"],
                    "category": r["category"], "website": r["website"],
                    "is_public": r["is_public"],
                    "aliases": "; ".join(r.get("aliases", [])),
                    "created_at": r["created_at"], "updated_at": r["updated_at"],
                })
        zf.writestr("products.csv", products_csv.getvalue())

        events_csv = io.StringIO()
        evt_writer = csv.DictWriter(events_csv, fieldnames=["product_id", "product_name", "type", "date", "desc"])
        evt_writer.writeheader()
        for r in rows:
            for e in r.get("timeline_events", []):
                evt_writer.writerow({
                    "product_id": r["id"], "product_name": r["name"],
                    "type": e["type"], "date": e["date"], "desc": e["desc"],
                })
        zf.writestr("timeline_events.csv", events_csv.getvalue())

        versions_csv = io.StringIO()
        ver_writer = csv.DictWriter(versions_csv, fieldnames=["product_id", "product_name", "name", "date", "desc", "summary"])
        ver_writer.writeheader()
        for r in rows:
            for v in r.get("version_nodes", []):
                ver_writer.writerow({
                    "product_id": r["id"], "product_name": r["name"],
                    "name": v["name"], "date": v["date"],
                    "desc": v["desc"], "summary": v["summary"],
                })
        zf.writestr("version_nodes.csv", versions_csv.getvalue())

        if include_screenshots:
            ss_csv = io.StringIO()
            ss_writer = csv.DictWriter(ss_csv, fieldnames=[
                "screenshot_id", "product_id", "product_name",
                "version_node_id", "file_path", "caption", "uploaded_at",
            ])
            ss_writer.writeheader()
            for r in rows:
                for s in r.get("screenshots", []):
                    ss_writer.writerow({
                        "screenshot_id": s["id"],
                        "product_id": s["product_id"],
                        "product_name": r["name"],
                        "version_node_id": s.get("version_node_id") or "",
                        "file_path": s["file_path"],
                        "caption": s["caption"],
                        "uploaded_at": s["uploaded_at"],
                    })
            zf.writestr("screenshots.csv", ss_csv.getvalue())

        prices_csv = io.StringIO()
        pr_writer = csv.DictWriter(prices_csv, fieldnames=["product_id", "product_name", "plan", "old", "new", "date", "currency"])
        pr_writer.writeheader()
        for r in rows:
            for pc in r.get("price_changes", []):
                pr_writer.writerow({
                    "product_id": r["id"], "product_name": r["name"],
                    "plan": pc["plan"], "old": pc["old"], "new": pc["new"],
                    "date": pc["date"], "currency": pc["currency"],
                })
        zf.writestr("price_changes.csv", prices_csv.getvalue())

        if include_features:
            fc_csv = io.StringIO()
            fc_writer = csv.DictWriter(fc_csv, fieldnames=["product_id", "product_name", "feature", "type", "desc", "version_node_id"])
            fc_writer.writeheader()
            for r in rows:
                for fc in r.get("feature_changes", []):
                    fc_writer.writerow({
                        "product_id": r["id"], "product_name": r["name"],
                        "feature": fc["feature"], "type": fc["type"],
                        "desc": fc["desc"], "version_node_id": fc.get("version_node_id", ""),
                    })
            zf.writestr("feature_changes.csv", fc_csv.getvalue())

        if include_comparisons:
            comp_csv = io.StringIO()
            comp_writer = csv.DictWriter(comp_csv, fieldnames=["product_id", "product_name", "competitor_id", "dimension", "product_value", "competitor_value"])
            comp_writer.writeheader()
            for r in rows:
                for c in r.get("competitor_comparisons", []):
                    comp_writer.writerow({
                        "product_id": r["id"], "product_name": r["name"],
                        "competitor_id": c["competitor_id"], "dimension": c["dimension"],
                        "product_value": c["product_value"], "competitor_value": c["competitor_value"],
                    })
            zf.writestr("competitor_comparisons.csv", comp_csv.getvalue())

        if include_interviews:
            iv_csv = io.StringIO()
            iv_writer = csv.DictWriter(iv_csv, fieldnames=["product_id", "product_name", "name", "url", "date", "summary"])
            iv_writer.writeheader()
            for r in rows:
                for iv in r.get("founder_interviews", []):
                    iv_writer.writerow({
                        "product_id": r["id"], "product_name": r["name"],
                        "name": iv["name"], "url": iv["url"],
                        "date": iv["date"] or "", "summary": iv["summary"],
                    })
            zf.writestr("founder_interviews.csv", iv_csv.getvalue())

        if include_sources:
            sc_csv = io.StringIO()
            sc_writer = csv.DictWriter(sc_csv, fieldnames=["product_id", "product_name", "source", "url", "level", "notes"])
            sc_writer.writeheader()
            for r in rows:
                for sc in r.get("source_credibilities", []):
                    sc_writer.writerow({
                        "product_id": r["id"], "product_name": r["name"],
                        "source": sc["source"], "url": sc["url"],
                        "level": sc["level"], "notes": sc["notes"],
                    })
            zf.writestr("source_credibilities.csv", sc_csv.getvalue())

        if include_citations:
            cc_csv = io.StringIO()
            cc_writer = csv.DictWriter(cc_csv, fieldnames=["product_id", "product_name", "format", "text", "generated_at"])
            cc_writer.writeheader()
            for r in rows:
                for cc in r.get("citation_cards", []):
                    cc_writer.writerow({
                        "product_id": r["id"], "product_name": r["name"],
                        "format": cc["format"], "text": cc["text"],
                        "generated_at": cc["generated_at"],
                    })
            zf.writestr("citation_cards.csv", cc_csv.getvalue())

    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=products_export.zip"},
    )


def _export_zip(rows):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        content = json.dumps(rows, ensure_ascii=False, indent=2)
        zf.writestr("products_full.json", content)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": "attachment; filename=products_export.zip"},
    )
