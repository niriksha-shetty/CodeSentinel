from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, Float, Enum as SQLEnum
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
import enum

from app.database import Base

class SeverityLevel(str, enum.Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"

class AgentCategory(str, enum.Enum):
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    STYLE = "STYLE"

class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True, index=True)
    repo_full_name = Column(String(255), index=True, nullable=False)
    pr_number = Column(Integer, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    author = Column(String(255), nullable=False)
    state = Column(String(50), default="open")
    head_sha = Column(String(100), nullable=True)
    base_branch = Column(String(100), default="main")
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reviews = relationship("ReviewSession", back_populates="pull_request", cascade="all, delete-orphan")

class ReviewSession(Base):
    __tablename__ = "review_sessions"

    id = Column(Integer, primary_key=True, index=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)
    commit_sha = Column(String(100), nullable=False)
    status = Column(String(50), default="completed") # pending, completed, failed
    severity_score = Column(Float, default=0.0) # 0 to 100 risk score
    summary = Column(Text, nullable=True)
    
    security_count = Column(Integer, default=0)
    performance_count = Column(Integer, default=0)
    style_count = Column(Integer, default=0)
    total_findings = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    pull_request = relationship("PullRequest", back_populates="reviews")
    findings = relationship("ReviewFinding", back_populates="review_session", cascade="all, delete-orphan")

class ReviewFinding(Base):
    __tablename__ = "review_findings"

    id = Column(Integer, primary_key=True, index=True)
    review_session_id = Column(Integer, ForeignKey("review_sessions.id"), nullable=False)
    agent_type = Column(SQLEnum(AgentCategory), nullable=False)
    severity = Column(SQLEnum(SeverityLevel), nullable=False)
    file_path = Column(String(500), nullable=False)
    line_number = Column(Integer, nullable=False, default=1)
    issue_title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    suggestion = Column(Text, nullable=True)
    code_snippet = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    review_session = relationship("ReviewSession", back_populates="findings")
