from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import or_
from app.database import get_db
from app.models import Product, Alias
from app.schemas import (
    ProductCreate, ProductUpdate, ProductOut, ProductBrief, AliasCreate, AliasOut,
)

router = APIRouter(prefix="/catalog", tags=["收录"])


@router.post("/products", response_model=ProductOut, summary="提交产品条目")
def create_product(data: ProductCreate, db: Session = Depends(get_db)):
    product = Product(**data.model_dump())
    db.add(product)
    db.commit()
    db.refresh(product)
    return product


@router.get("/products", response_model=List[ProductOut], summary="获取产品列表")
def list_products(
    category: Optional[str] = None,
    is_public: Optional[bool] = None,
    keyword: Optional[str] = None,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    q = db.query(Product)
    if category is not None:
        q = q.filter(Product.category == category)
    if is_public is not None:
        q = q.filter(Product.is_public == is_public)
    if keyword:
        alias_sub = db.query(Alias.product_id).filter(Alias.alias_name.contains(keyword)).subquery()
        q = q.filter(
            or_(
                Product.name.contains(keyword),
                Product.description.contains(keyword),
                Product.id.in_(alias_sub),
            )
        )
    return q.offset(skip).limit(limit).all()


@router.get("/products/{product_id}", response_model=ProductOut, summary="获取产品详情")
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    return product


@router.put("/products/{product_id}", response_model=ProductOut, summary="更新产品条目")
def update_product(product_id: int, data: ProductUpdate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(product, key, value)
    db.commit()
    db.refresh(product)
    return product


@router.patch("/products/{product_id}/visibility", response_model=ProductOut, summary="公开条目开关")
def toggle_visibility(product_id: int, is_public: bool, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    product.is_public = is_public
    db.commit()
    db.refresh(product)
    return product


@router.delete("/products/{product_id}", summary="删除产品条目")
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    db.delete(product)
    db.commit()
    return {"detail": "已删除"}


@router.post("/products/{product_id}/aliases", response_model=AliasOut, summary="补充别名")
def add_alias(product_id: int, data: AliasCreate, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(status_code=404, detail="产品不存在")
    alias = Alias(product_id=product_id, alias_name=data.alias_name)
    db.add(alias)
    db.commit()
    db.refresh(alias)
    return alias


@router.delete("/products/{product_id}/aliases/{alias_id}", summary="删除别名")
def delete_alias(product_id: int, alias_id: int, db: Session = Depends(get_db)):
    alias = db.query(Alias).filter(Alias.id == alias_id, Alias.product_id == product_id).first()
    if not alias:
        raise HTTPException(status_code=404, detail="别名不存在")
    db.delete(alias)
    db.commit()
    return {"detail": "已删除"}


@router.get("/products/brief/list", response_model=List[ProductBrief], summary="简要产品列表")
def list_products_brief(db: Session = Depends(get_db)):
    return db.query(Product).all()
