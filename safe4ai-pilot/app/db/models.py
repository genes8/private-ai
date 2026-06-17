import enum

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.db import Base

# Canonical sentinel ID for the ghost "deleted" user.  Every file that filters
# or creates this user must import this constant instead of copying the string.
DELETED_USER_ID = "00000000-0000-0000-0000-000000000001"

# Canonical ID for the default "General" workspace.  Single-workspace deployments
# and pre-workspace data live here; backfill assigns legacy rows to it.  Every
# file that references the default workspace must import this constant.
DEFAULT_WORKSPACE_ID = "00000000-0000-0000-0000-000000000002"


class UserRole(str, enum.Enum):
    # Global org-admin: manages settings/users/tier and sees every workspace.
    admin = "admin"
    pilot_user = "pilot_user"


class WorkspaceRole(str, enum.Enum):
    # Authority WITHIN a single workspace (distinct from the global UserRole).
    workspace_admin = "workspace_admin"
    member = "member"


class IngestionStatus(str, enum.Enum):
    queued = "queued"
    embedding = "embedding"
    indexed = "indexed"
    failed = "failed"
    skipped = "skipped"


class IngestionJobStatus(str, enum.Enum):
    pending = "pending"
    embedding = "embedding"
    completed = "completed"
    failed = "failed"


class DocumentVersionStatus(str, enum.Enum):
    pending = "pending"
    ingesting = "ingesting"
    staged = "staged"
    activating = "activating"
    active = "active"
    failed = "failed"
    superseded = "superseded"


class FeedbackRating(str, enum.Enum):
    positive = "positive"
    negative = "negative"


class ReviewStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, unique=True, nullable=False, index=True)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False, default=UserRole.pilot_user)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)
    failed_login_count = Column(Integer, default=0)
    locked_until = Column(DateTime(timezone=True), nullable=True)
    token_valid_after = Column(DateTime(timezone=True), nullable=True)


class Workspace(Base):
    """An intra-deployment boundary that segments documents and members.

    The deployment is still single-tenant (one company per stack); workspaces
    sub-divide that one company (e.g. Legal, Finance).  Retrieval, documents,
    sessions and audit are scoped to a workspace.
    """

    __tablename__ = "workspaces"

    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    slug = Column(String, nullable=False, unique=True, index=True)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    created_by = Column(
        String,
        ForeignKey("users.id", ondelete="SET DEFAULT"),
        nullable=False,
        server_default=DELETED_USER_ID,
    )


class WorkspaceMembership(Base):
    """Per-workspace authority for a user (distinct from the global UserRole)."""

    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint(
            "workspace_id", "user_id", name="uq_workspace_memberships_workspace_id_user_id"
        ),
    )

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String, ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(Enum(WorkspaceRole), nullable=False, default=WorkspaceRole.member)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Session(Base):
    __tablename__ = "sessions"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    workspace_id = Column(
        String,
        ForeignKey("workspaces.id", ondelete="SET DEFAULT"),
        nullable=False,
        server_default=DEFAULT_WORKSPACE_ID,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    state_json = Column(JSON, nullable=True)


class Document(Base):
    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    filename = Column(String, nullable=False)
    storage_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    ingestion_status = Column(
        Enum(IngestionStatus), nullable=False, default=IngestionStatus.queued
    )
    uploaded_by = Column(
        String,
        ForeignKey("users.id", ondelete="SET DEFAULT"),
        nullable=False,
        server_default=DELETED_USER_ID,
    )
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now())
    workspace_id = Column(
        String,
        ForeignKey("workspaces.id", ondelete="RESTRICT"),
        nullable=False,
        server_default=DEFAULT_WORKSPACE_ID,
        index=True,
    )
    doc_metadata = Column(JSON, nullable=True)
    ingestion_started_at = Column(DateTime(timezone=True), nullable=True)
    file_size_bytes = Column(Integer, nullable=True)
    version = Column(Integer, default=1)
    active_version = Column(Integer, default=1)
    active_version_id = Column(
        String,
        ForeignKey(
            "document_versions.id",
            ondelete="SET NULL",
            use_alter=True,
            name="documents_active_version_id_fkey",
        ),
        nullable=True,
        index=True,
    )
    title = Column(String, nullable=True)
    pending_version = Column(Integer, nullable=True)
    pending_filename = Column(String, nullable=True)
    pending_storage_filename = Column(String, nullable=True)
    pending_file_type = Column(String, nullable=True)
    pending_file_size_bytes = Column(Integer, nullable=True)


