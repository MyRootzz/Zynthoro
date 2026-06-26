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

## What's Implemented (XPRIZE Jury Demo Account — done 2026-02-05)

**One-click demo for XPRIZE judges / investors**
- New `seed_jury_demo()` hook runs on every backend startup. Creates user `jury@zynthoro.ai` / `ZynthoroDemo2026!` with `is_demo=true`, plan `Enterprise Advanced`, `email_verified=true`, `twofa_enabled=false`, `onboarding_completed=true`. Force-resets on every boot so judges can never be locked out.
- Login bypass: `/api/auth/login` returns `stage='ok'` directly for `is_demo` accounts — no email verify, no 2FA setup gate. `is_demo` can ONLY be set by the seed (verified via signup-injection test).
- Seeded demo data (idempotent — only inserts if absent):
  - 5 team members at levels L9 / L7 / L5 / L3 / L1
  - 5 projects across Project Management, Marketing, Compliance, Sales, Operations
  - 6 invoices totalling €61,440 (€13,980 paid · €47,460 outstanding · 1 overdue)
- Frontend `/dashboard/projects` and `/dashboard/finance` render the full Projects table and Finance dashboard for demo users (via `GET /api/demo/projects` & `GET /api/demo/invoices`); non-demo users see the construction placeholder unchanged.

**Test results — iteration 12:**
- 10/10 new jury-demo tests PASS (login bypass, signup-injection hardening, demo endpoints, workspace isolation, idempotency)
- 116/116 backend regression PASS + 1 skipped by design
- Frontend E2E verified all 6 surfaces (login → dashboard → projects → finance → team → founder regression)

## What's Implemented (Internal Stripe-Event Alerts — done 2026-02-05)

**Every Stripe webhook → email to info@zynthoro.ai**
- New `email_service.send_stripe_alert(kind, event_type, …)` renders a branded HTML email (Zynthoro navy header, accent-coloured left border per event kind) and dispatches via Resend.
- Webhook handler now fires `asyncio.create_task(send_stripe_alert(...))` (fire-and-forget, non-blocking) for **every** recognised event:
  - `checkout.session.completed` (mode=subscription) → `subscribe` (Presale → paid), `upgrade`, or `downgrade` based on `_plan_rank` comparison
  - `checkout.session.completed` (kind=seat_addon) → `seats` with quantity
  - `customer.subscription.deleted` → `cancel`
  - `invoice.payment_failed` → `payment_failed` with amount
  - `customer.subscription.trial_will_end` → `trial_end`
  - Catch-all (updated / paid / refunded / expired) → `other`
- Robust: webhook returns 2xx even when Resend rejects (currently "domain not verified" until DNS is added). All plan-flip / extra-seats DB writes happen FIRST, alert is best-effort.

**Test results — iteration 11:**
- 22/22 new alert tests PASS (`test_stripe_webhook_alerts.py`) covering every event branch + fire-and-forget robustness
- 106/106 backend regression PASS + 1 skipped by design
- Mocked Resend failure verified: webhook still returns 2xx and plan flip persists

**Deployment readiness:** ✅ PASS — `deployment_agent` confirmed zero blockers.

## What's Implemented (Builder-Mode Live Stripe Widget — done 2026-02-05)

**Live MRR + ARR widget for founders**
- New backend module function `stripe_subscriptions.compute_stripe_mrr()` paginates `stripe.Subscription.list(status='active')`, normalises yearly → monthly, splits add-on seat revenue from plan revenue.
- New endpoint `GET /api/founder/stripe-metrics` (founder-only) — returns `{active_subs, mrr_eur, arr_eur, seats_mrr_eur, plan_breakdown[], seat_breakdown[], currency, fetched_at}`.
- New frontend `StripeMetricsCard.jsx` mounted in `BuilderModePanel` below the four StatCards: 3 totals tiles (Active subs · MRR · ARR), plan-breakdown table with % of MRR, seat add-on summary row, refresh button.
- Currently shows the pre-launch empty state (0 subs) — will fill itself the moment your first customer completes Stripe checkout.

**Test results — iteration 10:**
- 8/8 new tests PASS (5 math unit tests + 3 authz)
- 84/84 backend regression PASS, 1 skipped by design
- Frontend founder login → builder toggle → metrics card render → empty state → refresh → all verified
- Non-founder regression: no toggle, no card, /api/founder/stripe-metrics returns 403

## What's Implemented (Real Stripe Checkout — Fix 8 + Fix 9 wired LIVE — done 2026-02-05)

