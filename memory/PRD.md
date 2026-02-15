# PasteBridge - Product Requirements Document

## Problem Statement
An Android application that listens to the device's clipboard. When text is copied, the app frictionlessly pushes the text to a web-based notepad accessible via a memorable, short code.

## Architecture
- **Backend**: FastAPI + MongoDB (server.py)
- **Frontend**: Expo (React Native) with expo-router
- **Database**: MongoDB (notepads, users collections)
- **Auth**: JWT-based (python-jose, passlib/bcrypt)
- **CI/CD**: GitHub Actions for APK builds (Gradle)

## Core Files
- `/app/backend/server.py` - All backend logic
- `/app/frontend/app/index.tsx` - Main app screen
- `/app/frontend/app/context/AuthContext.tsx` - Auth state management
- `/app/frontend/app/_layout.tsx` - Root layout with AuthProvider
- `/app/.github/workflows/build-apk.yml` - APK build workflow

## What's Implemented

### Phase 1: Notepad History - DONE
- Local notepad history (AsyncStorage), switch between notepads, max 50 items

### Phase 2: Guest Account Limits - DONE
- 90-day expiration for guest notepads, expiration banners, admin cleanup endpoint

### Phase 3: User Authentication - DONE (Feb 15, 2026)
- User registration/login with JWT tokens
- Auth endpoints: register, login, /me, profile update, password change
- AuthContext with SecureStore (native) / AsyncStorage (web) token storage
- Auth modal UI in mobile app (login/register forms)
- Authenticated notepad creation (linked to user, 365-day expiration)
- Link guest notepads to user account
- Get user's notepads endpoint
- Profile modal with logout
- **Testing**: 27/27 backend tests passed (100%)

## Prioritized Backlog

### P0 - Next Up
- Link Notepads to User Accounts (auto-associate on create when logged in)
- Migrate Guest Notepads to User Account after login

### P1 - Phase 4: Premium Features
- Subscription tiers (Free/Pro/Business)
- AI summarization of notepad content
- Workflow automation APIs
- Export/import functionality

### P2 - Technical Improvements
- Backend cron job for expired notepad cleanup
- Rate limiting
- Pagination for large notepads
- Database indexes

## DB Schema
- **notepads**: `{ id, code, owner_id, user_id, created_at, expires_at, account_type, entries: [{ text, timestamp }] }`
- **users**: `{ id, email, password_hash, name, account_type, created_at, updated_at }`

## Test Credentials
- Email: test@test.com / Password: password123
