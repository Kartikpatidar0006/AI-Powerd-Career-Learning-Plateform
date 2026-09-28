"""
Mock LLM Provider for local development and offline testing.

Analyzes raw text using intelligent keyword extraction and semantic heuristic
categorization, producing valid JSON matching StructuredSkillsOutput schema
without requiring an external API key or internet access.
"""

import json
import logging
import re
from app.core.llm.base import BaseLLMProvider

logger = logging.getLogger("profile-agent.mock-llm")

# Knowledge base of common skills, their standard categories, and default proficiency levels
SKILL_KNOWLEDGE_BASE = [
    # Languages
    (r"\bpython\b", "Python", "Languages", "intermediate"),
    (r"\bjavascript\b|\bjs\b", "JavaScript", "Languages", "intermediate"),
    (r"\btypescript\b|\bts\b", "TypeScript", "Languages", "intermediate"),
    (r"\bjava\b", "Java", "Languages", "intermediate"),
    (r"\bc\+\+\b", "C++", "Languages", "intermediate"),
    (r"\bgolang\b|\bgo\b", "Go", "Languages", "beginner"),
    (r"\brust\b", "Rust", "Languages", "beginner"),
    (r"\bsql\b", "SQL", "Databases", "intermediate"),
    (r"\bhtml(?:5)?\b", "HTML5", "Frontend", "advanced"),
    (r"\bcss(?:3)?\b", "CSS3", "Frontend", "intermediate"),
    # Frontend
    (r"\breact(?:\.js)?\b", "React", "Frontend", "intermediate"),
    (r"\bnext(?:\.js)?\b", "Next.js", "Frontend", "intermediate"),
    (r"\bvue(?:\.js)?\b", "Vue.js", "Frontend", "beginner"),
    (r"\btailwind(?:css)?\b", "Tailwind CSS", "Frontend", "intermediate"),
    (r"\bredux\b", "Redux", "Frontend", "intermediate"),
    # Backend
    (r"\bnode(?:\.js)?\b", "Node.js", "Backend", "intermediate"),
    (r"\bfastapi\b", "FastAPI", "Backend", "intermediate"),
    (r"\bexpress(?:\.js)?\b", "Express", "Backend", "intermediate"),
    (r"\bdjango\b", "Django", "Backend", "intermediate"),
    (r"\bflask\b", "Flask", "Backend", "intermediate"),
    (r"\bspring(?:boot)?\b", "Spring Boot", "Backend", "beginner"),
    (r"\brest(?:ful)?(?:\s*api[s]?)?\b", "REST APIs", "Backend", "intermediate"),
    (r"\bgraphql\b", "GraphQL", "Backend", "beginner"),
    # Databases
    (r"\bpostgres(?:ql)?\b", "PostgreSQL", "Databases", "intermediate"),
    (r"\bmongo(?:db)?\b", "MongoDB", "Databases", "intermediate"),
    (r"\bmysql\b", "MySQL", "Databases", "intermediate"),
    (r"\bredis\b", "Redis", "Databases", "beginner"),
    # DevOps & Cloud
    (r"\bdocker\b", "Docker", "DevOps & Cloud", "intermediate"),
    (r"\bkubernetes|\bk8s\b", "Kubernetes", "DevOps & Cloud", "beginner"),
    (r"\baws\b|\bamazon web services\b", "AWS", "DevOps & Cloud", "beginner"),
    (r"\bgit\b|\bgithub\b", "Git & GitHub", "DevOps & Cloud", "intermediate"),
    (r"\bci[\/\-]cd\b", "CI/CD Pipelines", "DevOps & Cloud", "beginner"),
    # AI / Data
    (r"\bmachine learning\b|\bml\b", "Machine Learning", "AI & Data", "intermediate"),
    (r"\bdeep learning\b", "Deep Learning", "AI & Data", "beginner"),
    (r"\bpytorch\b", "PyTorch", "AI & Data", "beginner"),
    (r"\btensorflow\b", "TensorFlow", "AI & Data", "beginner"),
    (r"\bpandas\b", "Pandas", "AI & Data", "intermediate"),
    (r"\bnumpy\b", "NumPy", "AI & Data", "intermediate"),
    # Core CS
    (r"\bdsa\b|\bdata structures\b", "Data Structures & Algorithms", "Core CS", "intermediate"),
    (r"\boop\b|\bobject oriented\b", "Object-Oriented Programming", "Core CS", "intermediate"),
    (r"\bsystem design\b", "System Design", "Core CS", "beginner"),
]


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM Provider for testing and offline environments."""

    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """Parse prompts and heuristically extract skills as structured JSON."""
        logger.info("MockLLMProvider: Generating simulated skills extraction")
        text = user_prompt.lower()

        extracted_skills = []
        seen_names = set()

        # Check for target role to boost relevant core skills
        is_frontend = "front" in text
        is_backend = "back" in text
        is_ai = "data" in text or "ml" in text or "ai" in text
        is_2plus = "2+yrs" in text or "2+ yrs" in text or "2 years" in text

        for pattern, name, category, default_prof in SKILL_KNOWLEDGE_BASE:
            if re.search(pattern, text, re.IGNORECASE):
                prof = default_prof
                conf = 0.88
                if is_2plus and prof == "intermediate":
                    prof = "advanced"
                    conf = 0.94
                extracted_skills.append({
                    "skill_name": name,
                    "category": category,
                    "proficiency_level": prof,
                    "confidence_score": conf,
                })
                seen_names.add(name)

        # Ensure at least 4 default foundational skills matching target context
        defaults = []
        if is_ai:
            defaults = [
                {"skill_name": "Python", "category": "Languages", "proficiency_level": "intermediate", "confidence_score": 0.90},
                {"skill_name": "Pandas", "category": "AI & Data", "proficiency_level": "intermediate", "confidence_score": 0.85},
                {"skill_name": "SQL", "category": "Databases", "proficiency_level": "beginner", "confidence_score": 0.80},
                {"skill_name": "Git & GitHub", "category": "DevOps & Cloud", "proficiency_level": "intermediate", "confidence_score": 0.85},
            ]
        elif is_frontend:
            defaults = [
                {"skill_name": "JavaScript", "category": "Languages", "proficiency_level": "intermediate", "confidence_score": 0.90},
                {"skill_name": "React", "category": "Frontend", "proficiency_level": "intermediate", "confidence_score": 0.88},
                {"skill_name": "CSS3", "category": "Frontend", "proficiency_level": "intermediate", "confidence_score": 0.85},
                {"skill_name": "Git & GitHub", "category": "DevOps & Cloud", "proficiency_level": "intermediate", "confidence_score": 0.85},
            ]
        else:  # Full Stack / Backend / Default
            defaults = [
                {"skill_name": "Python", "category": "Languages", "proficiency_level": "intermediate", "confidence_score": 0.90},
                {"skill_name": "FastAPI", "category": "Backend", "proficiency_level": "intermediate", "confidence_score": 0.88},
                {"skill_name": "PostgreSQL", "category": "Databases", "proficiency_level": "intermediate", "confidence_score": 0.85},
                {"skill_name": "Git & GitHub", "category": "DevOps & Cloud", "proficiency_level": "intermediate", "confidence_score": 0.85},
                {"skill_name": "REST APIs", "category": "Backend", "proficiency_level": "intermediate", "confidence_score": 0.89},
            ]

        for item in defaults:
            if item["skill_name"] not in seen_names:
                extracted_skills.append(item)
                seen_names.add(item["skill_name"])

        return json.dumps({"skills": extracted_skills})
