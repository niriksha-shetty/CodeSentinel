import json
import logging
import re
from typing import List, Dict, Any, Optional
from app.config import settings
from app.models import SeverityLevel, AgentCategory
from app.schemas import ASTChunk

logger = logging.getLogger(__name__)

class BaseAgent:
    def __init__(self, name: str, category: AgentCategory):
        self.name = name
        self.category = category
        self.provider = settings.ai_provider
        self.gemini_key = settings.gemini_api_key
        self.openai_key = settings.openai_api_key

    def get_system_prompt(self) -> str:
        raise NotImplementedError("Subclasses must implement get_system_prompt()")

    def analyze_chunk(self, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        """
        Analyzes a single AST chunk. Calls LLM if API key is configured,
        or uses rule-based heuristic fallback if offline/mock mode.
        """
        if self.provider == "gemini" and self.gemini_key:
            return self._analyze_gemini(chunk, filename)
        elif self.provider == "openai" and self.openai_key:
            return self._analyze_openai(chunk, filename)
        else:
            return self._analyze_rule_fallback(chunk, filename)

    def _analyze_gemini(self, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        """Invokes Gemini API for code review pass."""
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_key)
            
            prompt = f"{self.get_system_prompt()}\n\n"
            prompt += f"Filename: {filename}\nChunk Type: {chunk.chunk_type}\nChunk Name: {chunk.name}\n"
            prompt += f"Start Line: {chunk.start_line}, End Line: {chunk.end_line}\n\n"
            prompt += f"Code to review:\n```\n{chunk.code}\n```\n\n"
            prompt += "Respond ONLY with a valid JSON array of objects following the specified JSON schema."

            response = client.models.generate_content(
                model=settings.gemini_model,
                contents=prompt,
            )
            return self._parse_json_response(response.text, chunk, filename)
        except Exception as e:
            logger.error(f"Gemini API error in {self.name}: {e}. Falling back to heuristic analysis.")
            return self._analyze_rule_fallback(chunk, filename)

    def _analyze_openai(self, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        """Invokes OpenAI API for code review pass."""
        try:
            import openai
            client = openai.OpenAI(api_key=self.openai_key)
            
            prompt = f"Filename: {filename}\nChunk Name: {chunk.name}\nStart Line: {chunk.start_line}\nCode:\n```\n{chunk.code}\n```"

            response = client.chat.completions.create(
                model=settings.openai_model,
                messages=[
                    {"role": "system", "content": self.get_system_prompt()},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2
            )
            content = response.choices[0].message.content or "[]"
            return self._parse_json_response(content, chunk, filename)
        except Exception as e:
            logger.error(f"OpenAI API error in {self.name}: {e}. Falling back to heuristic analysis.")
            return self._analyze_rule_fallback(chunk, filename)

    def _parse_json_response(self, text: str, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        """Parses JSON array returned by LLM prompt."""
        text = text.strip()
        # Clean markdown code blocks if wrapped
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()

        try:
            findings = json.loads(text)
            if not isinstance(findings, list):
                return []
            
            parsed = []
            for f in findings:
                parsed.append({
                    "agent_type": self.category.value,
                    "severity": f.get("severity", "MEDIUM").upper(),
                    "file_path": filename,
                    "line_number": int(f.get("line_number", chunk.start_line)),
                    "issue_title": f.get("issue_title", f"{self.name} Issue"),
                    "description": f.get("description", "Code anomaly detected."),
                    "suggestion": f.get("suggestion", ""),
                    "code_snippet": f.get("code_snippet", chunk.code[:200])
                })
            return parsed
        except Exception as e:
            logger.warning(f"Failed to parse LLM JSON output in {self.name}: {e}")
            return []

    def _analyze_rule_fallback(self, chunk: ASTChunk, filename: str) -> List[Dict[str, Any]]:
        """Must be implemented by concrete agent classes for fallback rule-based analysis."""
        return []
