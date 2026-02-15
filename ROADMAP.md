# PasteBridge Product Roadmap

## Vision
Transform PasteBridge from a simple clipboard-to-web tool into a comprehensive cross-device productivity platform with AI-powered workflow automation.

---

## Phase 1: Notepad History ✅ (Current - MVP Enhancement)
**Status: COMPLETE**

### Features Implemented:
- [x] Local storage of notepad history on device (AsyncStorage)
- [x] Display list of active notepads with metadata (code, entry count, last used)
- [x] Switch between multiple notepads seamlessly
- [x] Remove individual notepads from history (long press)
- [x] Create new notepads while preserving history
- [x] Validate notepads against server on history load
- [x] Maximum 50 notepads stored in history

### Technical Notes:
- History stored in AsyncStorage under key `pastebridge_notepad_history`
- Each history item contains: code, created_at, last_used, entry_count
- History validated on modal open to remove orphaned entries

---

## Phase 2: Guest Account Limits ✅ (Current - Complete)
**Status: COMPLETE**

### Features Implemented:
- [x] Add `expires_at` field to notepad schema (90 days from creation)
- [x] Add `account_type` field (guest/user/premium) to notepads
- [x] Display expiration warning in app (< 7 days remaining)
- [x] Display expiration info in web view (banner with date and days remaining)
- [x] Backend returns expiration info in API responses
- [x] Handle expired notepads (410 Gone response)
- [x] Admin stats endpoint for monitoring
- [x] Admin cleanup endpoint for expired notepads
- [x] Warning banner styling (amber color) for expiring soon notepads
- [x] History modal shows days remaining for each notepad
- [x] "Expiring" badge on notepads close to expiration

### Backend Changes:
```python
class Notepad(BaseModel):
    # existing fields...
    account_type: str = "guest"  # guest | user | premium
    expires_at: datetime = Field(default_factory=lambda: datetime.utcnow() + timedelta(days=90))
```

### API Endpoints Added:
- `GET /api/admin/stats` - Get notepad statistics
- `POST /api/admin/cleanup-expired` - Cleanup expired notepads

---

## Phase 3: User Authentication ✅
**Status: COMPLETE (Feb 2026)**

### Features Implemented:
- [x] User registration (email/password)
- [x] User login with JWT tokens (30-day expiration)
- [x] Link existing guest notepads to user account (single + bulk)
- [x] User profile management (name update)
- [x] Password change flow
- [x] Auth state persistence (SecureStore on native, AsyncStorage on web)
- [x] Auto-link notepads to user on authenticated creation
- [x] Bulk "Claim All Notepads" after login/registration
- [x] Merge server-side user notepads with local history
- [x] "Linked" badge on history items
- [ ] Social login (Google OAuth via Emergent) - FUTURE
- [ ] Password reset flow - FUTURE

### Backend Changes:
- `users` collection in MongoDB
- JWT token generation and validation (python-jose)
- Password hashing (passlib/bcrypt)
- Endpoints: register, login, /me, profile update, change-password, user notepads, link-notepad, link-notepads (bulk)

### Frontend Changes:
- AuthContext provider with global state
- Auth modal (login/register forms)
- Profile modal with logout
- Guest banner prompting sign-up
- Secure token storage (expo-secure-store)
- Claim All Notepads modal after login
- Server-side notepad merge in history view

---

## Phase 4: Premium Features
**Status: PLANNED**
**Target: Sprint 5-8**

### 4.1 Subscription Tiers
- [ ] Free tier (90-day retention, 50 notepads)
- [ ] Pro tier ($4.99/mo - 1 year retention, 200 notepads)
- [ ] Business tier ($14.99/mo - unlimited retention, unlimited notepads)

### 4.2 Storage Packages
- [ ] Extended retention options
- [ ] Increased notepad limits
- [ ] Larger text entry limits
- [ ] Attachment support (images, files)

### 4.3 AI Summary Integration
- [ ] Integrate LLM for text summarization
- [ ] Auto-summarize long clipboard captures
- [ ] Daily/weekly digest summaries
- [ ] Smart categorization of entries
- [ ] Key points extraction

### 4.4 Workflow Automation
- [ ] Webhook integrations
- [ ] API access for automation
- [ ] Zapier/Make integration
- [ ] Custom triggers and actions
- [ ] Export to external services (Notion, Google Docs, etc.)

### 4.5 Team Features (Business)
- [ ] Team workspaces
- [ ] Shared notepads
- [ ] Access controls
- [ ] Activity logs
- [ ] Admin dashboard

---

## Phase 5: Advanced Features
**Status: FUTURE**

### Potential Features:
- [ ] End-to-end encryption
- [ ] Offline mode with sync
- [ ] Desktop apps (Electron)
- [ ] Browser extensions
- [ ] Voice-to-text capture
- [ ] OCR from screenshots
- [ ] Cross-platform sync
- [ ] Tags and folders
- [ ] Search across all notepads
- [ ] Dark/light theme toggle

---

## Technical Debt & Improvements

### Performance:
- [ ] Implement pagination for large notepads
- [ ] Add caching layer (Redis)
- [ ] Optimize database queries with indexes

### Security:
- [ ] Rate limiting
- [ ] Input sanitization audit
- [ ] Security headers
- [ ] HTTPS enforcement

### Monitoring:
- [ ] Error tracking (Sentry)
- [ ] Analytics integration
- [ ] Performance monitoring
- [ ] Uptime monitoring

---

## Release Notes

### v1.1.0 (Current)
- Added notepad history feature
- Users can now manage multiple notepads
- Improved copy button reliability
- Fixed scroll reset issue on web view
- Live updating without page refresh

### v1.0.0
- Initial MVP release
- Basic clipboard capture and send
- Memorable code generation
- Web notepad view
- Share/copy functionality

---

## Contributing

This roadmap is a living document and will be updated as priorities evolve based on user feedback and business requirements.

Last Updated: February 2026
