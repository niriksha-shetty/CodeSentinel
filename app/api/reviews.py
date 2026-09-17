from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from app.database import get_db
from app.models import PullRequest, ReviewSession, ReviewFinding
from app.schemas import (
    PullRequestResponse, ReviewSessionResponse, ReviewStatsResponse,
    SimulatePRRequest
)
from app.services.review_engine import MultiAgentReviewEngine

router = APIRouter()
review_engine = MultiAgentReviewEngine()


@router.get("/reviews", response_model=List[PullRequestResponse])
def get_all_reviews(db: Session = Depends(get_db)):
    """Fetches all pull requests and their associated AI review sessions."""
    prs = db.query(PullRequest).order_by(PullRequest.created_at.desc()).all()
    return prs


@router.get("/reviews/{session_id}", response_model=ReviewSessionResponse)
def get_review_session(session_id: int, db: Session = Depends(get_db)):
    """Fetches details for a specific review session by ID."""
    session = db.query(ReviewSession).filter(ReviewSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Review session not found")
    return session


@router.get("/stats", response_model=ReviewStatsResponse)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """Calculates overall metrics and severity stats across all PR review runs."""
    total_prs = db.query(PullRequest).count()
    total_sessions = db.query(ReviewSession).count()
    
    total_findings = db.query(ReviewFinding).count()
    security_findings = db.query(ReviewFinding).filter(ReviewFinding.agent_type == "SECURITY").count()
    performance_findings = db.query(ReviewFinding).filter(ReviewFinding.agent_type == "PERFORMANCE").count()
    style_findings = db.query(ReviewFinding).filter(ReviewFinding.agent_type == "STYLE").count()
    critical_findings = db.query(ReviewFinding).filter(ReviewFinding.severity == "CRITICAL").count()

    avg_score_res = db.query(func.avg(ReviewSession.severity_score)).scalar()
    avg_score = round(float(avg_score_res), 1) if avg_score_res is not None else 0.0

    return ReviewStatsResponse(
        total_prs_reviewed=total_prs,
        total_review_sessions=total_sessions,
        total_findings=total_findings,
        security_findings=security_findings,
        performance_findings=performance_findings,
        style_findings=style_findings,
        avg_severity_score=avg_score,
        critical_findings_count=critical_findings
    )


@router.post("/simulate", response_model=ReviewSessionResponse)
def simulate_pr_review(payload: SimulatePRRequest, db: Session = Depends(get_db)):
    """
    Interactive PR Review Simulator Endpoint.
    Allows manual submission of Python diffs/code snippets for instant 3-pass multi-agent AST review analysis.
    """
    # Create or fetch PR record
    db_pr = db.query(PullRequest).filter(
        PullRequest.repo_full_name == payload.repo_full_name,
        PullRequest.pr_number == payload.pr_number
    ).first()

    if not db_pr:
        db_pr = PullRequest(
            repo_full_name=payload.repo_full_name,
            pr_number=payload.pr_number,
            title=payload.pr_title,
            author=payload.author,
            head_sha="simulated_sha_123"
        )
        db.add(db_pr)
        db.commit()
        db.refresh(db_pr)

    # Run multi-agent pipeline
    results = review_engine.run_review_pipeline(
        code_or_diff=payload.diff_content,
        filename=payload.filename
    )

    # Persist session
    session = ReviewSession(
        pull_request_id=db_pr.id,
        commit_sha="simulated_sha_123",
        status="completed",
        severity_score=results["severity_score"],
        summary=results["summary"],
        security_count=results["security_count"],
        performance_count=results["performance_count"],
        style_count=results["style_count"],
        total_findings=results["total_findings"]
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    # Save findings
    for f in results["findings"]:
        finding = ReviewFinding(
            review_session_id=session.id,
            agent_type=f["agent_type"],
            severity=f["severity"],
            file_path=f["file_path"],
            line_number=f["line_number"],
            issue_title=f["issue_title"],
            description=f["description"],
            suggestion=f.get("suggestion"),
            code_snippet=f.get("code_snippet")
        )
        db.add(finding)

    db.commit()
    db.refresh(session)

    return session
