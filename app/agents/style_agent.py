import re
from typing import List, Dict, Any
from app.agents.base import BaseAgent
from app.models import AgentCategory, SeverityLevel
from app.schemas import ASTChunk

class StyleAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="StyleAgent", category=AgentCategory.STYLE)

    def get_system_prompt(self) -> str:
        return """You are StyleAgent, a Python code style guardian and maintainability expert.
Your job is to check code for:
1. PEP8 compliance & naming conventions (snake_case functions/vars, PascalCase classes, UPPERCASE constants).
2. Code readability, type hints, and clear documentation.
3. Bare `except:` clauses or swallowing exceptions silently.
4. Wildcard imports (`from module import *`).
5. Overly long, deeply nested, or unreadable functions.

You MUST respond with a JSON array of objects.
JSON schema per object:
[
  {
    "line_number": <int>,
    "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO",
    "issue_title": "<Short clear title>",
    "description": "<Explanation of style/readability issue>",
    "suggestion": "<Clean PEP8 compliant code>",
    "code_snippet": "<Offending code snippet>"
  }
]
If no style issues are present, return an empty JSON array: [].
Do NOT include markdown wrapping or extra conversational text outside the JSON array."""

    def _analyze_rule_fallback(self, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        findings = []
        lines = chunk.code.splitlines()

        # Check function naming / PEP8
        if chunk.chunk_type in ("function", "async_function"):
            if not re.match(r'^[a-z_][a-z0-9_]*$', chunk.name) and not chunk.name.startswith("__"):
                findings.append({
                    "agent_type": self.category.value,
                    "severity": SeverityLevel.LOW.value,
                    "file_path": filename,
                    "line_number": chunk.start_line,
                    "issue_title": f"PEP8 Naming Violation: `{chunk.name}`",
                    "description": f"Function name `{chunk.name}` should follow snake_case naming convention per PEP8.",
                    "suggestion": f"def {re.sub(r'([A-Z])', r'_\1', chunk.name).lower().lstrip('_')}(...):",
                    "code_snippet": lines[0] if lines else ""
                })

            # Check for function length (> 50 lines)
            if len(lines) > 50:
                findings.append({
                    "agent_type": self.category.value,
                    "severity": SeverityLevel.MEDIUM.value,
                    "file_path": filename,
                    "line_number": chunk.start_line,
                    "issue_title": f"Excessive Function Length ({len(lines)} lines)",
                    "description": f"Function `{chunk.name}` is {len(lines)} lines long. Break into smaller single-responsibility helper functions.",
                    "suggestion": "# Refactor into smaller sub-functions",
                    "code_snippet": lines[0] if lines else ""
                })

        for idx, line_str in enumerate(lines, start=chunk.start_line):
            stripped = line_str.strip()

            # Check wildcard import
            if re.search(r'from\s+[a-zA-Z0-9_\.]+\s+import\s+\*', stripped):
                findings.append({
                    "agent_type": self.category.value,
                    "severity": SeverityLevel.MEDIUM.value,
                    "file_path": filename,
                    "line_number": idx,
                    "issue_title": "Wildcard Import Used (`from module import *`)",
                    "description": "Wildcard imports pollute the local namespace and obscure variable origins.",
                    "suggestion": "from module import SpecificClass, specific_function",
                    "code_snippet": stripped
                })

            # Check bare except
            if re.search(r'except\s*:', stripped):
                findings.append({
                    "agent_type": self.category.value,
                    "severity": SeverityLevel.MEDIUM.value,
                    "file_path": filename,
                    "line_number": idx,
                    "issue_title": "Bare `except:` Clause",
                    "description": "Bare except catches system exit signals and KeyboardInterrupt. Catch specific exceptions instead.",
                    "suggestion": "except Exception as e:\n    logger.error(f'Error occurred: {e}')",
                    "code_snippet": stripped
                })

        return findings