**Plan upgrades (Fix 8)**
- New module `/app/backend/stripe_subscriptions.py` with 7 PLAN_PRICE_IDS (Starter €499, Creator €699, Business €899, Agency €1,199, Enterprise Basic €2,499, Plus €3,999, Advanced €5,999).
- New endpoint `POST /api/checkout/subscription/session {plan_key}` returns a real `cs_live_*` Stripe Checkout URL in `subscription` mode.
- Frontend `ChangePlanDialog.jsx` now expands to all 7 plan cards (data-testid pattern `changeplan-{key-dashed}`), clicks redirect to Stripe-hosted checkout.

**Extra seats (Fix 9)**
- SEAT_PRICE_IDS for Business (€4.99/seat) and Agency (€3.99/seat). Enterprise = unlimited (400 with friendly message). Starter/Creator → 400 with upgrade prompt.
- New endpoint `POST /api/checkout/seats/session {quantity}` (bounds 1..100).
- Frontend `Team.jsx` "Add seats — checkout" button (data-testid='seats-checkout-btn') redirects to Stripe.

**Webhook (full subscription event handling)**
- `/api/webhook/stripe` now uses raw Stripe SDK `construct_event()` first (handles ALL event types), falls back to Emergent wrapper for the legacy Starter one-time flow.
- `checkout.session.completed` (mode=subscription) → sets `user.subscription_plan`, `stripe_subscription_id`, `stripe_customer_id`; or for seat-addon kind, `$inc user.extra_seats` by quantity.
- `customer.subscription.deleted` → marks `subscription_status='cancelled'`.

**Return handlers**
- `?checkout=success` / `?checkout=cancelled` on `/dashboard/settings` and `/dashboard/team` show success/cancel toasts and clean the URL.

**Test results — iteration 9:**
- 21/21 new Stripe checkout tests PASS (`test_stripe_subscription_checkout.py`)
- 48/48 regression PASS + 1 skipped by design
- All 7 plan keys produce valid `cs_live_*` URLs
- Validation: invalid plan_key → 422, no auth → 401, billing_exempt → 400 with friendly message
- Webhook: no/invalid signature → 400 (real signed events only verifiable via Stripe CLI in prod)

**Deployment readiness:** ✅ PASS (deployment_agent confirmed no blockers).


## What's Implemented (Zyntha Caption AI — done 2026-02-05)

**Zyntha Caption AI (Marketing & Content > Compose)**
- New backend endpoint `POST /api/marketing/caption` calls Gemini 2.5 Flash with a strict JSON-mode prompt. Available to ALL paying tiers (Starter included) — Zyntha's free hook.
- Returns `{caption, hashtags[5-10], provider, model, platform, badge}` in 2-5s.
**Zyntha Caption AI (Marketing & Content > Compose)**
- New backend endpoint `POST /api/marketing/caption` calls Gemini 2.5 Flash via emergentintegrations with a strict JSON-mode system prompt. Available to ALL paying tiers (Starter included) — Zyntha's free hook.
- Returns `{caption, hashtags[5-10], provider, model, platform, badge}` in 2-5s.
- Robust `_coerce_caption_json` parser handles raw JSON, fenced JSON, AND mid-truncation (regex extraction of caption + hashtags from partial output). max_tokens=1500.
- Frontend `MarketingContent.jsx` Compose panel now has a platform select (IG/FB/LinkedIn/TikTok/X/YouTube), a "Generate caption with Zyntha" button (spinner during call), hashtag chips below the textarea, and a "Copy caption + tags" button that puts `caption\\n\\n#tag1 #tag2 …` on the clipboard.

**Verification (iterations 7 + 8):**
- 11/11 caption pytest pass across all 6 platforms.
- Full backend suite: 55 passed, 1 skipped.
- Manual end-to-end via Playwright: empty-idea toast works, no backend call on empty, hashtag chips render, copy button copies the right format.

**Deployment readiness:** ✅ PASS (deployment_agent confirmed no blockers).

## What's Implemented (Mega-Batch Fixes 4–13 — done 2026-02-05)

**Fix 4 — Signup legal checkbox**
- Required "I agree to Terms & Privacy Policy" checkbox on `/signup` linking to `/legal/terms-of-service` and `/legal/privacy-policy`. Submit button disabled until checked. data-testid: `signup-agree-legal`.

**Fix 5 — Social Media Studio + plan-gating (UI shell)**
- New page `/dashboard/marketing` (`MarketingContent.jsx`) with: 6 platform tiles (FB, IG always available; LinkedIn, TikTok, X, YouTube unlocked from Creator), 7 tabs (compose, calendar, photo, video, campaigns, analytics, clients).
- Per-plan gating: Calendar/Photo Suite/Video Suite → Creator; Campaigns/Analytics → Business; Clients → Agency.
- OAuth + real photo/video AI deferred per user choice (UI shell only).

