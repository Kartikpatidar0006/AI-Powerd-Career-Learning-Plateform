# AI Career Hub - Database Schema

## Version
v1.0

## Author
Kartik Patidar

## Database
PostgreSQL 16+

## ORM
SQLAlchemy 2.0

## Migration
Alembic

## UUID Strategy
UUID v4

---

# Database Design Principles

This database is designed following enterprise-level software engineering practices.

Goals:

- High Scalability
- High Performance
- Clean Relationships
- Third Normal Form (3NF)
- Easy Maintenance
- FastAPI Compatible
- SQLAlchemy Compatible
- AI Ready
- Multi-role Authentication
- Production Ready

---

# Naming Convention

## Tables

snake_case

Example

users

student_profiles

task_submissions

---

## Columns

snake_case

Example

created_at

updated_at

profession_id

resume_url

---

## Primary Keys

Every table uses

UUID

Example

id UUID PRIMARY KEY

---

## Foreign Keys

Every relation should use UUID.

Example

user_id UUID REFERENCES users(id)

---

## Common Columns

Almost every table should have

created_at

updated_at

Some tables also include

deleted_at

for Soft Delete.

---

# Database Modules

The complete database is divided into the following modules.

1. Authentication

2. Users

3. Student Profile

4. Profession

5. Skills

6. Learning Roadmap

7. Tasks

8. AI Feedback

9. Resume Analyzer

10. Mock Interview

11. Notifications

12. Achievements

13. Leaderboard

14. Activity Logs

15. AI Memory

16. AWS S3 Storage

---

# Table Count

Estimated

30–35 Tables

---

# Next

Authentication Module

# Module 1 - Authentication

## Overview

# Table 1 - Roles

## Purpose

The Roles table defines different types of users in the system.

Instead of hardcoding permissions, every user will be assigned a role.

This makes the application scalable and supports Role Based Access Control (RBAC).

---

## Roles

- Student
- Mentor
- Admin
- Super Admin (Future)

---

## Columns

| Column | Type | Description |
|---------|------|-------------|
| id | UUID | Primary Key |
| name | VARCHAR(50) | Role Name |
| description | TEXT | Description of Role |
| created_at | TIMESTAMP | Created Time |
| updated_at | TIMESTAMP | Last Updated |

---

## Relationships

One Role

↓

Many Users

roles (1)

↓

users (N)

---

## Indexes

- Primary Key
- Unique(name)

---

## Constraints

- Role Name cannot be duplicated.
- Role Name cannot be NULL.

The Authentication Module is responsible for secure user registration,
login, authorization, session management, password recovery, email
verification, and role-based access control.

The system follows JWT Authentication using Access Token and Refresh
Token strategy.

---

## Authentication Workflow

User Registration

↓

Email Verification

↓

Login

↓

JWT Access Token

↓

Refresh Token

↓

Access Protected APIs

↓

Logout

---

## Tables Included

1. users

2. roles

3. refresh_tokens

4. password_reset_tokens

5. email_verification_tokens

---

## Relationships

roles

↓

users

↓

refresh_tokens

↓

password_reset_tokens

↓

email_verification_tokens

---

## Security Features

- Password Hashing (bcrypt)
- JWT Authentication
- Refresh Tokens
- Role-Based Access Control (RBAC)
- Email Verification
- Password Reset
- Session Expiration
- Secure API Access

---

## Why Separate Tables?

Instead of storing everything in the Users table,
authentication-related data is separated into dedicated tables to improve:

- Security
- Scalability
- Performance
- Maintainability

This follows enterprise software architecture principles.

# Table 1 - Roles

## Purpose

The Roles table defines different types of users in the system.

Instead of hardcoding permissions, every user will be assigned a role.

This makes the application scalable and supports Role Based Access Control (RBAC).

---

## Roles

- Student
- Mentor
- Admin
- Super Admin (Future)

---

## Columns

