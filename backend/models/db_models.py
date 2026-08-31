import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import String, Numeric, Boolean, DateTime, ForeignKey, JSON, Integer
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    full_name: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)

    documents: Mapped[list["Document"]] = relationship(back_populates="user")


class StoredFile(Base):
    """
    Metadata for a file saved to disk (services/local_storage.py) at upload time.
    Keyed by the same file_id that flows through OCR/classify/extract/validate,
    so the original document is retrievable long after the wizard session ends.
    """
    __tablename__ = "stored_files"

    file_id: Mapped[str] = mapped_column(String, primary_key=True)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    original_filename: Mapped[str] = mapped_column(String, default="")
    mime_type: Mapped[str] = mapped_column(String, default="")
    file_size: Mapped[int] = mapped_column(Integer, default=0)
    page_count: Mapped[int] = mapped_column(Integer, default=1)
    width: Mapped[int] = mapped_column(Integer, default=0)
    height: Mapped[int] = mapped_column(Integer, default=0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=True
    )

    file_id: Mapped[str] = mapped_column(String, nullable=False)
    file_name: Mapped[str] = mapped_column(String, default="")
    doc_type: Mapped[str] = mapped_column(String, nullable=False, index=True)

    # Key fields pulled out for querying/duplicate detection — full set lives in extracted_fields.
    invoice_no: Mapped[str | None] = mapped_column(String, index=True, nullable=True)
    vendor_name: Mapped[str | None] = mapped_column(String, nullable=True)
    vendor_gstin: Mapped[str | None] = mapped_column(String, nullable=True)
    # The other party on a GST_INVOICE. Only ever populated for GST_INVOICE today —
    # other doc types (PURCHASE_BILL, EXPENSE_RECEIPT, UTILITY_BILL) never carry a
    # second party, so they're always "payable" and buyer_* stays null for them.
    buyer_name: Mapped[str | None] = mapped_column(String, nullable=True)
    buyer_gstin: Mapped[str | None] = mapped_column(String, nullable=True)
    # 'payable' (money out — a bill/invoice this business received, the default)
    # or 'receivable' (money in — an invoice this business issued to a customer).
    # See services/direction_service.py for how this gets decided.
    direction: Mapped[str] = mapped_column(String, nullable=False, default="payable", index=True)
    total_amount: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    document_date: Mapped[str | None] = mapped_column(String, nullable=True)

    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    classification_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)
    classifier_level: Mapped[str | None] = mapped_column(String, nullable=True)

    # Full traceability — the raw output of each pipeline stage, not just what got flattened
    # into the columns above. Lets a later "why was this extracted" view reconstruct the chain.
    ocr_result: Mapped[dict] = mapped_column(JSON, default=dict)
    classification_result: Mapped[dict] = mapped_column(JSON, default=dict)
    extraction_result: Mapped[list] = mapped_column(JSON, default=list)

    validation_result: Mapped[dict] = mapped_column(JSON, default=dict)
    overall_passed: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)

    user: Mapped["User | None"] = relationship(back_populates="documents")
    line_items: Mapped[list["DocumentLineItem"]] = relationship(
        back_populates="document", cascade="all, delete-orphan", order_by="DocumentLineItem.sort_order"
    )


class DocumentLineItem(Base):
    __tablename__ = "document_line_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    description: Mapped[str] = mapped_column(String, default="")
    hsn_sac: Mapped[str] = mapped_column(String, default="")
    quantity: Mapped[str] = mapped_column(String, default="")
    unit: Mapped[str] = mapped_column(String, default="")
    rate: Mapped[str] = mapped_column(String, default="")
    amount: Mapped[str] = mapped_column(String, default="")

    document: Mapped["Document"] = relationship(back_populates="line_items")


class FieldCorrection(Base):
    """
    A log of every human correction made to an extracted field via the Document
    Review workspace (PUT /api/documents/{id}). This is the feedback dataset:
    it doesn't feed anything automatically yet, but it's what a future fine-tuning
    or "the model keeps confusing X for Y" analysis would be built from.
    """
    __tablename__ = "field_corrections"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    corrected_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    field_name: Mapped[str] = mapped_column(String, nullable=False, index=True)
    original_value: Mapped[str] = mapped_column(String, default="")
    corrected_value: Mapped[str] = mapped_column(String, default="")
    model_confidence: Mapped[float | None] = mapped_column(Numeric(5, 2), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow, index=True)


class AppSettings(Base):
    """
    Per-user settings row (one per user_id). Holds business profile info
    and the tunable validation/classification thresholds that otherwise
    live as hardcoded constants in utils/confidence_config.py.
    """
    __tablename__ = "app_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )

    # Business profile
    business_name: Mapped[str] = mapped_column(String, default="")
    business_gstin: Mapped[str] = mapped_column(String, default="")
    business_address: Mapped[str] = mapped_column(String, default="")

    # Classifier thresholds
    classifier_l1_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.80"))
    classifier_l2_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.60"))

    # Extraction threshold
    extractor_layoutlm_threshold: Mapped[Decimal] = mapped_column(Numeric(4, 3), default=Decimal("0.50"))

    # Validation tolerances
    gst_tax_match_tolerance: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0.01"))
    gst_rate_match_tolerance: Mapped[Decimal] = mapped_column(Numeric(6, 3), default=Decimal("0.5"))

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow
    )