**Fix 6 — UpgradeLock component**
- `UpgradeLock.jsx` (card + compact variants) used across the platform. Always shows what's missing + an "Upgrade to <plan>" CTA → `/dashboard/settings#billing`. Never hard-blocks.

**Fix 7 — Employee hierarchy 1-10**
- Backend (`server.py`): `TeamInviteIn.level (1-10)`, `PLAN_MAX_LEVEL` (Business 5 / Agency 7 / Enterprise 10), `team_invite` returns HTTP 403 if level exceeds plan max.
- Frontend (`Team.jsx`): new "Level" column with coloured badge (`team-level-${i}`), level Select in invite dialog (`invite-level`) showing only plan-allowed levels.
- New backend test file `tests/test_team_level.py` (4 tests, all passing).

**Fix 8 — Change Plan dialog**
- `ChangePlanDialog.jsx` invoked from Settings → Billing section (`change-plan-btn`). Shows all 5 plans with current-plan highlight; non-Starter cards show "Coming soon" (Stripe price IDs not yet wired).

**Fix 9 — Buy extra seats**
- `Team.jsx` seats dialog now correctly branches:
  - Business/Agency → chips + price preview
  - Enterprise → "Unlimited included"
  - Starter/Creator → "Upgrade to Business" copy + CTA navigating to `/dashboard/settings#billing` (`seats-upgrade-cta`)

**Fix 10 — User ↔ Builder mode**
- Sidebar toggle `switch-mode` already wired; `BuilderModePanel` renders for `is_founder` users only.

**Fix 11 — Cookie settings**
- `CookieSettingsProvider` mounts a first-visit banner (`cookie-banner`) + Customize modal (`cookie-settings-modal`) with locked "Necessary" + toggle "Functional" + toggle "Analytics". Saves to `localStorage['zy_cookie_prefs_v1']`. Footer link (`footer-cookie-settings`) reopens the modal anywhere.

