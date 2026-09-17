import re
from typing import List, Dict, Any
from app.agents.base import BaseAgent
from app.models import AgentCategory, SeverityLevel
from app.schemas import ASTChunk

class PerformanceAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="PerformanceAgent", category=AgentCategory.PERFORMANCE)

    def get_system_prompt(self) -> str:
        return """You are PerformanceAgent, a senior software architect specializing in runtime efficiency and optimization.
Your job is to identify performance issues including:
1. $O(N^2)$ or higher time complexity: Nested loops scanning lists/arrays or performing expensive operations per element.
2. N+1 Database Query problem: Executing database queries or HTTP network requests inside a loop.
3. Memory leaks & resource management: Opening files/sockets/connections without context managers (`with` statements) or proper cleanup.
4. Redundant API calls & compute: Duplicate sub-queries or repeated un-cached remote calls.
5. Blocking operations in async functions: Calling synchronous `time.sleep()`, synchronous `requests.get()`, or blocking I/O inside `async def`.

You MUST respond with a JSON array of objects.
JSON schema per object:
[
  {
    "line_number": <int>,
    "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO",
    "issue_title": "<Short clear title>",
    "description": "<Explanation of performance impact>",
    "suggestion": "<Optimized refactored code>",
    "code_snippet": "<Offending code snippet>"
  }
]
If no performance issues are present, return an empty JSON array: [].
Do NOT include markdown wrapping or extra conversational text outside the JSON array."""

    def _analyze_rule_fallback(self, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        findings = []
        lines = chunk.code.splitlines()

        in_loop = False
        loop_indent = -1
        nested_loop_detected = False

        for idx, line_str in enumerate(lines, start=chunk.start_line):
            stripped = line_str.strip()
            indent = len(line_str) - len(line_str.lstrip())

            # Detect loop
            is_loop_start = bool(re.match(r'^(for\s+|while\s+)', stripped))

            if is_loop_start:
                if in_loop and indent > loop_indent:
                    nested_loop_detected = True
                    findings.append({
                        "agent_type": self.category.value,
                        "severity": SeverityLevel.HIGH.value,
                        "file_path": filename,
                        "line_number": idx,
                        "issue_title": "Potential O(N^2) Algorithmic Time Complexity",
                        "description": f"Nested loop detected at line {idx}. Iterating over collections inside outer loops causes $O(N^2)$ time complexity.",
                        "suggestion": "# Consider using a set/dict lookup or vectorizing operation:\nseen = set(outer_collection)\nfor item in inner_collection:\n    if item in seen: ...",
                        "code_snippet": line_str.strip()
                    })
                else:
                    in_loop = True
                    loop_indent = indent
            elif in_loop and indent <= loop_indent and stripped:
                in_loop = False

            # Detect DB query or HTTP call inside loop
            if in_loop:
                if re.search(r'(?i)(db\.|session\.|query\(|requests\.|httpx\.|fetch\(|select\s)', stripped):
                    findings.append({
                        "agent_type": self.category.value,
                        "severity": SeverityLevel.HIGH.value,
                        "file_path": filename,
                        "line_number": idx,
                        "issue_title": "N+1 Query / Network Call inside Loop",
                        "description": f"Database query or network call executed inside a loop at line {idx}. This leads to severe I/O bottleneck.",
                        "suggestion": "# Batch load data before loop:\nitems = db.query(Model).filter(Model.id.in_(ids)).all()",
                        "code_snippet": line_str.strip()
                    })

            # Detect file open without context manager
            if re.search(r'=\s*open\s*\(', stripped) and not line_str.strip().startswith('with '):
                findings.append({
                    "agent_type": self.category.value,
                    "severity": SeverityLevel.MEDIUM.value,
                    "file_path": filename,
                    "line_number": idx,
                    "issue_title": "Unclosed File Resource / Potential Leak",
                    "description": "File handle opened without `with` context manager. May leak open file descriptors if exception occurs.",
                    "suggestion": "with open(filepath, 'r') as f:\n    data = f.read()",
                    "code_snippet": line_str.strip()
                })

            # Detect blocking sleep or requests in async code
            if chunk.chunk_type == "async_function":
                if "time.sleep(" in stripped:
                    findings.append({
                        "agent_type": self.category.value,
                        "severity": SeverityLevel.HIGH.value,
                        "file_path": filename,
                        "line_number": idx,
                        "issue_title": "Blocking `time.sleep()` in Async Function",
                        "description": "time.sleep() blocks the event loop thread for all concurrent requests.",
                        "suggestion": "import asyncio\nawait asyncio.sleep(...) # Safe non-blocking delay",
                        "code_snippet": line_str.strip()
                    })
                elif re.search(r'requests\.(get|post|put|delete)', stripped):
                    findings.append({
                        "agent_type": self.category.value,
                        "severity": SeverityLevel.MEDIUM.value,
                        "file_path": filename,
                        "line_number": idx,
                        "issue_title": "Synchronous Requests in Async Function",
                        "description": "Synchronous HTTP request blocks the async event loop thread.",
                        "suggestion": "import httpx\nasync with httpx.AsyncClient() as client:\n    res = await client.get(...)",
                        "code_snippet": line_str.strip()
                    })

        return findings
