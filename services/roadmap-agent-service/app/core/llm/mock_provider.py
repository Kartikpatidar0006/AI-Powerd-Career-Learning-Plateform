"""
Mock LLM Provider for roadmap-agent-service.

Generates deterministic, schema-valid roadmaps and tasks without requiring
external API keys. Used for offline development and CI testing.

NOTE: This mock is intentionally duplicated from profile-agent-service for
service independence. See base.py for rationale.
"""

import json
import logging

from app.core.llm.base import BaseLLMProvider

logger = logging.getLogger("roadmap-agent.mock-llm")


class MockLLMProvider(BaseLLMProvider):
    """Deterministic Mock LLM Provider producing valid roadmap/task JSON."""

    def __init__(self, artificial_delay: float = 0.2) -> None:
        self.artificial_delay = artificial_delay

    async def generate_json(self, system_prompt: str, user_prompt: str) -> str:
        """
        Analyze the prompt and return deterministic, schema-valid JSON.

        Detects whether the request is for roadmap generation or task generation
        based on keywords in the system_prompt, and returns appropriate fixtures.
        """
        if self.artificial_delay > 0:
            import asyncio
            await asyncio.sleep(self.artificial_delay)

        logger.info("MockLLMProvider: Generating deterministic response (delay: %.2fs)", self.artificial_delay)

        prompt_lower = system_prompt.lower()

        if "roadmap" in prompt_lower and "milestone" in prompt_lower:
            return self._generate_roadmap(user_prompt)
        elif "task" in prompt_lower:
            return self._generate_task(user_prompt)
        # Fallback
        return json.dumps({"result": "mock"})

    def _generate_roadmap(self, user_prompt: str) -> str:
        """Generate a deterministic, schema-valid roadmap JSON."""
        prompt_lower = user_prompt.lower()

        # Detect target role from prompt for minimal personalization
        is_frontend = "frontend" in prompt_lower or "react" in prompt_lower
        is_data = "data" in prompt_lower or "ml" in prompt_lower
        role = "Frontend Developer" if is_frontend else ("Data Engineer" if is_data else "Full Stack Engineer")

        milestones = [
            {
                "order": 1,
                "title": "Foundations & Environment Setup",
                "description": f"Establish a solid foundation for {role} by setting up development tooling and reviewing core CS fundamentals.",
                "target_skills": ["Git & GitHub", "Linux CLI", "VS Code"],
                "estimated_days": 10,
                "difficulty_band": 1,
                "success_criteria": [
                    "Create and manage a Git repository with branches and pull requests",
                    "Configure a professional local dev environment"
                ]
            },
            {
                "order": 2,
                "title": "Core Language Proficiency",
                "description": "Master the primary programming language required for the target role with idiomatic patterns.",
                "target_skills": ["Python" if not is_frontend else "JavaScript", "Data Structures & Algorithms"],
                "estimated_days": 15,
                "difficulty_band": 2,
                "success_criteria": [
                    "Implement common data structures from scratch",
                    "Solve 10 algorithm challenges with documented complexity analysis"
                ]
            },
            {
                "order": 3,
                "title": "Framework & Tooling Mastery",
                "description": "Build functional projects using the primary framework for the target role.",
                "target_skills": ["FastAPI" if not is_frontend else "React", "REST APIs"],
                "estimated_days": 20,
                "difficulty_band": 2,
                "success_criteria": [
                    "Build a fully functional CRUD application with proper error handling",
                    "Write unit and integration tests with >80% coverage"
                ]
            },
            {
                "order": 4,
                "title": "Database Design & Persistence",
                "description": "Design normalized relational schemas and implement async database interactions.",
                "target_skills": ["PostgreSQL", "SQLAlchemy", "Database Design"],
                "estimated_days": 12,
                "difficulty_band": 3,
                "success_criteria": [
                    "Design and migrate a multi-table normalized schema",
                    "Implement async CRUD operations with connection pooling"
                ]
            },
            {
                "order": 5,
                "title": "System Integration & API Design",
                "description": "Design and build production-quality APIs with authentication, validation, and documentation.",
                "target_skills": ["API Security", "JWT Authentication", "OpenAPI"],
                "estimated_days": 15,
                "difficulty_band": 3,
                "success_criteria": [
                    "Implement JWT-based auth with refresh token rotation",
                    "Document all API endpoints with OpenAPI/Swagger specs"
                ]
            },
            {
                "order": 6,
                "title": "DevOps & Containerization",
                "description": "Containerize applications and set up basic CI/CD pipelines.",
                "target_skills": ["Docker", "Docker Compose", "CI/CD Pipelines"],
                "estimated_days": 10,
                "difficulty_band": 4,
                "success_criteria": [
                    "Containerize an application with multi-stage Dockerfile",
                    "Configure a GitHub Actions CI pipeline with automated tests"
                ]
            },
            {
                "order": 7,
                "title": "Production Readiness & Observability",
                "description": "Add structured logging, health checks, metrics, and performance profiling.",
                "target_skills": ["Structured Logging", "Health Checks", "Performance Optimization"],
                "estimated_days": 10,
                "difficulty_band": 4,
                "success_criteria": [
                    "Implement structured JSON logging with correlation IDs",
                    "Add health check endpoints and basic Prometheus metrics"
                ]
            },
            {
                "order": 8,
                "title": "Capstone: Real-World Portfolio Project",
                "description": "Build a complete, deployable, production-quality project showcasing all acquired skills.",
                "target_skills": ["System Design", "Technical Documentation", "Code Review"],
                "estimated_days": 20,
                "difficulty_band": 5,
                "success_criteria": [
                    "Deploy a complete application with CI/CD to a cloud provider",
                    "Write comprehensive README and architecture documentation"
                ]
            }
        ]

        return json.dumps({"milestones": milestones})

    def _generate_task(self, user_prompt: str) -> str:
        """Generate a deterministic, schema-valid task JSON."""
        prompt_lower = user_prompt.lower()

        # Detect milestone context
        milestone_title = "Core Development"
        if "foundation" in prompt_lower or "setup" in prompt_lower:
            if "git repository management" in prompt_lower:
                milestone_title = "Foundations & Environment Setup"
                title = "Linux CLI Automation & Environment Tooling"
                description = "Develop an automated command-line workflow script in Python to streamline project initialization and testing."
                requirements = [
                    "1. Write a CLI automation script for project scaffolding and checks",
                    "2. Parse arguments and handle environment flags with argparse",
                    "3. Ensure clean exit codes and error messages",
                    "4. Add unit tests covering argument parsing and script execution"
                ]
                acceptance_criteria = [
                    "Script executes without error on standard environments",
                    "Arguments are validated with descriptive help messages",
                    "Tests pass with 100% success rate"
                ]
                skills_targeted = ["Linux CLI", "Python", "Automation"]
            else:
                milestone_title = "Foundations & Environment Setup"
                title = "Git Repository Management & Branching Workflow"
                description = "Practice professional Git workflows by creating a repository, implementing a feature with proper branching, and submitting a pull request."
                requirements = [
                    "1. Initialize a new Git repository for a sample Python project",
                    "2. Create a 'develop' branch from main",
                    "3. Add a Python script that computes the Fibonacci sequence iteratively",
                    "4. Commit with conventional commit messages (feat:, fix:, docs:)",
                    "5. Create a pull request and document the changes in a CHANGELOG.md"
                ]
                acceptance_criteria = [
                    "Repository is public on GitHub with at least 5 meaningful commits",
                    "Branching strategy is documented in README.md",
                    "CHANGELOG.md follows Keep a Changelog format",
                    "Python script is PEP8 compliant and includes docstrings"
                ]
                skills_targeted = ["Git & GitHub", "Linux CLI", "Technical Documentation"]
        elif "database" in prompt_lower:
            title = "Async PostgreSQL Schema Design & CRUD Implementation"
            description = "Design a normalized database schema and implement full async CRUD operations using SQLAlchemy 2.0."
            requirements = [
                "1. Design a 3-table normalized schema (users, posts, tags) with proper FK relationships",
                "2. Write Alembic migrations for the schema",
                "3. Implement async SQLAlchemy CRUD operations for each table",
                "4. Add proper indexing on frequently queried columns",
                "5. Write pytest integration tests covering all CRUD paths"
            ]
            acceptance_criteria = [
                "Schema is in 3NF with documented relationships",
                "Migrations are reversible (upgrade and downgrade)",
                "All CRUD operations use async/await correctly",
                "Test coverage > 85% for database layer"
            ]
            skills_targeted = ["PostgreSQL", "SQLAlchemy", "Database Design"]
        else:
            title = "RESTful API with FastAPI: CRUD Endpoints & Pydantic Validation"
            description = "Build a production-quality REST API with FastAPI implementing full CRUD for a resource, with proper validation, error handling, and OpenAPI documentation."
            requirements = [
                "1. Create FastAPI application with a 'Task' resource (CRUD endpoints)",
                "2. Implement Pydantic v2 request/response schemas with field validators",
                "3. Add proper HTTP status codes and error responses for all cases",
                "4. Configure CORS for frontend access",
                "5. Write pytest tests using TestClient covering all endpoints and edge cases"
            ]
            acceptance_criteria = [
                "All 5 CRUD endpoints return correct status codes",
                "Invalid input returns 422 with descriptive errors",
                "OpenAPI docs are accessible at /docs",
                "Test suite passes with 0 failures and covers error paths"
            ]
            skills_targeted = ["FastAPI", "REST APIs", "Pydantic"]

        task = {
            "title": title,
            "description": description,
            "requirements": requirements,
            "acceptance_criteria": acceptance_criteria,
            "skills_targeted": skills_targeted,
            "estimated_hours": 6.0,
            "starter_hint": f"Start by reviewing the milestone objectives for '{milestone_title}'. Structure your code in clear modules before writing tests."
        }
        return json.dumps(task)