**Fix 12 — Two pricing comparison tables**
- New section `PricingComparisonTables.jsx` mounted on Home between Pricing and Enterprise sections. Table 1 (`pricing-table-replacement`) = 13 tool categories vs. cost vs. included-from-plan. Table 2 (`pricing-table-savings`) = 5 plan rows with gold-highlighted Enterprise row. Blue (#1A4FFF) headers, mobile cards on <768px.

**Fix 13 — Mobile responsive audit**
- `index.css`: `@media (max-width:640px)` block ensures ≥44px touch targets, smaller hero typography, tighter container padding.
- `DashboardLayout.jsx`: main padding `px-3 sm:px-6` instead of `px-4 sm:px-8`.
- `TopBar.jsx`: 64px height on mobile (was 72px), truncated title, smaller font.
- Team table: status + 2FA + last-login columns hidden on small screens (`hidden sm:table-cell`, `hidden md:table-cell`).
- New marketing section `AnyDeviceSection.jsx` ("Works on any device") with CSS-only phone/tablet/desktop mockups.

**Test results — iterations 5 + 6**
- 44/44 backend tests pass + 1 skipped by design.
- All 13 fixes verified end-to-end via Playwright.
- 3 minor deviations from iteration 5 (Buy-seats Starter copy, Enterprise comma, footnote asterisk) all fixed and re-verified in iteration 6.

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


## Changelog
### 2026-02-26 — Launch blockers removed + Jury Tour
- Removed "This module is part of the upcoming launch — June 30, 2026" message from `ModulePlaceholder.jsx`. Every ERP module now renders a functional landing view with quick actions and module tiles (Planning, Time Tracking, Sales, Finance, Accounting, Projects, HR, Operations, Marketing, Communication, Compliance, Settings).
- Replaced every `<ComingSoon>` card in `MarketingContent.jsx` (campaigns, analytics, multi-client, calendar) with `<FeatureReady>` "Included in your workspace" cards.
- Plan gating for demo / `is_unlimited` / Enterprise-tier users now grants full access across Marketing tabs (`fullAccess` flag short-circuits all `canStarter/canCreator/canBusiness/canAgency` checks).
- New `JuryTour.jsx` 5-step (6 incl. welcome) tour overlay mounted in `DashboardLayout`. Auto-opens once for `is_demo` users, persists via `localStorage`, with a re-openable "Jury tour" pill at bottom-left of the dashboard.


### 2026-02-26 — Operations & Production module + Voice AI input
- New `operations_module.py` router exposing `/api/operations/*` for recipes, BOMs, production orders, work orders, quality inspections, lots and cost summary.
- Plan gating via `_require_plan()`: Business+ → recipes/orders/work orders/costs · Agency+ → BOMs/QC · Enterprise+ → traceability. Demo/`is_unlimited`/`billing_exempt` bypass everything.
- Auto cost roll-up on recipes (material + labour + overhead → total → per-unit). Auto lot/order number generation (PO-YYYYMMDD-XXXXX, LOT-YYMMDD-XXXXXX). Multi-level BOM with max_level + total cost calc.
- Lot traceability endpoint returns full graph (lot + production order + upstream raw lots). Recall flips status.
- Jury demo seed populates 3 recipes (sourdough, juice, lip balm), 3 production orders (planned/in_progress/completed), 2 QC inspections (1 pass, 1 fail), 3 lots (2 active, 1 recalled).
- New `useVoiceInput.js` hook + `VoiceButton.jsx` component using browser-native Web Speech API. Mic button wired into all 4 assistants (Zyntha, Thoro, Zyona, Zynthoro Assist floating). Live interim transcription → final text auto-sends. Graceful fallback (disabled MicOff) on unsupported browsers.
- New `OperationsModule.jsx` frontend with 7 tabs and full CRUD: Recipes & Formulas, Bill of Materials, Production Orders, Work Orders, Quality Control, Lot Traceability, Production Costs.
- New homepage sections: `ProductionSection.jsx` ("Replace SAP & Oracle for €899/month" + 6 features + industry tags) and `VoiceAISection.jsx` ("Speak your mind. Zynthoro listens." dark hero with gold mic).
- `Comparison.jsx` rebuilt: now shows Zynthoro vs SAP, Oracle NetSuite, AFAS, Design tools — including new "Voice input on AI" and "Recipes, BOM, traceability" rows.
- Validated: 17/17 backend tests pass, frontend smoke tests pass, deployment readiness PASS.


### 2026-02-26 — Jury lockout immunity + Homepage Voice Tour
- BUG FIX: `auth_login` in `server.py` now looks up the user document first; if `is_demo=True`, `check_lockout` and `record_failed_login` are skipped entirely. Result: jury demo can NEVER be rate-limited. Non-demo accounts retain full brute-force protection.
- Cleared stale lockout / `failed_login_count` / `locked_until` state on the `jury@zynthoro.ai` user doc.
- Interactive Voice Tour: `VoiceAISection.jsx` now contains an unauthenticated try-the-mic widget (`home-voice-tryout`) with live transcription preview, "clear transcript" reset, and graceful fallback on non-Chromium browsers. Lets prospects experience the voice differentiator before signup.
- Validated by testing_agent (iteration_14.json — 5/5 backend pass, frontend mounted correctly, non-demo accounts still hit 429). Deployment readiness PASS.


### 2026-02-26 — Voice tryout lead capture
- New `POST /api/voice-tryout` — public/anonymous endpoint that stores homepage voice tryout transcripts in `db.voice_tryout_leads` (transcript, email?, language, user_agent, ip, is_test auto-flagged via `_is_test_signup`).
- New `GET /api/founder/voice-tryouts` — founder-only, returns `{leads, count, with_email_count, anonymous_count, test_count}` with test rows filtered out.
- `VoiceAISection.jsx` now fires anonymous POST on first transcript and reveals an email-capture form ("Liked that? Drop your email…") — successful submit shows a green confirmation card.
- Validated by testing_agent (iteration_15.json: 8/8 backend pass + full frontend lead flow). Deployment readiness PASS.


### 2026-02-26 — Daily founder digest email
- New `daily_digest.py` module: aggregates last-24h presale signups + voice-tryout leads (test rows filtered), renders branded HTML, sends via Resend to `info@zynthoro.ai`.
- Background asyncio scheduler (`start_scheduler`) wakes hourly and fires once when UTC hour matches `DIGEST_HOUR_UTC` (default 07 UTC = 08:00 CET / 09:00 CEST). Dedupe persists via `db.system_state`.
- Manual founder endpoints: `POST /api/founder/digest/send` (default dedupes today; `?force=true` re-sends) + `GET /api/founder/digest/preview` (returns rendered HTML + counts without sending).
- Validated by testing_agent (iteration_17: 10/10 GREEN). Deployment readiness PASS.


### 2026-02-26 — Builder Mode digest card
- Added `DigestCard` to `BuilderModePanel.jsx`: shows last-24h KPI tiles (presale, voice leads, anonymous tryouts), schedule note ("Auto-sent to info@zynthoro.ai every day at 07:00 UTC"), and a prominent blue "Send test now" button. After a successful send, inline green confirmation with the timestamp appears.
- UI smoke-tested end-to-end (founder login → Builder mode → click Send test now → success toast + inline confirmation). Backend already 10/10 green in iteration_17. Deployment readiness PASS.
