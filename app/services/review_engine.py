import logging
from typing import List, Dict, Any, Tuple
from app.services.ast_chunker import chunk_code_by_ast
from app.agents.security_agent import SecurityAgent
from app.agents.performance_agent import PerformanceAgent
from app.agents.style_agent import StyleAgent

logger = logging.getLogger(__name__)

class MultiAgentReviewEngine:
    def __init__(self):
        self.security_agent = SecurityAgent()
        self.performance_agent = PerformanceAgent()
        self.style_agent = StyleAgent()

    def run_review_pipeline(self, code_or_diff: str, filename: str = "code.py") -> Dict[str, Any]:
        """
        Executes a 3-pass multi-agent code review on the provided code/diff:
        - AST Code Chunking (function/class boundaries)
        - Pass 1: SecurityAgent analysis
        - Pass 2: PerformanceAgent analysis
        - Pass 3: StyleAgent analysis
        - Calculates aggregated severity score & summary report.
        """
        # Step 1: Split into semantic AST chunks
        chunks = chunk_code_by_ast(code_or_diff, filename=filename)
        logger.info(f"Generated {len(chunks)} AST chunks for file '{filename}'")

        all_findings: List[Dict[str, Any]] = []

        # Step 2: Run 3-pass multi-agent analysis on each chunk
        for chunk in chunks:
            # Pass 1: Security Agent
            sec_findings = self.security_agent.analyze_chunk(chunk, filename)
            all_findings.extend(sec_findings)

            # Pass 2: Performance Agent
            perf_findings = self.performance_agent.analyze_chunk(chunk, filename)
            all_findings.extend(perf_findings)

            # Pass 3: Style Agent
            style_findings = self.style_agent.analyze_chunk(chunk, filename)
            all_findings.extend(style_findings)

        # Step 3: Deduplicate findings
        unique_findings = self._deduplicate_findings(all_findings)

        # Step 4: Calculate counts and severity score
        security_count = sum(1 for f in unique_findings if f["agent_type"] == "SECURITY")
        performance_count = sum(1 for f in unique_findings if f["agent_type"] == "PERFORMANCE")
        style_count = sum(1 for f in unique_findings if f["agent_type"] == "STYLE")

        severity_score = self.calculate_severity_score(unique_findings)
        summary = self.generate_executive_summary(
            filename=filename,
            chunks_count=len(chunks),
            findings=unique_findings,
            score=severity_score
        )

        return {
            "severity_score": severity_score,
            "security_count": security_count,
            "performance_count": performance_count,
            "style_count": style_count,
            "total_findings": len(unique_findings),
            "summary": summary,
            "findings": unique_findings,
            "chunks_processed": len(chunks)
        }

    @staticmethod
    def calculate_severity_score(findings: List[Dict[str, Any]]) -> float:
        """
        Calculates an aggregated risk score (0 to 100).
        0 = Pristine / Clean Code
        100 = Extremely Critical Security / Performance Failure
        """
        weights = {
            "CRITICAL": 30.0,
            "HIGH": 18.0,
            "MEDIUM": 8.0,
            "LOW": 3.0,
            "INFO": 1.0
        }
        raw_score = sum(weights.get(f.get("severity", "LOW"), 2.0) for f in findings)
        return min(100.0, round(raw_score, 1))

    @staticmethod
    def generate_executive_summary(filename: str, chunks_count: int, findings: List[Dict[str, Any]], score: float) -> str:
        """Generates a structured markdown summary of the review results."""
        status_badge = "🟢 PASS" if score < 25 else ("🟡 WARNING" if score < 60 else "🔴 ACTION REQUIRED")
        
        summary = f"## 🛡️ CodeSentinel Automated PR Review Report\n\n"
        summary += f"**Overall Status**: {status_badge} | **Severity Score**: `{score}/100`\n"
        summary += f"**File Analyzed**: `{filename}` | **AST Chunks**: `{chunks_count}`\n\n"

        if not findings:
            summary += "✨ **No issues detected!** The pull request diff passed all Security, Performance, and Style analysis checks.\n"
            return summary

        summary += "### 📊 Findings Breakdown\n"
        sec_count = sum(1 for f in findings if f["agent_type"] == "SECURITY")
        perf_count = sum(1 for f in findings if f["agent_type"] == "PERFORMANCE")
        style_count = sum(1 for f in findings if f["agent_type"] == "STYLE")

        summary += f"- 🔒 **Security Agent**: `{sec_count}` issue(s)\n"
        summary += f"- ⚡ **Performance Agent**: `{perf_count}` issue(s)\n"
        summary += f"- 🎨 **Style Agent**: `{style_count}` issue(s)\n\n"

        summary += "### 🚨 Top Flagged Issues\n"
        sorted_findings = sorted(findings, key=lambda x: {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3, "INFO": 4}.get(x.get("severity"), 5))
        
        for idx, f in enumerate(sorted_findings[:5], start=1):
            summary += f"{idx}. **[{f['agent_type']}] {f['issue_title']}** (Line {f['line_number']}) — `{f['severity']}`\n"
            summary += f"   _{f['description']}_\n"

        return summary

    @staticmethod
    def _deduplicate_findings(findings: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicates findings with identical file, line, and title."""
        seen = set()
        deduped = []
        for f in findings:
            key = (f.get("file_path"), f.get("line_number"), f.get("issue_title"))
            if key not in seen:
                seen.add(key)
                deduped.append(f)
        return deduped
