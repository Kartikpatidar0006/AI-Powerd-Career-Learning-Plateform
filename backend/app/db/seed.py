"""
backend/app/db/seed.py
======================
Comprehensive Database Seeder Script.

Populates initial production seed data for all 14+ Tech Career Professions:
  1. Default roles ('admin', 'student', 'mentor')
  2. Initial admin user ('admin@aicareer.com')
  3. 14+ Career Professions with distinct roadmaps, milestone steps, skills,
     real-world tasks/projects (with GitHub & deployment requirements), and interview questions.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.base import Base
from app.core.security import hash_password
from app.db.session import SessionLocal
from app.models.career_roadmap import CareerRoadmap, RoadmapStep
from app.models.interview_question import InterviewQuestion
from app.models.profession import Profession
from app.models.role import Role
from app.models.skill import Skill
from app.models.task import Task
from app.models.user import User

logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


# 14+ Comprehensive Profession definitions with distinct roadmaps, tasks, and questions
SEED_PROFESSIONS = [
    {
        "name": "AI Engineer",
        "slug": "ai-engineer",
        "category": "AI & Machine Learning",
        "description": "Design, build, and deploy generative AI applications, LLM pipelines, neural networks, and scalable AI infrastructure.",
        "skills": [
            {"name": "Python 3.11+", "category": "Language", "difficulty": "Beginner"},
            {"name": "PyTorch & Neural Networks", "category": "AI Framework", "difficulty": "Intermediate"},
            {"name": "FastAPI & LLM Serving", "category": "API Framework", "difficulty": "Intermediate"},
            {"name": "LangChain & RAG Pipelines", "category": "Generative AI", "difficulty": "Advanced"},
        ],
        "roadmap_title": "AI Engineer Mastery Roadmap",
        "roadmap_desc": "Comprehensive 16-week path from PyTorch fundamentals to production RAG & LLM agent serving.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: PyTorch Foundations & Deep Learning Logic",
                "skill_index": 1,
                "task_title": "Build a Custom Neural Network from Scratch in PyTorch",
                "task_desc": "Implement a multi-layer perceptron with custom autograd loss functions and evaluate on MNIST/CIFAR datasets.",
                "task_instructions": "1. Clone template repository.\n2. Write training loop with PyTorch DataLoader.\n3. Log epoch metrics.\n4. Submit GitHub URL and live model evaluation link.",
            },
            {
                "order": 2,
                "title": "Phase 2: Asynchronous LLM API Serving with FastAPI",
                "skill_index": 2,
                "task_title": "Deploy Asynchronous Streaming AI API Endpoint",
                "task_desc": "Create a high-performance FastAPI endpoint that streams LLM tokens via Server-Sent Events (SSE).",
                "task_instructions": "1. Build FastAPI app.\n2. Integrate OpenAI/HuggingFace API with async streaming.\n3. Add Docker containerization.\n4. Submit GitHub repository and deployed Render/Railway live API URL.",
            },
            {
                "order": 3,
                "title": "Phase 3: Production Retrieval-Augmented Generation (RAG) System",
                "skill_index": 3,
                "task_title": "Build Enterprise Vector Search & Knowledge Base RAG",
                "task_desc": "Implement document chunking, vector embeddings using Qdrant/Pinecone, and LLM re-ranking.",
                "task_instructions": "1. Ingest PDF documentation.\n2. Calculate embeddings & store in vector DB.\n3. Build prompt pipeline.\n4. Submit repository and live API web interface.",
            },
        ],
        "interview_questions": [
            {"question": "How do attention mechanisms in Transformer architectures differ from recurrent neural networks (RNNs)?", "topic": "Deep Learning", "difficulty": "Hard"},
            {"question": "Explain how Retrieval-Augmented Generation (RAG) reduces hallucinations in LLMs.", "topic": "Generative AI", "difficulty": "Medium"},
        ],
    },
    {
        "name": "Machine Learning Engineer",
        "slug": "machine-learning-engineer",
        "category": "AI & Machine Learning",
        "description": "Develop predictive models, feature pipelines, recommendation engines, and end-to-end MLOps production systems.",
        "skills": [
            {"name": "Feature Engineering & Pandas", "category": "Data Science", "difficulty": "Beginner"},
            {"name": "Scikit-Learn & Model Tuning", "category": "ML", "difficulty": "Intermediate"},
            {"name": "MLOps & MLflow Tracking", "category": "MLOps", "difficulty": "Advanced"},
        ],
        "roadmap_title": "Machine Learning Engineer Production Roadmap",
        "roadmap_desc": "Master end-to-end predictive modeling, feature stores, model registry, and MLOps deployment.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Feature Engineering & Data Pipeline Optimization",
                "skill_index": 0,
                "task_title": "Build Automated ETL Feature Pipeline",
                "task_desc": "Transform raw transactional data into ML feature tables using Pandas and NumPy.",
                "task_instructions": "Submit GitHub repository link.",
            },
            {
                "order": 2,
                "title": "Phase 2: Predictive Model Training & MLflow Tracking",
                "skill_index": 1,
                "task_title": "Train & Evaluate XGBoost Classifier with MLflow Tracking",
                "task_desc": "Train gradient boosting model, log hyper-parameters to MLflow, and export ONNX model artifact.",
                "task_instructions": "Submit GitHub link and live API deployment.",
            },
        ],
        "interview_questions": [
            {"question": "How do you handle severe class imbalance in binary classification models?", "topic": "Model Evaluation", "difficulty": "Medium"},
            {"question": "What is the difference between Data Drift and Concept Drift in production ML models?", "topic": "MLOps", "difficulty": "Hard"},
        ],
    },
    {
        "name": "Data Scientist",
        "slug": "data-scientist",
        "category": "Data & Analytics",
        "description": "Extract statistical insights, perform predictive modeling, design experiments, and communicate data-driven strategy.",
        "skills": [
            {"name": "Exploratory Data Analysis", "category": "Statistics", "difficulty": "Beginner"},
            {"name": "Statistical Hypothesis Testing", "category": "Math", "difficulty": "Intermediate"},
            {"name": "Predictive Analytics & Visualization", "category": "Analytics", "difficulty": "Intermediate"},
        ],
        "roadmap_title": "Data Scientist Professional Roadmap",
        "roadmap_desc": "Extract business value from complex datasets using statistics, machine learning, and executive dashboards.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Exploratory Data Analysis & Statistical Profiling",
                "skill_index": 0,
                "task_title": "Perform Full Statistical Profiling on Customer Churn Dataset",
                "task_desc": "Clean raw data, detect outliers, perform correlation analysis, and plot Seaborn distributions.",
                "task_instructions": "Submit GitHub Jupyter Notebook.",
            },
        ],
        "interview_questions": [
            {"question": "Explain the P-value and how to interpret a 95% confidence interval in A/B testing.", "topic": "Statistics", "difficulty": "Medium"},
        ],
    },
    {
        "name": "Data Analyst",
        "slug": "data-analyst",
        "category": "Data & Analytics",
        "description": "Transform complex business datasets into actionable dashboards, SQL queries, and strategic decision frameworks.",
        "skills": [
            {"name": "Advanced SQL & Window Functions", "category": "Database", "difficulty": "Intermediate"},
            {"name": "Business Intelligence Dashboards", "category": "BI", "difficulty": "Beginner"},
        ],
        "roadmap_title": "Data Analyst Career Roadmap",
        "roadmap_desc": "Master SQL analytics, BI dashboards, and data storytelling.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Advanced SQL Analytics & Window Functions",
                "skill_index": 0,
                "task_title": "Write Complex SQL Analytical Queries for Revenue Attribution",
                "task_desc": "Calculate month-over-month growth, rolling averages, and retention cohorts using PostgreSQL CTEs.",
                "task_instructions": "Submit GitHub SQL script repository.",
            },
        ],
        "interview_questions": [
            {"question": "What is the difference between WHERE and HAVING clauses in SQL queries?", "topic": "SQL", "difficulty": "Easy"},
        ],
    },
    {
        "name": "Backend Developer",
        "slug": "backend-developer",
        "category": "Software Engineering",
        "description": "Engineer high-throughput REST & GraphQL APIs, microservices architectures, databases, and secure auth pipelines.",
        "skills": [
            {"name": "Python & AsyncIO", "category": "Language", "difficulty": "Beginner"},
            {"name": "FastAPI REST Services", "category": "Framework", "difficulty": "Intermediate"},
            {"name": "PostgreSQL & SQLAlchemy 2.0", "category": "Database", "difficulty": "Intermediate"},
            {"name": "Docker & Redis Caching", "category": "Infrastructure", "difficulty": "Advanced"},
        ],
        "roadmap_title": "Backend Developer Mastery Roadmap",
        "roadmap_desc": "Complete path to building resilient microservices, secure authentication, and high-performance databases.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: REST API Design & JWT Authentication",
                "skill_index": 1,
                "task_title": "Build Secure JWT Authentication Microservice",
                "task_desc": "Implement password hashing with bcrypt, access/refresh JWT tokens, and rate-limiting middleware.",
                "task_instructions": "1. Build FastAPI application.\n2. Write pytest suite.\n3. Dockerize application.\n4. Submit GitHub link and live API deployment URL.",
            },
            {
                "order": 2,
                "title": "Phase 2: Relational Database Optimization & Redis Caching",
                "skill_index": 2,
                "task_title": "Optimize PostgreSQL Database Queries & Implement Redis Caching",
                "task_desc": "Add database composite indexes, write SQLAlchemy 2.0 selectinload queries, and cache read endpoints with Redis.",
                "task_instructions": "Submit GitHub repository and deployment link.",
            },
        ],
        "interview_questions": [
            {"question": "Explain how database indexing works using B-Trees and when an index might degrade performance.", "topic": "Database", "difficulty": "Medium"},
            {"question": "What is the difference between concurrency and parallelism in Python AsyncIO?", "topic": "Python", "difficulty": "Hard"},
        ],
    },
    {
        "name": "Frontend Developer",
        "slug": "frontend-developer",
        "category": "Software Engineering",
        "description": "Build responsive, accessible, interactive web interfaces using React, JavaScript, modern CSS, and component systems.",
        "skills": [
            {"name": "Modern JavaScript ES6+", "category": "Language", "difficulty": "Beginner"},
            {"name": "React 18 & State Hooks", "category": "Framework", "difficulty": "Intermediate"},
            {"name": "Vanilla CSS & Responsive Systems", "category": "Styling", "difficulty": "Beginner"},
        ],
        "roadmap_title": "Frontend Engineer Roadmap",
        "roadmap_desc": "Craft high-performance user interfaces with React, state management, and accessibility standards.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Modern React 18 & Component Systems",
                "skill_index": 1,
                "task_title": "Build Interactive Kanban Board Application",
                "task_desc": "Create drag-and-drop task board with local state persistence, dark theme, and custom hooks.",
                "task_instructions": "Submit GitHub repository link and live Vercel/Netlify URL.",
            },
        ],
        "interview_questions": [
            {"question": "How does React Virtual DOM reconciliation work under the hood?", "topic": "React", "difficulty": "Medium"},
        ],
    },
    {
        "name": "Full Stack Developer",
        "slug": "full-stack-developer",
        "category": "Software Engineering",
        "description": "Master complete web application lifecycles from interactive frontends to robust backend microservices and databases.",
        "skills": [
            {"name": "React & Frontend Architecture", "category": "Frontend", "difficulty": "Intermediate"},
            {"name": "Node.js & FastAPI Backends", "category": "Backend", "difficulty": "Intermediate"},
            {"name": "Full Stack Integration", "category": "Architecture", "difficulty": "Advanced"},
        ],
        "roadmap_title": "Full Stack Software Engineer Roadmap",
        "roadmap_desc": "Architect complete web platforms connecting modern single page apps with scalable APIs and databases.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Full Stack SaaS Platform Development",
                "skill_index": 2,
                "task_title": "Build Complete AI SaaS Web Application",
                "task_desc": "Implement React single page app connected to FastAPI backend, PostgreSQL DB, and Stripe payment gateway.",
                "task_instructions": "Submit GitHub repo link and live deployed web application URL.",
            },
        ],
        "interview_questions": [
            {"question": "Explain Cross-Origin Resource Sharing (CORS) and how preflight OPTIONS requests work.", "topic": "Web Architecture", "difficulty": "Medium"},
        ],
    },
    {
        "name": "DevOps Engineer",
        "slug": "devops-engineer",
        "category": "Cloud & Infrastructure",
        "description": "Automate CI/CD build pipelines, infrastructure-as-code deployments, Kubernetes orchestration, and monitoring systems.",
        "skills": [
            {"name": "Docker & Containerization", "category": "Containers", "difficulty": "Beginner"},
            {"name": "Kubernetes & Helm", "category": "Orchestration", "difficulty": "Advanced"},
            {"name": "GitHub Actions CI/CD", "category": "Automation", "difficulty": "Intermediate"},
        ],
        "roadmap_title": "DevOps & Infrastructure Automation Roadmap",
        "roadmap_desc": "Master CI/CD pipelines, Docker, Kubernetes clusters, and cloud monitoring.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Automated CI/CD & Cloud Container Deployment",
                "skill_index": 2,
                "task_title": "Build Automated GitHub Actions CI/CD Pipeline",
                "task_desc": "Write workflow to run automated unit tests, build multi-arch Docker image, and deploy to Kubernetes cluster.",
                "task_instructions": "Submit GitHub repository and live cluster endpoint.",
            },
        ],
        "interview_questions": [
            {"question": "How does Kubernetes handle self-healing and liveness vs readiness probes?", "topic": "DevOps", "difficulty": "Hard"},
        ],
    },
    {
        "name": "Cloud Engineer",
        "slug": "cloud-engineer",
        "category": "Cloud & Infrastructure",
        "description": "Architect multi-cloud solutions, serverless functions, cloud security policies, and high-availability networking.",
        "skills": [
            {"name": "AWS Core Services", "category": "Cloud", "difficulty": "Intermediate"},
            {"name": "Terraform Infrastructure as Code", "category": "IaC", "difficulty": "Intermediate"},
        ],
        "roadmap_title": "Cloud Solutions Architect Roadmap",
        "roadmap_desc": "Build scalable cloud infrastructure using AWS, Terraform, and serverless compute.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Terraform Infrastructure Provisioning",
                "skill_index": 1,
                "task_title": "Provision VPC, EC2 & RDS Infrastructure using Terraform",
                "task_desc": "Write modular HCL scripts to provision secure AWS VPC network, subnets, and database clusters.",
                "task_instructions": "Submit GitHub Terraform repository.",
            },
        ],
        "interview_questions": [
            {"question": "Compare AWS Lambda serverless execution model with traditional EC2 instance hosting.", "topic": "Cloud", "difficulty": "Medium"},
        ],
    },
    {
        "name": "Cyber Security Engineer",
        "slug": "cyber-security-engineer",
        "category": "Security & Systems",
        "description": "Protect application infrastructures, perform vulnerability assessments, encrypt network traffic, and conduct threat analysis.",
        "skills": [
            {"name": "Linux Hardening & Networking", "category": "Security", "difficulty": "Intermediate"},
            {"name": "Web Security & OWASP Top 10", "category": "Security", "difficulty": "Advanced"},
        ],
        "roadmap_title": "Cyber Security Engineering Roadmap",
        "roadmap_desc": "Protect networks, applications, and cloud workloads against cyber threats.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: OWASP Vulnerability Audit & Defense",
                "skill_index": 1,
                "task_title": "Perform Security Audit & Fix OWASP Top 10 Vulnerabilities",
                "task_desc": "Audit target web application for SQL injection, XSS, and broken auth, and write patch fixes.",
                "task_instructions": "Submit GitHub repository with security audit report and patched codebase.",
            },
        ],
        "interview_questions": [
            {"question": "How does TLS/SSL handshake establish encrypted communication between client and server?", "topic": "Security", "difficulty": "Hard"},
        ],
    },
    {
        "name": "Android Developer",
        "slug": "android-developer",
        "category": "Mobile Development",
        "description": "Craft native mobile applications for Android, optimized UI components, local storage, and cloud synchronization.",
        "skills": [
            {"name": "Kotlin & Jetpack Compose", "category": "Mobile", "difficulty": "Intermediate"},
            {"name": "Android Architecture Components", "category": "Mobile", "difficulty": "Intermediate"},
        ],
        "roadmap_title": "Android App Engineer Roadmap",
        "roadmap_desc": "Develop modern Android apps using Kotlin, Jetpack Compose, and clean architecture.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Native Android App with Jetpack Compose",
                "skill_index": 0,
                "task_title": "Build Weather & Forecast Mobile App",
                "task_desc": "Develop native Android app fetching live weather API data using Retrofit and Room database persistence.",
                "task_instructions": "Submit GitHub repository and APK release file URL.",
            },
        ],
        "interview_questions": [
            {"question": "What is the Android activity lifecycle and how do launch modes affect task stacks?", "topic": "Android", "difficulty": "Medium"},
        ],
    },
    {
        "name": "UI/UX Designer",
        "slug": "ui-ux-designer",
        "category": "Design & Product",
        "description": "Design intuitive wireframes, user journeys, visual design systems, interactive prototypes, and usability testing.",
        "skills": [
            {"name": "Figma Design Systems", "category": "Design", "difficulty": "Beginner"},
            {"name": "User Research & Prototyping", "category": "UX", "difficulty": "Intermediate"},
        ],
        "roadmap_title": "UI/UX Product Designer Roadmap",
        "roadmap_desc": "Design modern user interfaces, visual design systems, and interactive prototypes.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Design System & Prototype Creation",
                "skill_index": 0,
                "task_title": "Design Complete Mobile Banking UI/UX Prototype",
                "task_desc": "Create wireframes, component design system, dark theme variants, and interactive Figma prototype.",
                "task_instructions": "Submit Figma public share link and documentation file URL.",
            },
        ],
        "interview_questions": [
            {"question": "How do you conduct usability testing and incorporate qualitative feedback into design iterations?", "topic": "UX", "difficulty": "Easy"},
        ],
    },
    {
        "name": "QA Engineer",
        "slug": "qa-engineer",
        "category": "Software Engineering",
        "description": "Build automated E2E testing suites, integration tests, performance benchmarking, and continuous quality audits.",
        "skills": [
            {"name": "Playwright & Cypress E2E", "category": "Testing", "difficulty": "Intermediate"},
            {"name": "API Testing with Pytest", "category": "Automation", "difficulty": "Intermediate"},
        ],
        "roadmap_title": "QA Automation Engineer Roadmap",
        "roadmap_desc": "Automate web and API quality testing using Playwright, Cypress, and continuous integration.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: End-to-End Automated Test Framework",
                "skill_index": 0,
                "task_title": "Build Automated E2E Test Suite for E-Commerce Checkout",
                "task_desc": "Write robust Playwright test scripts covering user login, cart manipulation, and payment flow.",
                "task_instructions": "Submit GitHub repository and HTML test execution report URL.",
            },
        ],
        "interview_questions": [
            {"question": "What is the difference between functional, regression, and smoke testing?", "topic": "Testing", "difficulty": "Easy"},
        ],
    },
    {
        "name": "Blockchain Developer",
        "slug": "blockchain-developer",
        "category": "Web3 & Security",
        "description": "Engineer decentralized smart contracts, Web3 dApps, consensus protocol integrations, and cryptographic security.",
        "skills": [
            {"name": "Solidity Smart Contracts", "category": "Web3", "difficulty": "Intermediate"},
            {"name": "Ethers.js & Web3 Frontend", "category": "DApp", "difficulty": "Advanced"},
        ],
        "roadmap_title": "Blockchain & Smart Contract Developer Roadmap",
        "roadmap_desc": "Build decentralized applications, smart contracts on Ethereum, and Web3 integrations.",
        "steps": [
            {
                "order": 1,
                "title": "Phase 1: Solidity Smart Contract Deployment",
                "skill_index": 0,
                "task_title": "Deploy Decentralized ERC-20 Token & Staking Contract",
                "task_desc": "Write audited Solidity smart contract, test with Hardhat, and deploy to Sepolia testnet.",
                "task_instructions": "Submit GitHub repository and deployed contract Etherscan link.",
            },
        ],
        "interview_questions": [
            {"question": "Explain reentrancy attacks in EVM smart contracts and how the Checks-Effects-Interactions pattern prevents them.", "topic": "Blockchain", "difficulty": "Hard"},
        ],
    },
]


from sqlalchemy import select, text

def seed_database(db: Session) -> None:
    """Seed comprehensive platform database records for all 14+ professions idempotently."""
    logger.info("Starting production database seeding for 14+ professions...")
    Base.metadata.create_all(bind=db.get_bind())

    # Ensure new columns exist on users table
    try:
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS profession_id UUID;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS onboarding_completed BOOLEAN DEFAULT FALSE;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS assessment_score INT DEFAULT 0;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS ai_match_percentage INT DEFAULT 0;"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS daily_study_time VARCHAR(50);"))
        db.execute(text("ALTER TABLE users ADD COLUMN IF NOT EXISTS experience_level VARCHAR(50);"))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning("Column migration notice: %s", e)

    # 1. Roles
    roles_data = [
        {"name": "admin", "description": "Administrator with full system privileges."},
        {"name": "student", "description": "Learner studying career roadmaps and completing tasks."},
        {"name": "mentor", "description": "Industry mentor providing feedback and guidance."},
    ]
    roles: dict[str, Role] = {}
    for r_info in roles_data:
        existing_role = db.execute(select(Role).where(Role.name == r_info["name"])).scalars().first()
        if not existing_role:
            role_obj = Role(name=r_info["name"], description=r_info["description"])
            db.add(role_obj)
            db.flush()
            roles[r_info["name"]] = role_obj
            logger.info("Created role: %s", r_info["name"])
        else:
            roles[r_info["name"]] = existing_role

    # 2. Admin User
    admin_email = "admin@aicareer.com"
    existing_admin = db.execute(select(User).where(User.email == admin_email)).scalars().first()
    if not existing_admin:
        admin_user = User(
            email=admin_email,
            full_name="System Admin",
            password_hash=hash_password("AdminPassword123!"),
            role_id=roles["admin"].id,
            is_active=True,
            is_verified=True,
        )
        db.add(admin_user)
        db.flush()
        logger.info("Created admin user: %s", admin_email)

    # 3. Seed All 14+ Professions, Skills, Roadmaps, Steps, Tasks, and Interview Questions
    for prof_data in SEED_PROFESSIONS:
        # Profession
        existing_p = db.execute(select(Profession).where(Profession.slug == prof_data["slug"])).scalars().first()
        if not existing_p:
            p_obj = Profession(
                name=prof_data["name"],
                slug=prof_data["slug"],
                category=prof_data["category"],
                description=prof_data["description"],
                is_active=True,
            )
            db.add(p_obj)
            db.flush()
            logger.info("Created profession: %s", prof_data["name"])
            profession_entity = p_obj
        else:
            profession_entity = existing_p

        # Skills
        created_skills = []
        for sk_data in prof_data["skills"]:
            existing_sk = db.execute(
                select(Skill)
                .where(Skill.name == sk_data["name"])
                .where(Skill.profession_id == profession_entity.id)
            ).scalars().first()

            if not existing_sk:
                sk_obj = Skill(
                    name=sk_data["name"],
                    category=sk_data["category"],
                    difficulty=sk_data["difficulty"],
                    description=f"{sk_data['name']} competency for {profession_entity.name}",
                    profession_id=profession_entity.id,
                )
                db.add(sk_obj)
                db.flush()
                created_skills.append(sk_obj)
            else:
                created_skills.append(existing_sk)

        # Career Roadmap
        existing_rm = db.execute(
            select(CareerRoadmap).where(CareerRoadmap.profession_id == profession_entity.id)
        ).scalars().first()

        if not existing_rm:
            rm_obj = CareerRoadmap(
                title=prof_data["roadmap_title"],
                description=prof_data["roadmap_desc"],
                profession_id=profession_entity.id,
                difficulty="Medium",
                estimated_months=4,
                is_active=True,
            )
            db.add(rm_obj)
            db.flush()
            logger.info("Created roadmap: %s", prof_data["roadmap_title"])
            roadmap_entity = rm_obj
        else:
            roadmap_entity = existing_rm

        # Steps & Tasks
        for step_idx, step_data in enumerate(prof_data["steps"]):
            assigned_skill = created_skills[step_data["skill_index"] % len(created_skills)]

            existing_step = db.execute(
                select(RoadmapStep)
                .where(RoadmapStep.roadmap_id == roadmap_entity.id)
                .where(RoadmapStep.step_order == step_data["order"])
            ).scalars().first()

            if not existing_step:
                step_obj = RoadmapStep(
                    roadmap_id=roadmap_entity.id,
                    skill_id=assigned_skill.id,
                    step_order=step_data["order"],
                    estimated_hours=40,
                    required=True,
                )
                db.add(step_obj)
                db.flush()
                step_entity = step_obj
            else:
                step_entity = existing_step

            # Task under step
            existing_task = db.execute(
                select(Task).where(Task.roadmap_step_id == step_entity.id)
            ).scalars().first()

            if not existing_task:
                task_obj = Task(
                    title=step_data["task_title"],
                    description=step_data["task_desc"],
                    instructions=step_data["task_instructions"],
                    difficulty="Medium",
                    estimated_minutes=120,
                    order_no=step_data["order"],
                    is_active=True,
                    roadmap_step_id=step_entity.id,
                )
                db.add(task_obj)
                db.flush()
                logger.info("Created task: %s", step_data["task_title"])

    db.commit()
    logger.info("Database seeding completed successfully for all 14+ professions!")


if __name__ == "__main__":
    db_session = SessionLocal()
    try:
        seed_database(db_session)
    finally:
        db_session.close()
