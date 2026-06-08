from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, EmailStr


class ProductCreate(BaseModel):
    name: str
    description: str = ""
    category: str = ""
    website: str = ""
    is_public: bool = True


class ProductUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    website: Optional[str] = None
    is_public: Optional[bool] = None


class AliasCreate(BaseModel):
    alias_name: str


class AliasOut(BaseModel):
    id: int
    product_id: int
    alias_name: str

    class Config:
        from_attributes = True


class ProductOut(BaseModel):
    id: int
    name: str
    description: str
    category: str
    website: str
    is_public: bool
    created_at: datetime
    updated_at: datetime
    aliases: List[AliasOut] = []

    class Config:
        from_attributes = True


class ProductBrief(BaseModel):
    id: int
    name: str
    category: str
    is_public: bool

    class Config:
        from_attributes = True


class TimelineEventCreate(BaseModel):
    event_type: str
    event_date: datetime
    description: str = ""


class TimelineEventOut(BaseModel):
    id: int
    product_id: int
    event_type: str
    event_date: datetime
    description: str

    class Config:
        from_attributes = True


class VersionNodeCreate(BaseModel):
    version_name: str
    release_date: datetime
    description: str = ""
    changes_summary: str = ""


class VersionNodeOut(BaseModel):
    id: int
    product_id: int
    version_name: str
    release_date: datetime
    description: str
    changes_summary: str

    class Config:
        from_attributes = True


class ScreenshotOut(BaseModel):
    id: int
    product_id: int
    version_node_id: Optional[int] = None
    file_path: str
    caption: str
    uploaded_at: datetime

    class Config:
        from_attributes = True


class FeatureChangeCreate(BaseModel):
    version_node_id: Optional[int] = None
    feature_name: str
    change_type: str
    description: str = ""


class FeatureChangeOut(BaseModel):
    id: int
    product_id: int
    version_node_id: Optional[int] = None
    feature_name: str
    change_type: str
    description: str

    class Config:
        from_attributes = True


class CompetitorComparisonCreate(BaseModel):
    competitor_product_id: int
    dimension: str
    product_value: str = ""
    competitor_value: str = ""


class CompetitorComparisonOut(BaseModel):
    id: int
    product_id: int
    competitor_product_id: int
    dimension: str
    product_value: str
    competitor_value: str

    class Config:
        from_attributes = True


class FounderInterviewCreate(BaseModel):
    interviewee_name: str
    interview_url: str = ""
    interview_date: Optional[datetime] = None
    summary: str = ""


class FounderInterviewOut(BaseModel):
    id: int
    product_id: int
    interviewee_name: str
    interview_url: str
    interview_date: Optional[datetime] = None
    summary: str

    class Config:
        from_attributes = True


class PriceChangeCreate(BaseModel):
    plan_name: str
    old_price: Optional[float] = None
    new_price: float
    effective_date: datetime
    currency: str = "CNY"


class PriceChangeOut(BaseModel):
    id: int
    product_id: int
    plan_name: str
    old_price: Optional[float] = None
    new_price: float
    effective_date: datetime
    currency: str

    class Config:
        from_attributes = True


class SubscriptionCreate(BaseModel):
    subscriber_email: str


class SubscriptionOut(BaseModel):
    id: int
    subscriber_email: str
    product_id: int
    created_at: datetime

    class Config:
        from_attributes = True


class CorrectionAppealCreate(BaseModel):
    appellant_name: str
    appellant_email: str
    field_name: str
    current_value: str = ""
    proposed_value: str = ""
    reason: str = ""


class CorrectionAppealOut(BaseModel):
    id: int
    product_id: int
    appellant_name: str
    appellant_email: str
    field_name: str
    current_value: str
    proposed_value: str
    reason: str
    status: str
    created_at: datetime

    class Config:
        from_attributes = True


class CorrectionAppealReview(BaseModel):
    status: str


class SourceCredibilityCreate(BaseModel):
    source_name: str
    source_url: str = ""
    credibility_level: str
    notes: str = ""


class SourceCredibilityOut(BaseModel):
    id: int
    product_id: Optional[int] = None
    source_name: str
    source_url: str
    credibility_level: str
    notes: str

    class Config:
        from_attributes = True


class CitationCardCreate(BaseModel):
    format_type: str = "plain"


class CitationCardOut(BaseModel):
    id: int
    product_id: int
    citation_text: str
    format_type: str
    generated_at: datetime

    class Config:
        from_attributes = True


class SearchResult(BaseModel):
    products: List[ProductOut]
    total: int


class SearchHit(BaseModel):
    hit_type: str
    product_id: int
    product_name: str
    snippet: str
    hit_time: Optional[str] = None


class CrossSearchResult(BaseModel):
    hits: List[SearchHit]
    total: int


class AuditLogOut(BaseModel):
    id: int
    product_id: int
    appeal_id: Optional[int] = None
    action: str
    field_name: str
    old_value: str
    new_value: str
    reviewed_by: str
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateEventOut(BaseModel):
    id: int
    product_id: int
    event_type: str
    description: str
    created_at: datetime
    is_read: Optional[bool] = None

    class Config:
        from_attributes = True


class CredibilityScoreOut(BaseModel):
    product_id: int
    product_name: str
    score: float
    high_count: int
    medium_count: int
    low_count: int
    total_sources: int
