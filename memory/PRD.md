# PasteBridge - Product Requirements Document

## Problem Statement
An Android application that listens to the device's clipboard. When text is copied, the app frictionlessly pushes the text to a web-based notepad accessible via a memorable, short code.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: Expo (React Native) with expo-router
- **Database**: MongoDB (notepads, users, webhooks, feedback, payment_transactions)
- **Auth**: JWT-based (python-jose, passlib/bcrypt)
- **AI**: GPT-5.2 via emergentintegrations library
- **Payments**: Stripe via emergentintegrations library
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
- In-app feedback form (bug/feature_request/missing_feature/other)
- Admin endpoints: list, filter, AI-summarize, status update
- Feedback button in mobile app toolbar
- **Testing**: 27/27 tests passed

### Stripe Subscriptions - DONE (Feb 17, 2026)
- Free ($0): 5 notepads, 90-day storage
- Pro ($4.99): Unlimited, 1-year, AI summarize, export
- Business ($14.99): Unlimited, never-expire, webhooks, priority
- Stripe checkout, status polling, webhook, success/cancel pages
- Plans web page at /api/subscription/plans-page

### Web View Enhancements - DONE (Feb 17, 2026)
- Export TXT/MD/JSON buttons on notepad view
- AI Summarize button with inline results

## Total Testing: 109/109 tests passed across 4 iterations (100%)

## DB Collections
- **notepads**: id, code, owner_id, user_id, created_at, expires_at, account_type, entries
- **users**: id, email, password_hash, name, account_type, push_tokens, subscription_plan
- **webhooks**: id, user_id, url, events, secret, active
- **feedback**: id, category, title, description, severity, user_id, user_email, status
- **payment_transactions**: id, session_id, user_id, plan, amount, currency, payment_status, activated

## API Endpoints
- Auth: register, login, /me, profile, change-password, notepads, link-notepad(s), push-token
- Webhooks: create, list, delete
- Notepad: create, get, lookup, append, clear, export, summarize
- Feedback: submit, list, summarize, update status
- Subscription: plans, checkout, status, success page, plans page, webhook
- Admin: cleanup-expired, stats
- Web: landing (/), notepad view, plans page, success page

## Prioritized Backlog
### P1 - Technical Improvements
- Rate limiting, pagination, database indexes
- Social login (Google OAuth), password reset
### P2 - UX Enhancements
- Desktop apps, browser extensions
- Collaborative notepads
- Notepad search/filtering
