# PasteBridge - Product Requirements Document

## Problem Statement
An Android application that listens to the device's clipboard. When text is copied, the app frictionlessly pushes the text to a web-based notepad accessible via a memorable, short code.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: Expo (React Native) with expo-router
- **Database**: MongoDB with 12 indexes (notepads, users, webhooks, feedback, password_resets, payment_transactions)
- **Auth**: JWT + Google OAuth (Emergent Auth) + password reset
- **AI**: GPT-5.2 via emergentintegrations
- **Payments**: Stripe via emergentintegrations
- **Security**: Rate limiting (in-memory), bcrypt password hashing
- **CI/CD**: GitHub Actions for APK builds (Gradle)

## Core Files
- `/app/backend/server.py` - All backend logic
- `/app/frontend/app/index.tsx` - Main app screen
- `/app/frontend/app/context/AuthContext.tsx` - Auth + push notification state
- `/app/frontend/app/_layout.tsx` - Root layout with AuthProvider

## What's Implemented

### Phase 1: Notepad History - DONE
### Phase 2: Guest Account Limits - DONE
### Phase 3: User Authentication - DONE (Feb 15, 2026)
### Phase 4: Premium Features - DONE (Feb 17, 2026)
- Push notifications, Cron job, Webhooks, Export, AI Summarization
### Bug & Feedback System - DONE (Feb 17, 2026)
- In-app feedback form + admin dashboard with AI summary
### Stripe Subscriptions - DONE (Feb 17, 2026)
- Free/Pro/Business tiers with Stripe checkout
### Technical Improvements - DONE (Feb 17, 2026)
- **Rate limiting**: register (5/5min), login (10/5min), forgot-password (3/10min), google-session (10/5min)
- **Pagination**: Feedback list with page/limit/total/pages
- **Database indexes**: 12 indexes across 6 collections (sparse unique on code, email, id)
- **Google OAuth**: Emergent Auth callback + session exchange
- **Password reset**: Token-based with web reset page
- **Admin dashboard**: Full web UI at /api/admin/dashboard

## Total Testing: 134/134 tests passed across 5 iterations (100%)

## DB Collections & Indexes
- **notepads**: code (unique sparse), user_id, expires_at, account_type
- **users**: email (unique sparse), id (unique sparse)
- **feedback**: status, category, created_at (desc)
- **webhooks**: user_id
- **password_resets**: token, expires_at
- **payment_transactions**: session_id

## API Endpoints
- Auth: register, login, /me, profile, change-password, notepads, link-notepad(s), push-token, forgot-password, reset-password, google-callback, google-session
- Webhooks: create, list, delete
- Notepad: create, get, lookup, append, clear, export, summarize
- Feedback: submit, list (paginated), summarize, update status
- Subscription: plans, checkout, status, success page, plans page, stripe webhook
- Admin: cleanup-expired, stats, dashboard
- Web: landing (/), notepad view, plans page, reset page, google callback, success page

## Prioritized Backlog
### P2 - UX Enhancements
- Desktop apps, browser extensions
- Collaborative notepads
- Notepad search/filtering
- Email notifications for password reset

## Test Credentials
- Email: test@test.com / Password: password123
