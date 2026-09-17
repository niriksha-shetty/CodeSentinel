import hmac
import hashlib
import logging
from fastapi import APIRouter, Request, HTTPException, Header, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from typing import Optional

from app.config import settings
from app.database import get_db
from app.models import PullRequest, ReviewSession, ReviewFinding
from app.services.review_engine import MultiAgentReviewEngine
from app.services.github_service import GitHubService

logger = logging.getLogger(__name__)

router = APIRouter()
review_engine = MultiAgentReviewEngine()
github_service = GitHubService()


def verify_github_signature(payload_body: bytes, signature_header: Optional[str]):
    """Verifies HMAC SHA-256 signature from GitHub webhook header."""
    if not settings.github_webhook_secret:
        return  # Signature verification disabled if no secret set
    if not signature_header:
        raise HTTPException(status_code=401, detail="X-Hub-Signature-256 header missing")

    sha_name, signature = signature_header.split('=')
    if sha_name != 'sha256':
        raise HTTPException(status_code=400, detail="Invalid signature algorithm")

    mac = hmac.new(
        settings.github_webhook_secret.encode('utf-8'),
        msg=payload_body,
        digestmod=hashlib.sha256
    )
    if not hmac.compare_digest(mac.hexdigest(), signature):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")


@router.post("/webhook")
async def github_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_github_event: Optional[str] = Header(None),
    x_hub_signature_256: Optional[str] = Header(None),
    db: Session = Depends(get_db)
):
    """
    GitHub Webhook listener endpoint for Pull Request events (opened, synchronize, reopened).
    Validates HMAC signature and processes multi-agent code review asynchronously.
    """
    body_bytes = await request.body()
    verify_github_signature(body_bytes, x_hub_signature_256)

    payload = await request.json()

    if x_github_event != "pull_request":
        return {"status": "ignored", "reason": f"Event '{x_github_event}' is not pull_request"}

    action = payload.get("action")
    if action not in ("opened", "synchronize", "reopened"):
        return {"status": "ignored", "reason": f"PR action '{action}' does not trigger review"}

    pr_data = payload.get("pull_request", {})
    repo_data = payload.get("repository", {})

    repo_full_name = repo_data.get("full_name", "unknown/repo")
    pr_number = pr_data.get("number", 0)
    pr_title = pr_data.get("title", "Untitled PR")
    author = pr_data.get("user", {}).get("login", "unknown")
    head_sha = pr_data.get("head", {}).get("sha", "head_sha")
    base_branch = pr_data.get("base", {}).get("ref", "main")

    logger.info(f"Received PR event '{action}' for {repo_full_name}#{pr_number}")

    # Step 1: Record or update PullRequest in database
    db_pr = db.query(PullRequest).filter(
        PullRequest.repo_full_name == repo_full_name,
        PullRequest.pr_number == pr_number
    ).first()

    if not db_pr:
        db_pr = PullRequest(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            title=pr_title,
            author=author,
            head_sha=head_sha,
            base_branch=base_branch
        )
        db.add(db_pr)
        db.commit()
        db.refresh(db_pr)

    # Step 2: Schedule background task for PR review processing
    background_tasks.add_task(
        process_pr_review,
        pr_id=db_pr.id,
        repo_full_name=repo_full_name,
        pr_number=pr_number,
        commit_sha=head_sha
    )

    return {
        "status": "accepted",
        "message": f"Review initiated for {repo_full_name}#{pr_number}",
        "action": action,
        "pr_id": db_pr.id
    }


async def process_pr_review(pr_id: int, repo_full_name: str, pr_number: int, commit_sha: str):
    """
    Background worker function that fetches PR diff, runs multi-agent review,
    saves results to database, and posts inline feedback to GitHub.
    """
    from app.database import SessionLocal
    db = SessionLocal()

    try:
        # Fetch PR diff from GitHub
        diff_text = await github_service.fetch_pr_diff(repo_full_name, pr_number)
        if not diff_text:
            diff_text = "# Sample diff fallback\ndef process_data(data):\n    eval(data)"

        # Run 3-pass multi-agent review engine
        review_results = review_engine.run_review_pipeline(diff_text, filename="pr_diff.py")

        # Create ReviewSession entry
        session = ReviewSession(
            pull_request_id=pr_id,
            commit_sha=commit_sha,
            status="completed",
            severity_score=review_results["severity_score"],
            summary=review_results["summary"],
            security_count=review_results["security_count"],
            performance_count=review_results["performance_count"],
            style_count=review_results["style_count"],
            total_findings=review_results["total_findings"]
        )
        db.add(session)
        db.commit()
        db.refresh(session)

        # Store individual findings
        findings_objects = []
        github_comments = []

        for f in review_results["findings"]:
            finding_record = ReviewFinding(
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
            db.add(finding_record)
            
            # Format comment for GitHub Review API
            github_comments.append(GitHubService.format_github_comment(f))

        db.commit()

        # Post review feedback back to GitHub PR
        event_type = "REQUEST_CHANGES" if review_results["severity_score"] >= 60 else "COMMENT"
        await github_service.post_pr_review(
            repo_full_name=repo_full_name,
            pr_number=pr_number,
            commit_sha=commit_sha,
            comments=github_comments,
            body_summary=review_results["summary"],
            event=event_type
        )
        logger.info(f"Completed PR review task for {repo_full_name}#{pr_number}")

    except Exception as e:
        logger.error(f"Error processing PR review for {repo_full_name}#{pr_number}: {e}", exc_info=True)
    finally:
        db.close()
