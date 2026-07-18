# AI Career Hub

# Software Requirement Specification (SRS)

Version: 1.0

Author: Kartik Patidar

Project Type:
AI Powered Career Development Platform

---

# 1. Introduction

## 1.1 Purpose

The purpose of AI Career Hub is to bridge the gap between academic education and industry expectations by providing students with profession-specific learning paths, real-world tasks, AI-powered feedback, personalized recommendations, and AI-based mock interviews.

The platform is designed to help students continuously improve their technical and soft skills while becoming placement-ready through practical learning.

---

## 1.2 Vision

To become an intelligent AI mentor that guides students throughout their learning journey and helps them become industry-ready.

---

## 1.3 Target Users

• Students

• Mentors

• Administrators

---

## 1.4 Technology Stack

Frontend

- React.js
- Tailwind CSS
- React Query
- React Router
- Axios
- Framer Motion

Backend

- FastAPI

Database

- PostgreSQL

Authentication

- JWT Authentication

Vector Database

- ChromaDB

Storage

- AWS S3

AI

- Gemini / OpenAI
- LangChain
- Whisper (Future)

Deployment

- Docker
- Vercel
- Railway / AWS

---

# 2. Project Objectives

The system should:

- Personalize learning according to profession.
- Assign real-world industry tasks.
- Evaluate submissions using AI.
- Conduct AI-powered mock interviews.
- Analyze resumes.
- Track student progress.
- Recommend next learning steps.
- Generate career readiness reports.


# 3. Functional Requirements

The platform shall provide the following core functionalities.

## Authentication

- User Registration
- Secure Login
- JWT Authentication
- Email Verification
- Password Reset
- Logout

---

## Student Profile

- Complete Profile
- Select Profession
- Upload Resume
- Add GitHub
- Add LinkedIn
- Add Portfolio

---

## Learning Roadmap

- Personalized Learning Path
- AI Recommended Topics
- Skill Progress Tracking
- Learning Modules
- Learning Resources

---

## Task Management

- Profession-specific Tasks
- Task Submission
- GitHub Repository Submission
- Live Demo Submission
- Deadline Tracking

---

## AI Feedback

- AI Code Review
- Performance Score
- Code Quality
- Best Practices
- Suggestions

---

## Resume Analyzer

- ATS Score
- Missing Keywords
- Skill Gap Analysis
- Resume Suggestions

---

## AI Mock Interview

- Technical Questions
- HR Questions
- Communication Analysis
- Confidence Score
- Overall Interview Report

---

## Dashboard

- Student Progress
- Completed Tasks
- Upcoming Interviews
- Skill Growth
- Leaderboard

---

## Notifications

- Interview Reminder
- Deadline Reminder
- Task Updates
- Achievement Notifications

---

## Admin Panel

- Manage Students
- Manage Tasks
- Manage Learning Paths
- Manage Interviews
- Analytics Dashboard

# 4. User Roles and Permissions

The platform supports multiple user roles with different responsibilities.

---

## Student

### Permissions

- Register and Login
- Update Profile
- Select Profession
- View Learning Roadmap
- Complete Tasks
- Submit Projects
- Receive AI Feedback
- Schedule Mock Interviews
- Upload Resume
- View Dashboard
- Track Skill Progress
- Receive Notifications

---

## Mentor

### Permissions

- Review Student Progress
- Create Learning Resources
- Review Task Submissions
- Monitor AI Feedback
- Schedule Interviews
- Provide Manual Feedback

---

## Administrator

### Permissions

- Manage Users
- Manage Professions
- Manage Skills
- Manage Tasks
- Manage Learning Paths
- Manage Interviews
- Manage Reports
- View Analytics
- Manage Notifications

---

## Super Administrator (Future)

### Permissions

- Full System Access
- Manage Admins
- System Configuration
- AI Configuration
- Platform Monitoring

# 5. System Modules

The platform is divided into the following modules.

---

### Module 1

Authentication System

---

### Module 2

Student Profile Management

---

### Module 3

Profession Management

---

### Module 4

Learning Roadmap

---

### Module 5

Task Management

---

### Module 6

AI Feedback Engine

---

### Module 7

Resume Analyzer

---

### Module 8

AI Mock Interview

---

### Module 9

Dashboard & Analytics

---

### Module 10

Notifications

---

### Module 11

Leaderboard

---

### Module 12

Achievements

---

### Module 13

Admin Panel

---

### Module 14

AI Memory

---

### Module 15

File Storage

# 6. Core Features

## Personalized Dashboard

Students see a customized dashboard based on their selected profession.

---

## AI Learning Roadmap

Dynamic roadmap generated according to student goals.

---

## Real World Tasks

Industry-based practical assignments with deadlines.

---

## AI Code Review

Automatic evaluation of submitted code and projects.

---

## Resume Analysis

AI-powered ATS score and resume improvement suggestions.

---

## AI Mock Interview

Simulates technical and HR interviews with instant feedback.

---

## Skill Progress Tracking

Tracks learning progress across technical and soft skills.

---

## Notifications

Real-time reminders for tasks, interviews, and achievements.

---

## Analytics

Visual reports showing performance, consistency, and improvement.

---

## Career Readiness Score

A calculated score representing interview readiness.