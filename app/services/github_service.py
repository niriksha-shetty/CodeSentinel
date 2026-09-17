import httpx
import logging
from typing import List, Dict, Any, Optional
from app.config import settings

logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(self, token: Optional[str] = None):
        self.token = token or settings.github_token
        self.headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeSentinel-PR-Review-Agent"
        }
        if self.token:
            self.headers["Authorization"] = f"token {self.token}"

    async def fetch_pr_diff(self, repo_full_name: str, pr_number: int) -> str:
        """
        Fetches the unified git diff for a given PR from GitHub API.
        """
        if not self.token:
            logger.warning("No GITHUB_TOKEN configured; returning empty/mock diff capability.")
            return ""

        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}"
        diff_headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        
        async with httpx.AsyncClient() as client:
            response = await client.get(url, headers=diff_headers, timeout=30.0)
            if response.status_code == 200:
                return response.text
            else:
                logger.error(f"Failed to fetch PR diff: {response.status_code} - {response.text}")
                return ""

    async def post_pr_review(
        self,
        repo_full_name: str,
        pr_number: int,
        commit_sha: str,
        comments: List[Dict[str, Any]],
        body_summary: str,
        event: str = "COMMENT"
    ) -> Dict[str, Any]:
        """
        Posts automated multi-agent code review comments directly onto the active PR via GitHub's Review API.
        
        API Endpoint: POST /repos/{owner}/{repo}/pulls/{pr_number}/reviews
        Payload format:
        {
          "commit_id": "...",
          "body": "...",
          "event": "COMMENT" | "REQUEST_CHANGES" | "APPROVE",
          "comments": [
             {
               "path": "app/main.py",
               "line": 42,
               "body": "Comment text"
             }
          ]
        }
        """
        if not self.token:
            logger.info(f"[Offline Mode] Would post PR Review to {repo_full_name}#{pr_number}:\nSummary:\n{body_summary}\nComments: {len(comments)}")
            return {
                "status": "simulated",
                "repo": repo_full_name,
                "pr_number": pr_number,
                "comments_posted": len(comments),
                "event": event
            }

        url = f"https://api.github.com/repos/{repo_full_name}/pulls/{pr_number}/reviews"
        
        payload = {
            "commit_id": commit_sha,
            "body": body_summary,
            "event": event,
            "comments": comments
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=self.headers, json=payload, timeout=30.0)
            if response.status_code in (200, 201):
                logger.info(f"Successfully posted PR review to {repo_full_name}#{pr_number}")
                return response.json()
            else:
                logger.error(f"Failed to post PR review to GitHub: {response.status_code} - {response.text}")
                return {"status": "error", "status_code": response.status_code, "error": response.text}

    @staticmethod
    def format_github_comment(finding: Dict[str, Any]) -> Dict[str, Any]:
        """Formats a ReviewFinding dict into a GitHub Review comment object."""
        severity_emoji = {
            "CRITICAL": "🚨",
            "HIGH": "⚠️",
            "MEDIUM": "⚡",
            "LOW": "ℹ️",
            "INFO": "💡"
        }.get(finding.get("severity"), "🔍")

        agent_name = finding.get("agent_type", "AI")
        title = finding.get("issue_title", "Code Issue")
        desc = finding.get("description", "")
        suggestion = finding.get("suggestion", "")

        comment_body = f"### {severity_emoji} [{agent_name}] {title}\n"
        comment_body += f"**Severity**: `{finding.get('severity')}`\n\n"
        comment_body += f"{desc}\n"

        if suggestion:
            comment_body += f"\n**Suggested Fix:**\n```python\n{suggestion}\n```"

        return {
            "path": finding.get("file_path", "code.py"),
            "line": int(finding.get("line_number", 1)),
            "body": comment_body
        }
