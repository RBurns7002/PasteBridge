# PasteBridge - Product Requirements Document

## Problem Statement
An Android application that listens to the device's clipboard. When text is copied, the app frictionlessly pushes the text to a web-based notepad accessible via a memorable, short code.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: Expo (React Native) with expo-router
- **Database**: MongoDB (notepads, users, webhooks collections)
- **Auth**: JWT-based (python-jose, passlib/bcrypt)
- **AI**: GPT-5.2 via emergentintegrations library
- **CI/CD**: GitHub Actions for APK builds (Gradle)

## Core Files
- `/app/backend/server.py` - All backend logic
- `/app/frontend/app/index.tsx` - Main app screen
- `/app/frontend/app/context/AuthContext.tsx` - Auth + push notification state
- `/app/frontend/app/_layout.tsx` - Root layout with AuthProvider
- `/app/.github/workflows/build-apk.yml` - APK build workflow

## What's Implemented

### Phase 1: Notepad History - DONE
- Local notepad history (AsyncStorage), switch between notepads, max 50 items

### Phase 2: Guest Account Limits - DONE
- 90-day expiration for guest notepads, expiration banners

### Phase 3: User Authentication - DONE (Feb 15, 2026)
- Registration/login with JWT, profile management, password change
- Bulk "Claim All Notepads" after login
- Server-side notepad merge in history, "Linked" badges
- **Testing**: 47/47 backend tests passed

### Phase 4: Premium Features - DONE (Feb 17, 2026)
- **Push Notifications**: Expo push tokens registered on login, triggered on web notepad view
- **Cron Job**: Background cleanup of expired notepads every 6 hours
- **Workflow Automation**: Webhook CRUD (create, list, delete), fires on notepad append
- **Export/Import**: Download notepad as .txt, .md, or .json
- **AI Summarization**: GPT-5.2 powered notepad content summarization
- **Testing**: 35/35 backend tests passed

## Prioritized Backlog

### P1 - Subscription Tiers
- Stripe integration for Free/Pro/Business plans
- Premium notepads that never expire

### P2 - Technical Improvements
- Rate limiting
- Pagination for large notepads
- Database indexes
- Social login (Google OAuth)
- Password reset flow

## DB Schema
- **notepads**: `{ id, code, owner_id, user_id, created_at, expires_at, account_type, entries: [{ text, timestamp }] }`
- **users**: `{ id, email, password_hash, name, account_type, push_tokens: [], created_at, updated_at }`
- **webhooks**: `{ id, user_id, url, events: [], secret, active, created_at }`

## API Endpoints
- Auth: register, login, /me, profile, change-password, notepads, link-notepad, link-notepads, push-token
- Webhooks: create, list, delete
- Notepad: create, get, lookup, append, clear, export, summarize
- Admin: cleanup-expired, stats
- Web: landing page (/), notepad view

## Test Credentials
- Email: test@test.com / Password: password123