| Column | Type | Description |
|---------|------|-------------|
| id | UUID | Primary Key |
| name | VARCHAR(50) | Role Name |
| description | TEXT | Description of Role |
| created_at | TIMESTAMP | Created Time |
| updated_at | TIMESTAMP | Last Updated |

---

## Relationships

One Role

↓

Many Users

roles (1)

↓

users (N)

---

## Indexes

- Primary Key
- Unique(name)

---

## Constraints

- Role Name cannot be duplicated.
- Role Name cannot be NULL.



# Table 2 - Users

## Purpose

The Users table stores the primary account information of every registered user.

All authentication and authorization processes are based on this table.

Each user belongs to exactly one role.

---

## Columns

| Column | Type | Description |
|---------|------|-------------|
| id | UUID | Primary Key |
| role_id | UUID | Foreign Key → Roles |
| first_name | VARCHAR(100) | User First Name |
| last_name | VARCHAR(100) | User Last Name |
| email | VARCHAR(255) | Unique Email |
| phone | VARCHAR(20) | Contact Number |
| password_hash | TEXT | Encrypted Password |
| profile_picture | TEXT | AWS S3 URL |
| is_email_verified | BOOLEAN | Email Status |
| is_active | BOOLEAN | Account Status |
| last_login | TIMESTAMP | Last Login |
| created_at | TIMESTAMP | Created Time |
| updated_at | TIMESTAMP | Last Updated |

---

## Relationships

One Role

↓

Many Users

One User

↓

One Student Profile

One User

↓

Many Refresh Tokens

One User

↓

Many Notifications

---

## Indexes

Primary Key

Unique(email)

Index(role_id)

Index(phone)

---

## Constraints

Email must be unique.

Password should never be stored in plain text.

Phone number must be optional.


# Table 3 - Refresh Tokens

## Purpose

Stores refresh tokens issued after user login.

Refresh tokens are used to generate new access tokens without requiring
the user to log in again.

---

## Columns

| Column | Type | Description |
|---------|------|-------------|
| id | UUID | Primary Key |
| user_id | UUID | Foreign Key → Users |
| token | TEXT | Refresh Token |
| expires_at | TIMESTAMP | Expiration Time |
| created_at | TIMESTAMP | Token Created Time |

---

## Relationships

One User

↓

Many Refresh Tokens

---

## Indexes

Primary Key

Index(user_id)

Unique(token)

---

## Security Notes

Refresh tokens should be encrypted before storage.

Expired tokens should be automatically removed.


# Table 4 - Password Reset Tokens

## Purpose

Stores password reset requests.

---

## Columns

| Column | Type | Description |
|---------|------|-------------|
| id | UUID | Primary Key |
| user_id | UUID | Foreign Key |
| token | TEXT | Reset Token |
| expires_at | TIMESTAMP | Expiry |
| is_used | BOOLEAN | Token Used |
| created_at | TIMESTAMP | Created Time |

---

## Constraints

A token can only be used once.

Expired tokens become invalid.


# Table 5 - Email Verification Tokens

## Purpose

Stores verification links sent to newly registered users.

---

## Columns

| Column | Type | Description |
|---------|------|-------------|
| id | UUID | Primary Key |
| user_id | UUID | Foreign Key |
| token | TEXT | Verification Token |
| expires_at | TIMESTAMP | Expiry |
| is_verified | BOOLEAN | Verification Status |
| created_at | TIMESTAMP | Created Time |

---

## Constraints

Verification token expires after a configurable time (e.g., 24 hours).

A verified account cannot be verified again using the same token.

# Authentication Flow

Register

↓

Email Verification

↓

Login

↓

Access Token

↓

Refresh Token

↓

Protected APIs

↓

Logout


# Authentication Module Summary

## Tables

- roles
- users
- refresh_tokens
- password_reset_tokens
- email_verification_tokens

## Features

- JWT Authentication
- Role Based Access Control
- Refresh Token Strategy
- Password Reset
- Email Verification
- Secure Password Hashing