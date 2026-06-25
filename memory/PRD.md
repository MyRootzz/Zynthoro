# Zynthoro — Product Requirements Document

## Original Problem Statement
Build **Zynthoro Phase 1: Foundation & Homepage** — the marketing homepage for a next-gen AI ERP ecosystem that replaces SAP, Oracle, HubSpot, Canva, CapCut, Mailchimp etc.

- Tagline: "The Next-Gen AI ERP Ecosystem"
- Subtitle: "One platform. One AI. One truth."
- Powered by Anthropic Claude API · Selected for Claude for Startups
- Company: Casa Haya International BV (Casa De La Haya Holding BV)
- Founder: Ramona Vijfvinkel
- Launch: June 22, 2026

## User Choices (Phase 1)
- ✅ Capture presale signups in MongoDB
- ✅ English only (NL deferred)
- ✅ Skip founder account until Phase 2 (auth)
- ✅ Watch Demo scrolls to 12 Domains section
- ✅ Stick exactly to Inter/Helvetica spec

## Design System (frozen for the brand)
- Background White `#FFFFFF` · Text Black `#000000` · Secondary `#333333`
- Accent royal blue `#1A4FFF` · Premium gold `#D4AF37` (logo / Enterprise / badges only)
- Footer navy `#0A1628`
- Fonts: Inter (with Helvetica Neue fallback)
- Section spacing 120px, element spacing 60px

## Architecture
- **Frontend**: React 19 + CRA/craco + Tailwind + shadcn/ui + lucide-react + sonner. Pages under `/app/frontend/src/pages`, sections under `/app/frontend/src/components/sections`, layout under `/app/frontend/src/components/layout`.
- **Backend**: FastAPI + Motor (MongoDB) at `/app/backend/server.py`. Routes prefixed `/api`.
- **DB collections**: `presale_signups` (id, name, email, company, plan_interest, created_at), `status_checks`.

