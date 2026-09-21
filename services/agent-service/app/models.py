"""SQLAlchemy models for the agent service."""

from sqlalchemy import Column, Integer, String, Text, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from db.base import Base

class Student(Base):
    __tablename__ = "students"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False)
    profession = Column(String, nullable=False)
    created_at = Column(DateTime, server_default="now()")
    problems = relationship("Problem", back_populates="student")
    evaluations = relationship("Evaluation", back_populates="student")

class Problem(Base):
    __tablename__ = "problems"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    difficulty = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    student = relationship("Student", back_populates="problems")

class Evaluation(Base):
    __tablename__ = "evaluations"
    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    github_url = Column(String, nullable=False)
    score = Column(Integer)
    interview_plan = Column(Text)
    student = relationship("Student", back_populates="evaluations")

class Interview(Base):
    __tablename__ = "interviews"
    id = Column(Integer, primary_key=True, index=True)
    evaluation_id = Column(Integer, ForeignKey("evaluations.id"), nullable=False)
    transcript = Column(Text)
