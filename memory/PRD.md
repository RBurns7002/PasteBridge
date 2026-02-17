# PasteBridge - Product Requirements Document

## Problem Statement
An Android application that listens to the device's clipboard. When text is copied, the app frictionlessly pushes the text to a web-based notepad accessible via a memorable, short code.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: Expo (React Native) with expo-router
- **Database**: MongoDB with indexes (notepads, users, webhooks, feedback, password_resets, payment_transactions)
- **Auth**: JWT + Google OAuth (Emergent Auth) + password reset
- **AI**: GPT-5.2 via emergentintegrations
- **Payments**: Stripe via emergentintegrations
- **Security**: Rate limiting (in-memory), bcrypt password hashing
- **CI/CD**: GitHub Actions for APK builds (Gradle, metro maxWorkers=1, NODE_OPTIONS 4GB)

## Core Files
- `/app/backend/server.py` - All backend logic
- `/app/frontend/app/index.tsx` - Main app screen
- `/app/frontend/app/context/AuthContext.tsx` - Auth + push notifications
- `/app/frontend/app/_layout.tsx` - Root layout with AuthProvider
- `/app/.github/workflows/build-apk.yml` - APK build workflow
- `/app/frontend/metro.config.js` - Metro bundler config

## What's Implemented

### Phase 1-3: History, Guest Limits, Auth — DONE
### Phase 4: Premium Features — DONE (Feb 17)
- Push notifications, Cron job, Webhooks, Export, AI Summarization
### Bug & Feedback System — DONE (Feb 17)
### Stripe Subscriptions — DONE (Feb 17)
### Technical Improvements — DONE (Feb 17)
- Rate limiting, Pagination, DB indexes, Google OAuth, Password reset, Admin dashboard
### Collaborative Notepads — DONE (Feb 17)
- Share notepad by email, collaborator management, shared notepads list
- Access control (owner-only share/unshare, collaborator view)
### Search & Filtering — DONE (Feb 17)
- Text search across entries, code prefix search, date range filter
- Pagination (page/limit/total/pages), matching preview
### Analytics Dashboard — DONE (Feb 17)
- `/api/admin/analytics` — stats cards, entries/day chart, users/day chart, top notepads table
### GitHub Actions Fix — DONE (Feb 17)
- metro.config.js maxWorkers=1, NODE_OPTIONS 4GB, clear Metro cache

## Total Testing: 157/157 tests passed across 6 iterations (100%)

## API Endpoints
- Auth: register, login, /me, profile, change-password, notepads, link-notepad(s), push-token, forgot-password, reset-password, google-callback, google-session, shared-notepads
- Collaborative: share, unshare, collaborators
- Search: search notepads (text/code/date/pagination)
- Webhooks: create, list, delete
- Notepad: create, get, lookup, append, clear, export, summarize
- Feedback: submit, list (paginated), summarize, update status
- Subscription: plans, checkout, status, success page, plans page, stripe webhook
- Admin: cleanup-expired, stats, dashboard, analytics, analytics-data
- Web: landing (/), notepad view, plans page, reset page, google callback, success page

## Prioritized Backlog
### P2 - UX Enhancements
- Email service for password reset delivery
- Desktop apps, browser extensions
- Import functionality (upload txt/md/json)
- Real-time collaborative editing (WebSockets)

## Test Credentials
- test@test.com / password123
- collab@test.com / password123
