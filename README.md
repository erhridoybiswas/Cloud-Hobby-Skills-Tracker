# 🎯 Online Hobby & Skills Tracker with Community Sharing on Cloud

> A cloud-based platform where users track hobbies and skills, log practice
> sessions, set goals, upload proof of achievement, and share progress with
> a community feed.

[![CI](https://github.com/YOUR_USERNAME/Cloud-Hobby-Skills-Tracker/actions/workflows/ci.yml/badge.svg)](https://github.com/YOUR_USERNAME/Cloud-Hobby-Skills-Tracker/actions)
![Python](https://img.shields.io/badge/Python-3.11-blue)
![Flask](https://img.shields.io/badge/Flask-3.0-green)
![Tests](https://img.shields.io/badge/tests-62%20passing-brightgreen)
![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Overview

This project demonstrates end-to-end **cloud computing** concepts by building a
realistic multi-user application: authentication, a managed cloud database,
object storage for media, a REST API, progress analytics, and a scalable
social feed — all runnable locally for free and deployable to free-tier cloud
services.

## Problem Statement

People learning hobbies and skills have no single place to record practice,
measure progress, and stay motivated. Notes are scattered across devices, there
is no objective measure of improvement, and there is no community to share wins
with. Existing tools are either single-purpose (fitness trackers, code
practice sites) or too heavyweight for casual learners.

## Objectives

1. Provide cross-device, cloud-hosted progress tracking for any hobby or skill.
2. Automate progress, streak, and milestone calculation from practice logs.
3. Store media proof in cloud object storage, keeping the database lean.
4. Enable community sharing through a feed with likes and comments.
5. Demonstrate production-grade cloud architecture: managed DB, object storage,
   JWT auth, REST APIs, CI/CD, monitoring, and scalability.

## Features

- 🔐 JWT authentication with PBKDF2 password hashing
- 👤 User profiles with avatar upload
- 🎯 Skill/hobby tracking with levels and statuses
- 📊 Goals with automatic progress calculation
- 🏅 Milestones that auto-achieve
- ⏱️ Practice session logging with notes
- 🔥 Streak tracking (current + longest)
- 📈 Five-chart analytics dashboard
- 🌍 Community feed with images
- ❤️ Likes (duplicate-proof) and 💬 comments
- 👥 Follow system + following-only feed
- ☁️ Cloud object storage abstraction (S3 / Supabase / local)
- 🗄️ Cloud database abstraction (Postgres / SQLite)
- ✅ 62 automated tests + GitHub Actions CI

## Industry Relevance

The architecture mirrors Strava (activity logs → analytics → social feed),
Coursera (progress + certificates in object storage), and Behance
(media uploads → public feed). The same patterns power employee learning
portals, EdTech platforms, and creator communities.

## Cloud Computing Concepts

| Concept | Where it is demonstrated |
|---|---|
| Cloud-hosted application | Deployable to Render / Cloud Run |
| SaaS / PaaS / IaaS | Full SaaS product on PaaS compute |
| Managed cloud database | `cloud/database_service.py` (SQLite ⇄ Postgres) |
| Object storage | `cloud/storage_service.py` (local ⇄ S3 ⇄ Supabase) |
| Authentication | PBKDF2 + signed JWT |
| Authorization | Ownership checks in every query |
| REST API | 30+ JSON endpoints |
| Client-server architecture | Browser ↔ Flask |
| Serverless | App factory is Lambda/Cloud-Function ready |
| Scalability & elasticity | Stateless API, horizontal replicas |
| CDN | Frontend deployable to Netlify/CloudFront |
| Load balancing | Health endpoint for LB probes |
| Caching | Redis-ready feed caching |
| Environment variables | `.env` driven configuration |
| Secrets management | `.gitignore` + Secrets Manager in cloud |
| Logging & monitoring | Structured logs + `/api/health` |
| Backup | SQLite `.backup` / managed DB snapshots |
| CI/CD | GitHub Actions pipeline |

## Architecture
Users → Web Frontend → Authentication → REST API → Cloud Backend
│
┌───────────────┬───────────────┴──────────┐
▼ ▼ ▼
Cloud DB Object Storage Analytics
└───────────────┴──────────────────────────┘
▼
Community Feed

*(Replace with your exported diagram in `docs/architecture.png`.)*

## Technology Stack

**Backend:** Python 3.11, Flask 3, PyJWT, Werkzeug
**Database:** SQLite (local) → PostgreSQL / Supabase (cloud)
**Storage:** Local filesystem → AWS S3 / Supabase Storage
**Frontend:** HTML5, CSS3, vanilla JavaScript, Chart.js
**Testing:** pytest (62 tests)
**CI/CD:** GitHub Actions
**Deployment:** Render / Cloud Run / Docker

## Screenshots

| Screenshot | Description |
|---|---|
| `01_project_structure.png` | Repository folder tree |
| `02_architecture_diagram.png` | Cloud architecture |
| `03_registration.png` | Sign-up form |
| `04_dashboard.png` | Analytics dashboard with 5 charts |
| `05_skills.png` | Skill cards with progress bars |
| `06_goal_creation.png` | Goal + milestone modal |
| `07_practice_log.png` | Practice session modal |
| `08_community_feed.png` | Community feed |
| `09_like_comment.png` | Like and comment interaction |
| `10_api_response.png` | Postman REST API response |
| `11_tests_passing.png` | `pytest -v` output |
| `12_cloud_deploy.png` | Render deployment dashboard |
| `13_github_actions.png` | Green CI pipeline |

## Installation & Local Setup

```bash
git clone https://github.com/YOUR_USERNAME/Cloud-Hobby-Skills-Tracker.git
cd Cloud-Hobby-Skills-Tracker

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env             # then set SECRET_KEY

python backend/app.py
Open http://127.0.0.1:5000

Load demo data
bash
python sample_data/seed.py
Demo logins (password Password123): alice@example.com, bob@example.com, carol@example.com

Environment Variables
See .env.example. Never commit the real .env.

Cloud Deployment
See docs/DEPLOYMENT.md for step-by-step instructions
for Render + Supabase (free tier) and AWS (enterprise).

Testing
bash
pytest -v                                    # run all 62 tests
pytest --cov=backend --cov=cloud --cov=analytics
Security
Parameterized SQL, PBKDF2 hashing, JWT auth, ownership checks on every write,
file type/size validation, path-traversal protection, XSS escaping, CORS
scoping, and secrets kept out of version control.

Privacy
Public profile endpoints never expose email addresses. Account deletion
cascades across all related tables. See §24 of the project report.

Scalability
The API is stateless (JWT, no server-side sessions), so it scales horizontally
by adding replicas. Database indexes, pagination, and an abstraction layer for
caching are already in place. See §25.

Failure Handling
Compensating transactions across the database and object storage, idempotent
likes/follows, atomic goal+milestone creation, and graceful JSON error
responses. See §27.

Results
62/62 automated tests passing

~93 % code coverage

30+ REST endpoints

11 normalized tables with foreign keys and indexes

Runs on ₹0 of infrastructure (local + free-tier cloud)

Limitations
Free-tier hosting sleeps after inactivity (~30 s cold start).

No email verification or password reset flow yet.

Analytics are computed on read (fine at this scale, not at 1M users).

No refresh tokens — users re-login when the JWT expires.

Content moderation is limited to ownership checks.

Future Improvements
Refresh tokens + email verification

WebSocket notifications

Image thumbnailing + AWS Rekognition moderation

Redis-cached feed with fan-out-on-write

React + TypeScript frontend

Mobile app via React Native

Learning Outcomes
Cloud architecture design · REST API design · relational data modelling ·
JWT authentication and authorization · object storage vs database separation ·
analytics aggregation · automated testing · CI/CD · security hardening ·
failure handling across distributed storage.

Author
#**HRIDOY_BISWAS**
