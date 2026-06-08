from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey, Enum as SAEnum,
)
from sqlalchemy.orm import relationship
from app.database import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, index=True)
    description = Column(Text, default="")
    category = Column(String(100), default="")
    website = Column(String(500), default="")
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    aliases = relationship("Alias", back_populates="product", cascade="all, delete-orphan")
    timeline_events = relationship("TimelineEvent", back_populates="product", cascade="all, delete-orphan")
    version_nodes = relationship("VersionNode", back_populates="product", cascade="all, delete-orphan")
    screenshots = relationship("Screenshot", back_populates="product", cascade="all, delete-orphan")
    feature_changes = relationship("FeatureChange", back_populates="product", cascade="all, delete-orphan")
    founder_interviews = relationship("FounderInterview", back_populates="product", cascade="all, delete-orphan")
    price_changes = relationship("PriceChange", back_populates="product", cascade="all, delete-orphan")
    subscriptions = relationship("Subscription", back_populates="product", cascade="all, delete-orphan")
    correction_appeals = relationship("CorrectionAppeal", back_populates="product", cascade="all, delete-orphan")
    source_credibilities = relationship("SourceCredibility", back_populates="product", cascade="all, delete-orphan")
    citation_cards = relationship("CitationCard", back_populates="product", cascade="all, delete-orphan")
    audit_logs = relationship("AuditLog", back_populates="product", cascade="all, delete-orphan")
    update_events = relationship("UpdateEvent", back_populates="product", cascade="all, delete-orphan")


class Alias(Base):
    __tablename__ = "aliases"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    alias_name = Column(String(200), nullable=False)

    product = relationship("Product", back_populates="aliases")


class TimelineEvent(Base):
    __tablename__ = "timeline_events"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    event_type = Column(String(50), nullable=False)
    event_date = Column(DateTime, nullable=False)
    description = Column(Text, default="")

    product = relationship("Product", back_populates="timeline_events")


class VersionNode(Base):
    __tablename__ = "version_nodes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    version_name = Column(String(100), nullable=False)
    release_date = Column(DateTime, nullable=False)
    description = Column(Text, default="")
    changes_summary = Column(Text, default="")

    product = relationship("Product", back_populates="version_nodes")
    screenshots = relationship("Screenshot", back_populates="version_node")
    feature_changes = relationship("FeatureChange", back_populates="version_node")


class Screenshot(Base):
    __tablename__ = "screenshots"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    version_node_id = Column(Integer, ForeignKey("version_nodes.id"), nullable=True)
    file_path = Column(String(500), nullable=False)
    caption = Column(String(500), default="")
    uploaded_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="screenshots")
    version_node = relationship("VersionNode", back_populates="screenshots")


class FeatureChange(Base):
    __tablename__ = "feature_changes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    version_node_id = Column(Integer, ForeignKey("version_nodes.id"), nullable=True)
    feature_name = Column(String(200), nullable=False)
    change_type = Column(String(50), nullable=False)
    description = Column(Text, default="")

    product = relationship("Product", back_populates="feature_changes")
    version_node = relationship("VersionNode", back_populates="feature_changes")


class CompetitorComparison(Base):
    __tablename__ = "competitor_comparisons"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    competitor_product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    dimension = Column(String(200), nullable=False)
    product_value = Column(Text, default="")
    competitor_value = Column(Text, default="")

    product = relationship("Product", foreign_keys=[product_id])
    competitor = relationship("Product", foreign_keys=[competitor_product_id])


class FounderInterview(Base):
    __tablename__ = "founder_interviews"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    interviewee_name = Column(String(200), nullable=False)
    interview_url = Column(String(500), default="")
    interview_date = Column(DateTime, nullable=True)
    summary = Column(Text, default="")

    product = relationship("Product", back_populates="founder_interviews")


class PriceChange(Base):
    __tablename__ = "price_changes"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    plan_name = Column(String(200), nullable=False)
    old_price = Column(Float, nullable=True)
    new_price = Column(Float, nullable=False)
    effective_date = Column(DateTime, nullable=False)
    currency = Column(String(10), default="CNY")

    product = relationship("Product", back_populates="price_changes")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    subscriber_email = Column(String(200), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="subscriptions")


class CorrectionAppeal(Base):
    __tablename__ = "correction_appeals"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    appellant_name = Column(String(200), nullable=False)
    appellant_email = Column(String(200), nullable=False)
    field_name = Column(String(200), nullable=False)
    current_value = Column(Text, default="")
    proposed_value = Column(Text, default="")
    reason = Column(Text, default="")
    status = Column(String(20), default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="correction_appeals")
    audit_logs = relationship("AuditLog", back_populates="appeal", cascade="all, delete-orphan")


class SourceCredibility(Base):
    __tablename__ = "source_credibilities"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=True)
    source_name = Column(String(200), nullable=False)
    source_url = Column(String(500), default="")
    credibility_level = Column(String(20), nullable=False)
    notes = Column(Text, default="")

    product = relationship("Product", back_populates="source_credibilities")


class CitationCard(Base):
    __tablename__ = "citation_cards"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    citation_text = Column(Text, nullable=False)
    format_type = Column(String(50), default="plain")
    generated_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="citation_cards")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    appeal_id = Column(Integer, ForeignKey("correction_appeals.id"), nullable=True)
    action = Column(String(50), nullable=False)
    field_name = Column(String(200), default="")
    old_value = Column(Text, default="")
    new_value = Column(Text, default="")
    reviewed_by = Column(String(200), default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="audit_logs")
    appeal = relationship("CorrectionAppeal", back_populates="audit_logs")


class UpdateEvent(Base):
    __tablename__ = "update_events"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)
    event_type = Column(String(100), nullable=False)
    description = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="update_events")
    read_statuses = relationship("UpdateReadStatus", back_populates="update_event", cascade="all, delete-orphan")


class UpdateReadStatus(Base):
    __tablename__ = "update_read_statuses"

    id = Column(Integer, primary_key=True, index=True)
    update_event_id = Column(Integer, ForeignKey("update_events.id"), nullable=False)
    subscriber_email = Column(String(200), nullable=False)
    is_read = Column(Boolean, default=False)
    read_at = Column(DateTime, nullable=True)

    update_event = relationship("UpdateEvent", back_populates="read_statuses")
