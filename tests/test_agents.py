import pytest
from app.agents.security_agent import SecurityAgent
from app.agents.performance_agent import PerformanceAgent
from app.agents.style_agent import StyleAgent
from app.services.review_engine import MultiAgentReviewEngine
from app.schemas import ASTChunk

def test_security_agent_detects_secret_and_eval():
    agent = SecurityAgent()
    chunk = ASTChunk(
        chunk_type="function",
        name="test_fn",
        start_line=1,
        end_line=5,
        code='def run():\n    API_KEY = "sk_live_1234567890123456"\n    eval("1+1")'
    )
    findings = agent._analyze_rule_fallback(chunk, "test.py")
    titles = [f["issue_title"] for f in findings]
    
    assert any("Secret" in t for t in titles)
    assert any("eval" in t for t in titles)

def test_performance_agent_detects_nested_loop():
    agent = PerformanceAgent()
    chunk = ASTChunk(
        chunk_type="function",
        name="test_loop",
        start_line=1,
        end_line=8,
        code='def loop():\n    for i in list1:\n        for j in list2:\n            print(i, j)'
    )
    findings = agent._analyze_rule_fallback(chunk, "test.py")
    assert any("O(N^2)" in f["issue_title"] for f in findings)

def test_style_agent_detects_wildcard_import():
    agent = StyleAgent()
    chunk = ASTChunk(
        chunk_type="module_level",
        name="imports",
        start_line=1,
        end_line=2,
        code='from os import *'
    )
    findings = agent._analyze_rule_fallback(chunk, "test.py")
    assert any("Wildcard Import" in f["issue_title"] for f in findings)

def test_review_engine_severity_score_calculation():
    findings = [
        {"severity": "CRITICAL"},
        {"severity": "HIGH"},
        {"severity": "MEDIUM"}
    ]
    score = MultiAgentReviewEngine.calculate_severity_score(findings)
    assert score == 56.0 # 30 + 18 + 8 = 56