## What's Implemented (Phase 2 — done 2026-06-18)
- **Auth**: JWT (bcrypt), signup, email verification (idempotent, dev token returned + logged), login, brute-force lockout keyed by email, password reset (dev token), logout.
- **2FA**: TOTP (pyotp + QR base64) primary, email-code fallback (dev_code returned + logged). SMS marked "Coming soon".
- **Founder owner unlimited** auto-seeded on startup (regie@myrootzz.com / Zynthoro2026!), is_founder, is_unlimited, billing_exempt, Enterprise Unlimited plan, email_verified.
- **Onboarding**: 6-step wizard (welcome, company, first action, meet Assist, ready, redirect).
- **Dashboard**: blue sidebar (12 modules + Team + Settings + 3 AI assistants), top bar with greeting & plan badge, 4 KPI cards, 4 quick actions, AI Suggestions, empty-state activity feed.
- **Zynthoro Assist** floating bubble — always visible in /dashboard/*, Claude Sonnet 4.5 via Emergent universal key, history persisted in `ai_messages`.
- **Three specialised AI assistants** (`/dashboard/zyntha`, `/dashboard/thoro`, `/dashboard/zyona`) — each with own system prompt, gradient avatar, starter chips, chat persistence.
- **Teams**: list + invite (role select per plan) + buy-seats placeholder modal.
- **Builder Mode** (founder only): stats, feature flags (4 toggles), presale signups table.
- **Stripe**: completely deferred — `/api/checkout/status` returns `{enabled:false, message:"…June 22, 2026."}` per user choice.
- **Logo**: full gold `ZYNTHORO` everywhere (homepage navbar/footer, auth pages on dark chip, dashboard sidebar).
- **Tests**: 25/25 backend tests passing (`/app/backend/tests/test_phase2_auth_dashboard_ai.py`).

## What's Implemented (Streaming + Branded Export + Final Legal Polish — done 2026-02-05)

**Fix 1 — Streaming AI responses (no more truncation)**
- New `POST /api/ai/stream` SSE endpoint in `server.py` emitting `event: meta` (provider/model/badge/session_id), `event: delta` ({content}), `event: error`, `event: done` (latency_ms, chars).
- `max_tokens` raised from 900 → 4000 for all four assistants.
- `chat_stream` in `ai_assistants.py` persists user + final assistant messages and writes ai_logs after stream completes.
- Frontend reads SSE via `fetch()` + ReadableStream (`/app/frontend/src/lib/aiStream.js`), renders tokens progressively with a pulsing blue caret.

**Fix 2 — Corrected system prompts**
- `SP_THORO_BASIC` / `SP_THORO_PRO` now contain an ABSOLUTE RULE forbidding Shopify, WooCommerce, BigCommerce, HubSpot, Notion, QuickBooks etc. as primary recommendations — Zynthoro's Sales Admin / Invoicing & Finance / Marketing & Content / Operations domains come first.
- `SP_ZYONA` explicitly bans inventing fake assistant names (Lexara, Finara, Creova, Marketa, Operea, Legara, Salesa, HRova, Procura, Brandara, Insighta…) and pins the universe of assistants to exactly four real ones.
- Verified by testing agent against the actual model outputs in iteration_3.

**Fix 3 — Copy + Download-PDF buttons on every assistant message**
- `/app/frontend/src/lib/aiExport.js` exposes `stripMarkdown` (no **, _, #, ` symbols) and `downloadAssistantPdf` (jsPDF — navy header with gold ZYNTHORO wordmark, blue #1A4FFF accent line, ISO date, white background, `zynthoro.ai` footer).
- `AssistantActions.jsx` renders the action row beneath every completed assistant reply on both the per-page assistant route and the floating Zynthoro Assist bubble.
- Verified by testing agent: PDF download triggered with filename pattern `<assistant>-YYYY-MM-DD.pdf`; clipboard content is plain text.

**Fix 4 — Canonical legal page paths + GDPR content**
- New routes: `/legal/privacy-policy`, `/legal/terms-of-service`, `/legal/cookie-policy`, `/legal/dpa`, `/legal/sla`.
- Old short paths `/legal/privacy`, `/legal/terms`, `/legal/cookies` now redirect via `<Navigate to=…>`.
- Every legal page now references `Casa Haya International BV` + `KvK 99196581` + `info@zynthoro.ai`.
- Privacy + DPA + SLA all explicitly mention Republic of Ireland (eu-west) EU hosting.
- Footer "Legal" column has all five `data-testid='footer-link-*'` Link entries.

**Test results — iteration 3 + iteration 4**
- 9/9 new streaming + prompt-fix backend tests PASS.
- 24/25 phase-2 regression PASS (1 skipped by design — email-2FA can't be tested when Resend is live).
- 5/5 legal pages PASS (Ireland mention added to SLA in retest, iteration 4 confirmed).
- Streaming UI verified progressive (msg length grew 151 → 161 → 628 → 1114 chars during a single send).
- Copy + Download-PDF buttons verified on both the page-level assistants and the floating bubble.

## Phase 3 (queued — pasted by user during Phase 2)
- Full Pricing page (9 plans + comparison table + FAQ)
- 12 domain detail pages + /domains overview
- /enterprise page (14 modules + comparison + demo form)
- /about page (Casa Haya International BV, KvK, VAT)
- /legal/{privacy,terms,cookies,dpa,sla} pages
- Navbar "About" link + footer legal links

## What's Implemented (Phase 1 — done 2026-06-18)
- Homepage with 9 sections in order: Navbar, Hero, Social Proof, Why Zynthoro, 12 Domains grid, Pricing (4 plans), Zynthoro Assist (blue), Comparison table, Presale CTA, Footer.
- Sticky blue navbar with mobile hamburger; gold+white ZYNTHORO logo; "Start Free Trial" CTA.
- Presale signup flow: dialog (name/email/company/plan_interest) → `POST /api/presale/signup` → MongoDB → success state.
- Duplicate email returns 409 with friendly toast.
- `GET /api/presale/count` for future urgency widgets.
- SEO: meta title + description; smooth scroll; reveal-on-scroll animations.
- Test IDs centralized in `/app/frontend/src/constants/testIds/home.js`.
- Backend tests at `/app/backend/tests/test_presale.py` — 7/7 passing.

## User Personas
- **SME founders & operators** (EU, 5–50 staff) who currently juggle SAP/HubSpot/Canva/etc. and want one AI-native platform.
- **Agencies** managing multiple clients.
- **Enterprise** buyers needing SSO + SLA + EU compliance.

## Core Requirements (static)
- All `/api` prefix on backend; frontend always uses `REACT_APP_BACKEND_URL`.
- MongoDB via `MONGO_URL` / `DB_NAME` from env.
- No hardcoded secrets. No emojis in icons (use lucide-react).

## Backlog
### P0 — Phase 2 (next)
- JWT auth + Emergent Google login choice (per integration_playbook_expert_v2)
- Founder owner account: `regie@myrootzz.com`, billing exempt, unlimited
- Dashboard shell with Zynthoro Assist sidebar (Claude API)
- Real presale checkout (Stripe) for founding members

### P1 — Phase 3
- 12 domain detail pages
- Full Pricing page (all 9 tiers), Enterprise page
- AI assistants Zyntha / Thoro / Zyona (Claude tools)
- Dutch (NL) language toggle
- Legal pages: Privacy, Terms, Cookie, DPA
- Blog + Careers + Press pages

### P2
- Analytics dashboards for founder
- Marketplace of integrations
- Mobile-first redesign of dashboard
