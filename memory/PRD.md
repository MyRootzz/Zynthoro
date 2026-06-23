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
