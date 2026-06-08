from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Product, CompetitorComparison
from app.schemas import CompetitorComparisonCreate, CompetitorComparisonOut

router = APIRouter(prefix="/comparison", tags=["对比"])


@router.post("/products/{product_id}/comparisons", response_model=CompetitorComparisonOut, summary="创建竞品对比")
def create_comparison(product_id: int, data: CompetitorComparisonCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    competitor = db.query(Product).filter(Product.id == data.competitor_product_id).first()
    if not competitor:
        raise HTTPException(status_code=404, detail="竞品产品不存在")
    comp = CompetitorComparison(product_id=product_id, **data.model_dump())
    db.add(comp)
    db.commit()
    db.refresh(comp)
    return comp


@router.get("/products/{product_id}/comparisons", response_model=List[CompetitorComparisonOut], summary="获取竞品对比列表")
def list_comparisons(product_id: int, db: Session = Depends(get_db)):
    return db.query(CompetitorComparison).filter(CompetitorComparison.product_id == product_id).all()


@router.put("/comparisons/{comp_id}", response_model=CompetitorComparisonOut, summary="更新竞品对比")
def update_comparison(comp_id: int, data: CompetitorComparisonCreate, db: Session = Depends(get_db)):
    comp = db.query(CompetitorComparison).filter(CompetitorComparison.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="对比记录不存在")
    for key, value in data.model_dump().items():
        setattr(comp, key, value)
    db.commit()
    db.refresh(comp)
    return comp


@router.delete("/comparisons/{comp_id}", summary="删除竞品对比")
def delete_comparison(comp_id: int, db: Session = Depends(get_db)):
    comp = db.query(CompetitorComparison).filter(CompetitorComparison.id == comp_id).first()
    if not comp:
        raise HTTPException(status_code=404, detail="对比记录不存在")
    db.delete(comp)
    db.commit()
    return {"detail": "已删除"}


@router.get("/products/{product_id}/comparisons/summary", summary="竞品对比汇总")
def comparison_summary(product_id: int, db: Session = Depends(get_db)):
    comps = db.query(CompetitorComparison).filter(CompetitorComparison.product_id == product_id).all()
    if not comps:
        return {"dimensions": [], "competitors": []}
    competitor_ids = list({c.competitor_product_id for c in comps})
    competitors = db.query(Product).filter(Product.id.in_(competitor_ids)).all()
    comp_map = {p.id: p.name for p in competitors}
    dimensions = list({c.dimension for c in comps})
    return {
        "product_id": product_id,
        "competitors": [{"id": cid, "name": comp_map.get(cid, "未知")} for cid in competitor_ids],
        "dimensions": dimensions,
        "items": [
            {
                "dimension": c.dimension,
                "competitor_product_id": c.competitor_product_id,
                "competitor_name": comp_map.get(c.competitor_product_id, "未知"),
                "product_value": c.product_value,
                "competitor_value": c.competitor_value,
            }
            for c in comps
        ],
    }
