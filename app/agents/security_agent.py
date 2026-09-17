import re
from typing import List, Dict, Any
from app.agents.base import BaseAgent
from app.models import AgentCategory, SeverityLevel
from app.schemas import ASTChunk

class SecurityAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="SecurityAgent", category=AgentCategory.SECURITY)

    def get_system_prompt(self) -> str:
        return """You are SecurityAgent, a world-class cybersecurity expert auditing pull request diffs.
Your job is to identify security vulnerabilities including:
1. Hardcoded secrets, API keys, passwords, bearer tokens, or private keys.
2. Injection risks: SQL Injection (string concatenation/formatting in queries), Command Injection (os.system, subprocess with shell=True), Path Traversal.
3. Unsafe functions & deserialization: eval(), exec(), pickle.loads(), yaml.load() without Loader=SafeLoader, tempfile.mktemp().
4. Weak cryptography: MD5/SHA1 usage for password hashing or tokens.

You MUST respond with a JSON array of objects.
JSON schema per object:
[
  {
    "line_number": <int>,
    "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW" | "INFO",
    "issue_title": "<Short clear title>",
    "description": "<Detailed explanation of the risk and attack vector>",
    "suggestion": "<Refactored safe code block>",
    "code_snippet": "<Offending code snippet>"
  }
]
If no security vulnerabilities are present, return an empty JSON array: [].
Do NOT include markdown wrapping or extra conversational text outside the JSON array."""

    def _analyze_rule_fallback(self, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        findings = []
        lines = chunk.code.splitlines()

        # Secret patterns
        secret_patterns = [
            (r'(?i)(api[_-]?key|secret|password|passwd|auth[_-]?token|private[_-]?key)\s*=\s*["\'][A-Za-z0-9_\-]{8,}["\']', "Hardcoded Secret / API Key Detected", SeverityLevel.CRITICAL),
            (r'-----BEGIN\s+(RSA|EC|OPENSSH|PRIVATE)\s+KEY-----', "Hardcoded Private Key", SeverityLevel.CRITICAL),
            (r'bearer\s+[a-zA-Z0-9_\-\.]{20,}', "Hardcoded Bearer Token", SeverityLevel.HIGH)
        ]

        # Injection & unsafe function patterns
        unsafe_patterns = [
            (r'eval\s*\(', "Use of Unsafe `eval()` Function", SeverityLevel.CRITICAL, "eval() executes arbitrary code. Replace with safe literal evaluation like ast.literal_eval()."),
            (r'exec\s*\(', "Use of Unsafe `exec()` Function", SeverityLevel.CRITICAL, "exec() executes arbitrary code dynamically."),
            (r'os\.system\s*\(', "Command Injection Risk (`os.system`)", SeverityLevel.HIGH, "Use subprocess.run with argument list instead of shell string execution."),
            (r'subprocess\.(Popen|run|call)\s*\(.*shell\s*=\s*True', "Command Injection Risk (`shell=True`)", SeverityLevel.HIGH, "Set shell=False and pass command as a list of strings."),
            (r'pickle\.loads\s*\(', "Insecure Deserialization (`pickle.loads`)", SeverityLevel.HIGH, "pickle can execute arbitrary code during unpickling. Use JSON or safe serialization."),
            (r'yaml\.load\s*\([^)]*$', "Insecure YAML Deserialization", SeverityLevel.HIGH, "Use yaml.safe_load() to prevent remote code execution."),
            (r'(?i)SELECT\s+.*\s+FROM\s+.*%s|SELECT\s+.*\s+FROM\s+.*\{\}', "SQL Injection via String Formatting", SeverityLevel.CRITICAL, "Use parameterized queries (e.g. cursor.execute('SELECT * FROM users WHERE id = %s', (user_id,)))"),
            (r'hashlib\.md5\s*\(', "Weak Hash Algorithm (MD5)", SeverityLevel.MEDIUM, "MD5 is cryptographically broken. Use SHA-256 or bcrypt for passwords.")
        ]

        for i, line_str in enumerate(lines, start=chunk.start_line):
            # Check secret patterns
            for pattern, title, severity in secret_patterns:
                if re.search(pattern, line_str):
                    findings.append({
                        "agent_type": self.category.value,
                        "severity": severity.value,
                        "file_path": filename,
                        "line_number": i,
                        "issue_title": title,
                        "description": f"Potential sensitive credentials or secret exposed directly in code at line {i}.",
                        "suggestion": "# Move credentials to environment variables\nimport os\napi_key = os.getenv('API_KEY')",
                        "code_snippet": line_str.strip()
                    })

            # Check unsafe execution patterns
            for item in unsafe_patterns:
                pattern = item[0]
                title = item[1]
                severity = item[2]
                desc = item[3] if len(item) > 3 else "Unsafe operation detected."
                
                if re.search(pattern, line_str):
                    findings.append({
                        "agent_type": self.category.value,
                        "severity": severity.value,
                        "file_path": filename,
                        "line_number": i,
                        "issue_title": title,
                        "description": desc,
                        "suggestion": f"# Refactor line {i} to use safe standard library methods",
                        "code_snippet": line_str.strip()
                    })

        return findings
