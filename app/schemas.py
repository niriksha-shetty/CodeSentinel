from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
from datetime import datetime
from app.models import SeverityLevel, AgentCategory

# --- Finding & Review Schemas ---
class FindingBase(BaseModel):
    agent_type: AgentCategory
    severity: SeverityLevel
    file_path: str
    line_number: int
    issue_title: str
    description: str
    suggestion: Optional[str] = None
    code_snippet: Optional[str] = None

class FindingCreate(FindingBase):
    pass

class FindingResponse(FindingBase):
    id: int
    review_session_id: int
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class ReviewSessionResponse(BaseModel):
    id: int
    pull_request_id: int
    commit_sha: str
    status: str
    severity_score: float
    summary: Optional[str] = None
    security_count: int
    performance_count: int
    style_count: int
    total_findings: int
    created_at: datetime
    findings: List[FindingResponse] = []

    model_config = ConfigDict(from_attributes=True)

class PullRequestResponse(BaseModel):
    id: int
    repo_full_name: str
    pr_number: int
    title: str
    author: str
    state: str
    head_sha: Optional[str] = None
    base_branch: str
    created_at: datetime
    updated_at: datetime
    reviews: List[ReviewSessionResponse] = []

    model_config = ConfigDict(from_attributes=True)

# --- PR Simulation Request ---
class SimulatePRRequest(BaseModel):
    repo_full_name: str = "owner/repo"
    pr_number: int = 42
    pr_title: str = "Feature: Update user auth and database queries"
    author: str = "developer"
    filename: str = "app/auth.py"
    diff_content: str = Field(..., description="Git diff patch content or raw file content to analyze")

# --- Stats Summary Response ---
class ReviewStatsResponse(BaseModel):
    total_prs_reviewed: int
    total_review_sessions: int
    total_findings: int
    security_findings: int
    performance_findings: int
    style_findings: int
    avg_severity_score: float
    critical_findings_count: int

# --- AST Chunk Schema ---
class ASTChunk(BaseModel):
    chunk_type: str  # function, class, async_function, module_level, or raw_block
    name: str        # name of the function/class
    start_line: int  # 1-indexed
    end_line: int    # 1-indexed
    code: str        # source code content of the chunk