class DocumentVersion(Base):
    __tablename__ = "document_versions"
    __table_args__ = (
        UniqueConstraint(
            "document_id",
            "version_number",
            name="uq_document_versions_document_id_version_number",
        ),
    )

    id = Column(String, primary_key=True)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    version_number = Column(Integer, nullable=False)
    filename = Column(String, nullable=False)
    storage_filename = Column(String, nullable=False)
    file_type = Column(String, nullable=False)
    file_size_bytes = Column(Integer, nullable=True)
    checksum = Column(String, nullable=True)
    status = Column(
        Enum(DocumentVersionStatus), nullable=False, default=DocumentVersionStatus.pending
    )
    created_by = Column(
        String,
        ForeignKey("users.id", ondelete="SET DEFAULT"),
        nullable=False,
        server_default=DELETED_USER_ID,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ingestion_started_at = Column(DateTime(timezone=True), nullable=True)
    ingested_at = Column(DateTime(timezone=True), nullable=True)
    activated_at = Column(DateTime(timezone=True), nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    failed_reason = Column(Text, nullable=True)


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_version_id = Column(
        String, ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    chunk_index = Column(Integer, nullable=False)
    chunk_version = Column(Integer, default=1)
    content_preview = Column(String(500), nullable=True)
    qdrant_point_id = Column(String, nullable=True)


class SemanticCache(Base):
    __tablename__ = "semantic_cache"

    id = Column(String, primary_key=True)
    workspace_id = Column(
        String,
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
        server_default=DEFAULT_WORKSPACE_ID,
        index=True,
    )
    query_embedding = Column(Vector(768), nullable=False)
    query_text = Column(Text, nullable=False)
    response_json = Column(JSON, nullable=False)
    citations_json = Column(JSON, nullable=True)
    source_document_ids = Column(JSON, nullable=True)
    source_chunk_ids = Column(JSON, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    hit_count = Column(Integer, default=0)


class SemanticCacheHit(Base):
    __tablename__ = "semantic_cache_hits"

    id = Column(String, primary_key=True)
    cache_id = Column(
        String,
        ForeignKey("semantic_cache.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    workspace_id = Column(String, nullable=True, index=True)
    session_id = Column(String, nullable=True)
    timestamp = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    action_type = Column(String, nullable=False)
    query_text = Column(String(500), nullable=True)
    response_metadata = Column(JSON, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    model_used = Column(String, nullable=True)
    trace_id = Column(String, nullable=True)


class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False, index=True)
    workspace_id = Column(String, nullable=True, index=True)
    started_at = Column(DateTime(timezone=True), server_default=func.now())
    finished_at = Column(DateTime(timezone=True), nullable=True)
    status = Column(String, nullable=False)
    final_output = Column(Text, nullable=True)
    error = Column(Text, nullable=True)
    cost_usd = Column(Float, default=0.0)


class QueryFeedback(Base):
    __tablename__ = "query_feedback"

    id = Column(String, primary_key=True)
    trace_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False)
    workspace_id = Column(String, nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    rating = Column(Enum(FeedbackRating), nullable=False)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class IngestionJob(Base):
    __tablename__ = "ingestion_jobs"

    id = Column(String, primary_key=True)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    document_version_id = Column(
        String, ForeignKey("document_versions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    status = Column(Enum(IngestionJobStatus), nullable=False, default=IngestionJobStatus.pending)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    completed_at = Column(DateTime(timezone=True), nullable=True)
    error = Column(Text, nullable=True)


class HumanReviewQueue(Base):
    __tablename__ = "human_review_queue"

    id = Column(String, primary_key=True)
    session_id = Column(String, nullable=False)
    workspace_id = Column(String, nullable=True, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    query = Column(Text, nullable=False)
    draft_answer = Column(Text, nullable=True)
    citations_json = Column(JSON, nullable=True)
    risk_reason = Column(Text, nullable=True)
    status = Column(Enum(ReviewStatus), nullable=False, default=ReviewStatus.pending, index=True)
    reviewed_by = Column(String, nullable=True)
    reviewed_at = Column(DateTime(timezone=True), nullable=True)


class AppConfig(Base):
    __tablename__ = "app_config"

    key = Column(String, primary_key=True)
    value = Column(JSON, nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
