import os
import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from sqlalchemy.orm import Session
from app.database import get_db, UPLOAD_DIR
from app.models import Product, Screenshot, FeatureChange, FounderInterview, PriceChange, VersionNode
from app.schemas import (
    ScreenshotOut, FeatureChangeCreate, FeatureChangeOut,
    FounderInterviewCreate, FounderInterviewOut,
    PriceChangeCreate, PriceChangeOut,
)
from app.services.update_feed import create_update_event

router = APIRouter(prefix="/material", tags=["素材"])


@router.post("/products/{product_id}/screenshots", response_model=ScreenshotOut, summary="上传截图说明")
def upload_screenshot(
    product_id: int,
    file: UploadFile = File(...),
    caption: str = Form(""),
    version_node_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    if version_node_id:
        vn = db.query(VersionNode).filter(VersionNode.id == version_node_id).first()
        if not vn:
            raise HTTPException(status_code=404, detail="版本节点不存在")
    ext = os.path.splitext(file.filename or "image.png")[1]
    filename = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, filename)
    content = file.file.read()
    with open(file_path, "wb") as f:
        f.write(content)
    screenshot = Screenshot(
        product_id=product_id,
        version_node_id=version_node_id,
        file_path=filename,
        caption=caption,
    )
    db.add(screenshot)
    db.flush()
    create_update_event(
        product_id, "material",
        f"新增截图: {caption or filename}",
        db,
    )
    db.commit()
    db.refresh(screenshot)
    return screenshot


@router.get("/products/{product_id}/screenshots", response_model=List[ScreenshotOut], summary="获取截图列表")
def list_screenshots(product_id: int, db: Session = Depends(get_db)):
    return db.query(Screenshot).filter(Screenshot.product_id == product_id).order_by(Screenshot.uploaded_at).all()


@router.delete("/screenshots/{screenshot_id}", summary="删除截图")
def delete_screenshot(screenshot_id: int, db: Session = Depends(get_db)):
    s = db.query(Screenshot).filter(Screenshot.id == screenshot_id).first()
    if not s:
        raise HTTPException(status_code=404, detail="截图不存在")
    full_path = os.path.join(UPLOAD_DIR, s.file_path)
    if os.path.exists(full_path):
        os.remove(full_path)
    create_update_event(
        s.product_id, "material",
        f"删除截图: {s.caption or s.file_path}",
        db,
    )
    db.delete(s)
    db.commit()
    return {"detail": "已删除"}


@router.post("/products/{product_id}/feature-changes", response_model=FeatureChangeOut, summary="整理功能变迁")
def create_feature_change(product_id: int, data: FeatureChangeCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    fc = FeatureChange(product_id=product_id, **data.model_dump())
    db.add(fc)
    db.flush()
    create_update_event(
        product_id, "material",
        f"新增功能变迁 [{data.change_type}] {data.feature_name}: {data.description}",
        db,
    )
    db.commit()
    db.refresh(fc)
    return fc


@router.get("/products/{product_id}/feature-changes", response_model=List[FeatureChangeOut], summary="获取功能变迁列表")
def list_feature_changes(product_id: int, db: Session = Depends(get_db)):
    return db.query(FeatureChange).filter(FeatureChange.product_id == product_id).all()


@router.delete("/feature-changes/{fc_id}", summary="删除功能变迁记录")
def delete_feature_change(fc_id: int, db: Session = Depends(get_db)):
    fc = db.query(FeatureChange).filter(FeatureChange.id == fc_id).first()
    if not fc:
        raise HTTPException(status_code=404, detail="功能变迁记录不存在")
    create_update_event(
        fc.product_id, "material",
        f"删除功能变迁 [{fc.change_type}] {fc.feature_name}",
        db,
    )
    db.delete(fc)
    db.commit()
    return {"detail": "已删除"}


@router.post("/products/{product_id}/interviews", response_model=FounderInterviewOut, summary="关联创始人访谈")
def create_interview(product_id: int, data: FounderInterviewCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    interview = FounderInterview(product_id=product_id, **data.model_dump())
    db.add(interview)
    db.flush()
    create_update_event(
        product_id, "material",
        f"新增访谈 [{data.interviewee_name}]: {data.summary}",
        db,
    )
    db.commit()
    db.refresh(interview)
    return interview


@router.get("/products/{product_id}/interviews", response_model=List[FounderInterviewOut], summary="获取访谈列表")
def list_interviews(product_id: int, db: Session = Depends(get_db)):
    return db.query(FounderInterview).filter(FounderInterview.product_id == product_id).all()


@router.delete("/interviews/{interview_id}", summary="删除访谈")
def delete_interview(interview_id: int, db: Session = Depends(get_db)):
    iv = db.query(FounderInterview).filter(FounderInterview.id == interview_id).first()
    if not iv:
        raise HTTPException(status_code=404, detail="访谈不存在")
    create_update_event(
        iv.product_id, "material",
        f"删除访谈 [{iv.interviewee_name}]",
        db,
    )
    db.delete(iv)
    db.commit()
    return {"detail": "已删除"}


@router.post("/products/{product_id}/price-changes", response_model=PriceChangeOut, summary="保存价格变化")
def create_price_change(product_id: int, data: PriceChangeCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    pc = PriceChange(product_id=product_id, **data.model_dump())
    db.add(pc)
    db.flush()
    old_str = f"{data.old_price}" if data.old_price is not None else "N/A"
    create_update_event(
        product_id, "price",
        f"价格变化 [{data.plan_name}]: {old_str}→{data.new_price} {data.currency}",
        db,
    )
    db.commit()
    db.refresh(pc)
    return pc


@router.get("/products/{product_id}/price-changes", response_model=List[PriceChangeOut], summary="获取价格变化列表")
def list_price_changes(product_id: int, db: Session = Depends(get_db)):
    return db.query(PriceChange).filter(PriceChange.product_id == product_id).order_by(PriceChange.effective_date).all()


@router.delete("/price-changes/{pc_id}", summary="删除价格变化记录")
def delete_price_change(pc_id: int, db: Session = Depends(get_db)):
    pc = db.query(PriceChange).filter(PriceChange.id == pc_id).first()
    if not pc:
        raise HTTPException(status_code=404, detail="价格变化记录不存在")
    create_update_event(
        pc.product_id, "price",
        f"删除价格记录 [{pc.plan_name}]",
        db,
    )
    db.delete(pc)
    db.commit()
    return {"detail": "已删除"}
