from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os
from app.database import engine, Base, UPLOAD_DIR
from app.routers import catalog, timeline, material, comparison, citation, subscription, review

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="产品考古馆 API",
    description="供研究型媒体和产品团队调用，整理已停运或大改版的在线工具资料",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.isdir(UPLOAD_DIR):
    app.mount("/uploads", StaticFiles(directory=UPLOAD_DIR), name="uploads")

app.include_router(catalog.router, prefix="/api/v1")
app.include_router(timeline.router, prefix="/api/v1")
app.include_router(material.router, prefix="/api/v1")
app.include_router(comparison.router, prefix="/api/v1")
app.include_router(citation.router, prefix="/api/v1")
app.include_router(subscription.router, prefix="/api/v1")
app.include_router(review.router, prefix="/api/v1")


@app.get("/", tags=["健康检查"])
def root():
    return {"service": "产品考古馆", "version": "1.0.0", "status": "running"}
