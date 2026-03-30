# 8D-Report-KI — Product Requirements Document

## Original Problem Statement
Import, setup and run the GitHub repository `https://github.com/Vschatochin-wq/8d-Report-KI-` on the Emergent platform. The application is an **8D Complaint Management System** (8D-Opus Reklamationsmanagement) for **GÜHRING KG**, featuring:

- **FastAPI backend** with MongoDB
- **React frontend** with German-language UI
- **AI integration** (Claude Opus 4.6) for automated 8D report quality reviews
- **8D methodology** workflow (D1-D8 steps)

## User Personas
- **QM Administrator**: Full access to all complaints, reviews, and statistics
- **ZQM**: Quality management review and approval
- **Bearbeiter**: Complaint processing and 8D report completion
- **Viewer**: Read-only access

## Core Requirements
1. **Complaint CRUD**: Create, read, update, soft-delete complaints with 8D structure
2. **8D Workflow**: Status transitions (draft → open → in_progress → review_pending → reviewed → approval_pending → approved → closed)
3. **AI Reviews**: Claude Opus 4.6 reviews 8D reports for completeness, consistency, plausibility
4. **Dashboard**: KPIs, status distribution, monthly trends
5. **Notifications**: In-app notification system
6. **Document Upload**: OCR processing for complaint documents
7. **Multi-language**: German primary, English secondary
8. **Statistics**: Analysis dashboard with various charts and metrics

## Architecture
- **Backend**: FastAPI on port 8001, all routes prefixed with `/api`
- **Frontend**: React on port 3000, uses `REACT_APP_BACKEND_URL`
- **Database**: MongoDB via `MONGO_URL` env variable, DB name: `reklamation_db`
- **AI**: Claude Opus 4.6 via Emergent LLM Key (`emergentintegrations` library)

## What's Been Implemented (2026-03-30)
- [x] Backend server.py with all route registrations
- [x] Complaint CRUD endpoints (`/api/v1/complaints`)
- [x] Review endpoints (`/api/v1/complaints/{id}/review`, queue, stats)
- [x] Statistics endpoints (`/api/v1/statistics/dashboard`, trends, distribution)
- [x] Notification endpoints (`/api/v1/notifications`, unread-count)
- [x] Upload endpoints with OCR support
- [x] AI service integrated with Emergent LLM Key
- [x] Review service integrated with Emergent LLM Key  
- [x] Frontend Dashboard with stats and charts
- [x] Frontend Complaint List with filters and pagination
- [x] Frontend Complaint Detail with D1-D8 tabs
- [x] Frontend Review Queue page
- [x] Frontend Analysis Dashboard with 4 tabs
- [x] Sidebar navigation with all pages
- [x] I18n support (German)
- [x] 3 seeded sample complaints (BMW AG, Daimler AG, Volkswagen AG)
- [x] All tests passing (21/21 backend, all frontend pages)

## Prioritized Backlog
### P0 (Critical)
- None remaining

### P1 (Important)
- Authentication/authorization system
- Real WebSocket connection for live updates
- Full LanguageSwitch with locale persistence
- Document upload flow end-to-end testing

### P2 (Nice-to-have)
- UI/UX design improvements (avoid "AI slop" patterns)
- Email notifications
- Export functionality (PDF/Excel)
- Audit trail/history view
