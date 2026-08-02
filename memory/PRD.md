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
- **Founder owner unlimited** auto-seeded on startup (regie@myrootzz.com xxxxxxxxx), is_founder, is_unlimited, billing_exempt, Enterprise Unlimited plan, email_verified.
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


### 2026-02-26 — Voice tryout leads inline in Builder Mode
- Added `VoiceLeadsPanel` to `BuilderModePanel.jsx`: header shows "Voice tryout leads · N (M anonymous tryouts not shown)", table renders the last 10 with-email leads (email · transcript snippet · language · timestamp). Backend already exposed via `GET /api/founder/voice-tryouts` (tested 8/8 GREEN in iteration_15).
- UI smoke-tested: panel rendered 3 lead rows with transcripts (`"test"`, `"I want to try the voice flow"`, `"Schedule a sourdough batch"`) at the expected positions. Deployment readiness PASS.


### 2026-02-26 — CSV export on Builder Mode lead panels
- New `/app/frontend/src/lib/csvExport.js` — tiny RFC-4180-safe CSV exporter (escapes quotes/commas/newlines, prefixes UTF-8 BOM so Excel/Numbers auto-detect encoding).
- "Export CSV" buttons added to both **Presale signups** and **Voice tryout leads** panels. Filenames stamped with today's date (e.g. `zynthoro_voice_leads_20260226.csv`).
- Voice export includes full set of fields: email, transcript, language, user_agent, ip, created_at — ready for CRM import or sheet pivot.
- Buttons auto-disable when the list is empty.
- E2E verified via Playwright: Voice CSV downloaded (407B) with correct header, 3 rows, BOM, RFC-4180-quoted transcript. Deployment readiness PASS.


### 2026-02-26 — Auto-injected company context for AI assistants
- New `_build_user_context()` helper in `ai_assistants.py` renders a compact "## Company context" block (company, industry, country, headcount, website, primary user, plan) — only fields present on the user record are included. Returns empty string for blank profiles (no broken context).
- `chat_complete`, `chat_stream` and `generate_caption` all accept `user_context: Optional[Dict]` and prepend the block to the system prompt. Invisible to the user — they never sent it as a message.
- Server.py call sites updated: `POST /api/ai/chat`, `POST /api/ai/stream`, `POST /api/marketing/caption` now all pass `user_context=user`.
- Jury demo enriched: `company_industry='AI / SaaS · ERP for SMEs'`, `company_country='Netherlands'`, `company_employees='10-50'`, `company_website='https://zynthoro.ai'`.
- Validated by testing_agent (iteration_18: **6/6 GREEN**, new regression suite `test_ai_company_context.py`). End-to-end smoke: Zyntha now answers "You are working at Zynthoro Demo Workspace, an AI-native ERP platform for SMEs" without that info being in the user message.


### 2026-02-26 — AI sees indicator + Beta Founding Member program
- New `AISeesIndicator.jsx` — subtle 12px line (`AI sees: [company] · [industry]`) reading from `useAuth().user`. Renders nothing when both fields are empty. Mounted on `AssistantPage` (Zyntha, Thoro, Zyona) and the floating `AssistFloating` bubble.
- New beta program in `stripe_subscriptions.py`:
  - `ensure_beta_price()` idempotently creates a Stripe Product+Price (LIVE) the first time it's called; subsequent calls reuse the existing IDs. Uses `Product.search(metadata['kind']:'beta_founder')` for reliable lookup.
  - `beta_status()` returns `{price_id, product_id, amount_eur, spots_total: 100, spots_filled, spots_remaining, capped}`.
  - `create_beta_session()` opens a Stripe Checkout in subscription mode with `metadata.kind='beta_founder'` and `subscription_data.metadata.locked_price='1'`.
- Public endpoints: `GET /api/beta/status`, `POST /api/beta/checkout` (returns 410 Gone when cap is hit).
- New page `SubscribeBeta.jsx` at `/subscribe/beta` — gold/blue hero with live counter ("100 of 100 spots remaining"), progress bar, perks list, €4.99/month card with optional email + "Claim my Founding Member spot" CTA. Auto-redirects to `/#pricing` when capped.
- **Stripe LIVE created**: `product_id=prod_Um9oU3QSQPlZWt`, `price_id=price_1TmbUx5sy2phCvUrUL20uyof` (€4.99 EUR/month recurring).
- Validated by testing_agent (iteration_19: 7/7 GREEN). Deployment readiness PASS.


### 2026-02-26 — Stripe live-account migration + payment-link wiring
- `.env`: new `STRIPE_SECRET_KEY` (sk_live_51TlqBi…) and new `STRIPE_PUBLISHABLE_KEY`. Old keys retired.
- `stripe_subscriptions.py`: replaced `PLAN_PRICE_IDS` with `PLAN_CATALOG` (per-plan `product_id` + `payment_link` + `amount_eur` + `label`). Lazy price-resolver `_price_id_for_product()` caches the active recurring EUR price for the in-app upgrade flow. Reverse map `_PRODUCT_TO_PLAN` buckets MRR by `price.product` instead of price_id.
- New product IDs wired: Starter `prod_UmAR0H01lNwXqW` · Creator `prod_UmAS6hf1gSEPrY` · Business `prod_UmAUa7Hg41OB3z` · Agency `prod_UmAVqO1W9DBkVq` · Enterprise Basic `prod_UmAWmouNUB5YWz` · Plus `prod_UmAXphGXtJGWml` · Advanced `prod_UmAYIa6bLkc0sG` · Beta `prod_UmAQUfqoR63MYR`.
- Beta refactor: `ensure_beta_price()` accepts any active EUR price (handles user's one-time price config); `count_beta_filled()` falls back to counting paid Checkout sessions when Stripe rejects `Subscription.list` for non-recurring prices; `create_beta_session()` returns the Stripe Payment Link directly (subscription semantics live in the user's Stripe dashboard).
- Seats add-on temporarily disabled (`SEAT_PRICE_IDS = {}`, `create_seats_session` raises `ValueError`) until refreshed on the new account.
- New public endpoint `GET /api/pricing/catalog` exposes the entire plan catalog with payment links.
- `Pricing.jsx` rewired: CTAs now read from `/api/pricing/catalog` and redirect via `window.location.href` to the matching `buy.stripe.com/...` link (no backend round-trip). Prices updated: Starter €99 · Creator €699 · Business €899 · Agency €1,199 · Enterprise from €2,499. Enterprise → talks to sales.
- `SubscribeBeta.jsx`: Claim CTA now refreshes status, then redirects directly to the Stripe Payment Link (with optional `prefilled_email`).
- Test suite updated: `test_stripe_metrics.py` uses new `_plan_item()` helper that stamps `price.product` with real product IDs. Seats test marked skip. **7 passed, 1 skipped**.
- Validated by testing_agent_v3_fork (iteration_20: all GREEN, no action items). Deployment readiness PASS.


### 2026-02-26 — Beta signup Slack/Discord webhook ping
- New `webhook_notifier.py` module — auto-detects Slack (Block Kit), Discord (embeds), or generic JSON from the URL pattern. Fire-and-forget, never raises.
- Feature flag `beta_webhook_url` added (string, default empty) to `db.feature_flags`. Configurable from Builder Mode > Feature flags via a new `BetaWebhookField` component (paste URL → Save → Send test).
- New `POST /api/founder/beta-webhook/test` (founder-only) sends a sample "New Beta Founder (TEST)" ping. Returns `{sent, kind}` so the UI can show success/failure + the auto-detected platform.
- Stripe webhook handler (`checkout.session.completed`, `mode=subscription`) now detects Beta purchases by matching the line-item product against `BETA_PRODUCT_ID` (handles Payment Link path which doesn't carry our metadata). On match: persists `db.beta_signups`, computes remaining spots, and fires the configured webhook in the background.
- Validated by testing_agent (iteration_21: **19/19 backend + 12/12 frontend GREEN**). Deployment readiness PASS.


### 2026-02-26 — Revenue-pulse webhook mirroring
- Extended the Stripe webhook handler to send three additional Slack/Discord pings via the existing `beta_webhook_url` field:
  1. **💎 Enterprise subscriptions** — fires when `checkout.session.completed` includes a line-item product matching any of Enterprise Basic / Plus / Advanced. Title shows the tier, amount in EUR, country, session id.
  2. **⚠️ Payment failed** — fires on `invoice.payment_failed` alongside the existing email alert. Includes amount, attempt count, next attempt timestamp, subscription id.
  3. **🔒 Beta SOLD OUT** — extra ping fires when the 100th Beta Founding Member subscribes and `spots_remaining` rolls to 0.
- Single `items` expansion is now shared between Beta and Enterprise detection — one Stripe API call per event instead of two.
- All three triggers gracefully skip when `beta_webhook_url` is empty; existing email alert flow is unaffected.
- Validated by testing_agent (iteration_22: **15/15 new + 41/41 regression GREEN**). Deployment readiness PASS.


### 2026-06 — Canva Connect API integration (Marketing & Content)
- New `backend/canva_module.py` — OAuth 2.0 + PKCE (S256) flow against Canva Connect API. Router prefix `/api/canva`: `/status`, `/connect` (returns authorize URL), `/callback` (public, 307 → /dashboard/marketing?canva=connected|error), `/disconnect`, `/designs` (GET list + POST create preset doc/whiteboard/presentation), `/designs/{id}/export` (PDF/PNG job), `/exports/{job_id}` (poll).
- Tokens stored per-user in `db.canva_connections` (auto-refresh 5 min before expiry); PKCE states in `db.canva_oauth_states` (stale >15 min purged on each /connect).
- Redirect URI derived from request host → works on preview AND production without code change. User must register BOTH callback URLs in Canva Developer Portal and enable scopes: design:content:read, design:content:write, design:meta:read, profile:read.
- `.env`: CANVA_CLIENT_ID + CANVA_CLIENT_SECRET added.
- Frontend: new "Canva Studio" tab in Marketing & Content (`CanvaPanel.jsx`) — connect card, designs grid with thumbnails, create-design buttons, open-in-Canva links, PDF export with polling, disconnect. `?canva=connected|error` query param auto-opens tab + toasts.
- Full 12-module platform check performed same session: ALL modules load + backend regression GREEN.
- Validated by testing_agent (iteration_23: **18/18 backend + 12/12 frontend GREEN**). Real Canva OAuth handshake pending user login (needs redirect URLs configured in Canva portal first).

### 2026-06 — Stripe account migration #2 (new live account 51TlqbS)
- `.env`: new STRIPE_SECRET_KEY / STRIPE_PUBLISHABLE_KEY (acct 51TlqbS…); new STRIPE_WEBHOOK_SECRET (endpoint we_* recreated via API for https://zynthoro.ai/api/webhook/stripe — old endpoint deleted since its secret was unrecoverable).
- Old catalog product IDs (prod_UmA…) didn't exist in the new account → PLAN_CATALOG remapped: Starter→prod_UlNgemmdU55SYS (€99 "Starter Founder"), Creator→prod_UlNjuSTpfiqL4n, Business→prod_UlNlr39JAeUFPr, Agency→prod_UlNmUAq5RfJYsr, Ent Basic→prod_UlNmG6bbZQFEqh, Ent Plus→prod_UlNnUYsf9btulz, Ent Advanced→prod_UlO0nF9p11at94, Beta→prod_Um9oZGyOLXCPim (€4.99/mo).
- 8 new Payment Links created via API and hardcoded in PLAN_CATALOG + BETA_PAYMENT_LINK.
- NOTE: new account also has a €499/mo "Zynthoro Starter" (prod_UlNbqlkAoLv0nK) with a pre-existing payment link — NOT wired (pricing page advertises €99). Duplicate Beta product prod_Um9oU3QSQPlZWt unused.
- Verified: /api/beta/status + /api/pricing/catalog live against new account; test_stripe_metrics 6 passed 2 skipped.

### 2026-07-10 — Starter price €99 → €499 (Founder pricing sunset) + "Book a call" CTA
- **Starter switched from Zynthoro Starter Founder (€99, prod_UlNgemmdU55SYS) → Zynthoro Starter (€499, prod_UlNbqlkAoLv0nK)** everywhere:
  - `stripe_subscriptions.py` PLAN_CATALOG Starter entry updated: new product_id, payment_link `https://buy.stripe.com/4gM6oA4YKb7ZgKJard6Ri00`, amount_eur "499".
  - `components/sections/Pricing.jsx` — Starter card price "€99" → "€499".
  - `pages/SubscribeStarter.jsx` — Founder verification flow removed entirely (KvK/PDF upload UI dropped). Page reduced to a single €499 checkout CTA that calls `POST /api/checkout/starter/session {package_id: "starter_standard"}`.
  - `checkout.py` — `starter_founder` package removed from PACKAGES dict so any direct API hit for €99 pricing now 400s.
- **"Book a free 30-min call" button** added to `layout/Navbar.jsx` (desktop header only, before "Log in"). Links to `https://calendly.com/zynthoro/30min`. testid: `nav-book-call`.
- Verified via `/api/pricing/catalog` → Starter €499 → correct Stripe link, and homepage screenshot shows €499 card + Book-a-call CTA. No €99 anywhere on the homepage.
- NOTE: business-verification module + `starter_founder` scaffolding on backend (`business_verification.py`, KvK OCR) left in place but no longer reachable from UI — safe to remove later if desired.

### 2026-07-20 — Landing cleanup + Dashboard activity feed + orphan removal
- **`/api/dashboard/summary` — recent_activity now real.** Backend pulls latest team_members + demo_invoices + demo_projects + ai_messages, sorted by timestamp, top 8. Frontend `DashboardHome.jsx` renders each item with icon, title, subtitle, relative timestamp, and click-through link. testid: `dashboard-recent-activity`, `activity-item-{i}`.
- **Countdown timer + PresaleCTA section removed** from `pages/Home.jsx`. File `components/sections/PresaleCTA.jsx` deleted.
- **"Claim (Your) Presale Spot" buttons removed** from Navbar (desktop + mobile) and Hero. Replaced with "Get started" Link → `/signup`. Nav still has "Book a free 30-min call" + "Log in".
- **Hero "Watch Demo"** now opens a real modal (`data-testid=hero-demo-modal`) instead of scrolling. If env `REACT_APP_DEMO_VIDEO_URL` is set, modal renders a 16:9 iframe; otherwise shows "Live demo coming soon" + Calendly CTA to `/zynthoro/30min`.
- **`business_verification.py` removed** — file deleted, all backend imports/endpoints removed:
  - Deleted route: `POST /api/business-verification/upload`
  - Deleted route: `GET /api/admin/business-verifications`
  - Deleted DB index: `db.business_verifications` compound index
  - `POST /api/checkout/starter/session` now accepts only `starter_standard` and no `verification_id` (typed via Literal). Provisioning code no longer sets `founder_pricing_*` or `business_verification_id`.
  - `checkout.py` slimmed: only `starter_standard` package (€499); `founder_pricing_window()` helper removed; `verification_id` parameter kept with default `None` for signature stability.
- **`ModulePlaceholder.jsx` tiles** — removed `cursor-pointer` + `hover:border-[#1A4FFF]` classes, changed misleading "Open module" copy to "Coming soon". Tiles are now clearly non-interactive.
- Meta description on landing dropped the "Launching 30 June 2026" phrase.
- Verified: backend restarts cleanly, `/api/pricing/catalog` still returns Starter €499, `/api/dashboard/summary` returns 8 activity items for demo user, `/api/checkout/starter/session` still creates valid Stripe sessions.
- **NOT REDEPLOYED to production** — user must trigger a redeploy from the Emergent dashboard to push these changes to https://zynthoro.ai.

### 2026-07-20 (later) — Live activity write-through for real users
- Added `/app/backend/activity_log.py` with `log_event()` helper that inserts to `db.activity_events` (never raises — activity logging never blocks the primary flow).
- Wired write-through into two live event sources:
  1. `POST /api/team/invite` (server.py) — logs `team_member_invited` with role + level.
  2. `ai_assistants.save_message()` — logs `ai_message_sent` for each user prompt (assistant replies are NOT double-logged).
  - **Invoice creation hook deferred** — no real-user invoice-create endpoint exists yet (only demo seeded invoices). Add the hook when the Finance CRUD lands.
- `/api/dashboard/summary` refactored: unified path reads from `activity_events` for everyone (top 20 by timestamp). Demo user gets an additional merge with `demo_invoices` / `demo_projects` / seeded team members so the XPRIZE feed still looks rich.
- New index: `db.activity_events` on `(workspace_owner, timestamp desc)`.
- Verified with founder account: invite a teammate + send AI message → both events appear at the top of the dashboard feed within 1s. Test data cleaned up.

### 2026-07-20 (evening) — Subscription events in activity feed
- Stripe webhook (`checkout.session.completed` with `kind=subscription_change`) now fires an `activity_log.log_event`:
  - `alert_kind=upgrade`  → title "🎉 Upgraded to {plan}"
  - `alert_kind=downgrade` → title "Downgraded to {plan}"
  - `alert_kind=subscribe` → title "🎉 Subscribed to {plan}"
  - Subtitle shows "From {prev_plan}" or "New subscription".
- Starter one-time checkout provisioning path (`/api/checkout/starter/status`) also fires a matching event ("🎉 Subscribed to Starter" or "🎉 Upgraded to Starter").
- `customer.subscription.deleted` fires "Subscription cancelled — {plan}" so the feed tells the full story.
- All calls wrapped in `asyncio.create_task(...)` — activity logging never blocks the webhook response.
- Verified: manually logged an upgrade event for the founder, feed rendered it correctly at the top with the sparkles icon and Settings deep-link. Test data cleaned.

### 2026-07-20 (batch A shipped) — Kickstart lifetime deals + Compleet + AI+Social top-ups
Six new tiers wired end-to-end. All Stripe products live-mode.

**Stripe catalog (all confirmed via Stripe API):**
| tier_key           | plan_key         | €      | billing         | mode          | product_id                 | price_id                        |
|--------------------|------------------|--------|-----------------|---------------|----------------------------|---------------------------------|
| kickstart_1        | Kickstart 1      | 79.00  | lifetime        | payment       | prod_UttjPOJtS5cTns        | price_1Tu5wO5sy2phCvUrZSqZNzak  |
| kickstart_2        | Kickstart 2      | 149.00 | lifetime        | payment       | prod_Uttr6UVu8Lcgde        | price_1Tu6465sy2phCvUrmt77jtlS  |
| kickstart_3        | Kickstart 3      | 199.00 | lifetime        | payment       | prod_UttshkVDM8nk74        | price_1Tu64x5sy2phCvUrwBvmRSuG  |
| compleet           | Compleet         | 79.99  | monthly         | subscription  | prod_Uv1y3dZi4VLSlz  (NEW) | price_1TvBuG5sy2phCvUrlbahjtFj  |
| ai_social_week     | AI+Social Week   | 24.99  | one_time_week   | payment       | prod_Utty09spK6ZzVF        | price_1Tu6AT5sy2phCvUrFW68MprM  |
| ai_social_month    | AI+Social Month  | 59.99  | one_time_month  | payment       | prod_UttzlbwkpBggU9        | price_1Tu6BR5sy2phCvUrXCaUwBvE  |

**New backend files/endpoints:**
- `/app/backend/tier_catalog.py` — single source of truth (Stripe IDs, feature matrix, credit limits, checkout helper).
- `GET  /api/tier/catalog` — public catalog for landing/subscribe pages.
- `POST /api/checkout/tier/session` — requires `consent_waiver=true` (400 otherwise), creates live Stripe Checkout Session in the right mode (payment/subscription), records consent timestamp on `payment_transactions`.
- `GET  /api/checkout/tier/status/{session_id}` — poll for provisioning done (webhook side).
- `GET  /api/me/tier` + `.tier` field on `/api/auth/me` — returns `{plan_key, modules, seats, workspaces, ai_credits_limit, ai_credits_used, ai_credits_remaining, is_lifetime}` for the current user.
- `_consume_ai_credit()` middleware on `POST /api/ai/chat` & `POST /api/ai/stream` — 402 when limit hit; monthly reset for `ai_credits_period=month`; expiry check for one-time top-ups.
- Stripe webhook `kind=tier_purchase` branch — provisions plan, sets `is_lifetime`, `ai_credits_*`, `consent_waiver_at`, fires activity feed event ("🎉 Purchased Kickstart X" / "🎉 Subscribed to Compleet"), fires email alert.

**New frontend:**
- `/app/frontend/src/pages/SubscribeTier.jsx` — dynamic subscribe page at `/subscribe/:tierKey` with Dutch herroepingsrecht waiver (unchecked by default; CTA disabled until checked). Uses `art. 6:230p BW` verbatim wording.
- `/app/frontend/src/pages/SubscribeReturn.jsx` — post-Stripe polling page that waits for webhook provisioning, then routes user to `/dashboard`.
- `/app/frontend/src/components/sections/KickstartPricing.jsx` — landing section (`id="kickstart"`) with 3 Kickstart cards + Compleet + Week + Month.
- `ModulePlaceholder.jsx` — reads `user.tier.modules`, shows "🔒 Upgrade to unlock" pill badge on module pages the tier doesn't include.
- `Sidebar.jsx` — small lock icon next to sidebar items the tier doesn't include.
- New routes in `App.js`: `/subscribe/return` and `/subscribe/:tierKey`.

**AI credit limits (enforced):**
- Kickstart 1 = 50/mo · Kickstart 2 = 150/mo · Kickstart 3 = 300/mo
- Compleet = unlimited (limit=None)
- AI+Social Week = 30 total (7d expiry)
- AI+Social Month = 150 total (30d expiry)
- Founder / demo / billing-exempt / is_unlimited = unlimited (bypass)

**End-to-end verified:**
- All 6 Stripe live Checkout Sessions successfully created (cs_live_… URLs returned).
- Waiver-blocked checkout returns 400 with Dutch message.
- Landing page renders all 6 cards cleanly (screenshot in /tmp/kickstart.png).
- Subscribe page: waiver unchecked → CTA disabled; checked → CTA enabled (screenshots /tmp/subscribe_before.png, /tmp/subscribe_after.png).
- Founder /auth/me returns `modules_count=16 limit=None` (bypass).
- Presale user gets `modules=['settings','team'] limit=10`.

**Deferred to Batch B (per user Q1=A):**
- Website builder with templates + custom domain (CNAME/A-record). Not started — needs Emergent infra decision on multi-tenant custom domains.

### 2026-07-20 (late) — Bug fix: Kickstart tier provisioning + credit-limit revenue leak
User reported: purchased Kickstart 1 with promo ZYNTHORO-QA on production, `subscription_plan` stayed as 'Presale'. Deep-dive uncovered TWO cascading bugs:

**Bug 1 (root cause reported by user):** Stripe webhook branch `if event_type == "checkout.session.completed" and obj.get("mode") == "subscription"` silently dropped ALL one-time-payment tier sessions (K1/K2/K3/AI+Social Week/AI+Social Month all use `mode="payment"`). Only Compleet (`mode="subscription"`) provisioned. **Fix:** widened branch to `mode == "subscription" OR (mode == "payment" AND metadata.kind == "tier_purchase")`.

**Bug 2 (revenue leak introduced by fix, caught by testing agent):** `_provision_tier_purchase()` was reading `ai_credits_limit` from `tier_catalog.get_tier(tier_key)` (Stripe pricing metadata dict, no credit fields) instead of `tier_catalog.TIER_FEATURES[plan_key]`. Result: every K1/K2/K3/Week/Month user would provision with `ai_credits_limit=None` → treated as UNLIMITED by /api/me and /api/ai/chat. **Fix:** source credits from TIER_FEATURES[plan_key] and simplify the `period_end` branch to key off `billing` alone (not the AND with credits_period).

**Extras shipped with the fix:**
- Refactored provisioning into `_provision_tier_purchase()` helper (single source of truth, callable from webhook and status endpoint).
- Added **self-heal** to `GET /api/checkout/tier/status/{session_id}` — retrieves the Stripe session, and if it's paid-or-no_payment_required + complete + kind=tier_purchase + owned by the current user, re-runs provisioning. Fixes stuck users from missed webhooks without re-purchase.
- Frontend `SubscribeReturn.jsx` now treats `payment_status="no_payment_required"` (100%-off coupon result) as paid.

**Tests:**
- New file `/app/backend/tests/test_tier_provisioning_helper.py` — 11 tests directly invoke `_provision_tier_purchase()` for all 6 tiers + idempotency + self-heal + herroepingsrecht + QA bypass regression.
- All 11 pass. Combined with the earlier 22 QA-account tests: **33/33 green** (iteration 25 report at `/app/test_reports/iteration_25.json`).

**How stuck production users get healed:** after the fix is redeployed, any user with an unprovisioned tier purchase will be automatically healed the next time their browser hits `/subscribe/return` (or the frontend polls `GET /api/checkout/tier/status/{session_id}`). No manual DB write needed.

### 2026-07-20 (later) — Stripe checkout hardening (Emmy 502 report)
User reported another 502 with Emmy diagnosing "stale price_id at tier_catalog.py line 120". Main agent's direct Stripe API verification proved **all 6 product+price IDs are valid, active, and priced correctly** in the live account — Emmy's diagnosis was wrong. Message also contained an empty `[IDs hieronder]` placeholder (no replacement IDs provided).

**Hardening applied anyway (defensive value for future stale-ID / slow-Stripe scenarios):**
- `tier_catalog.create_tier_checkout_session()` — `stripe.checkout.Session.create` now runs via `asyncio.to_thread` + `asyncio.wait_for(timeout=8.0)`. Slow Stripe API can no longer wedge the event loop.
- `POST /api/checkout/tier/session` — new type-based exception handlers:
  - `stripe.error.InvalidRequestError` → **HTTP 400** with Dutch user message + Stripe's user_message as ref
  - `stripe.error.AuthenticationError` → **HTTP 500**
  - `stripe.error.RateLimitError` → **HTTP 429**
  - `asyncio.TimeoutError` → **HTTP 504**
  - Anything else → **HTTP 502** (fall-through)
- Old class-name string match (`if exc_cls == 'InvalidRequestError':`) replaced with proper `except stripe_sdk.error.InvalidRequestError:` per code review — typo-safe.

**Tests:** 36/36 green (added 3 new tests specifically for the InvalidRequestError → 400 conversion). Report at `/app/test_reports/iteration_27.json`.

### 2026-07-20 (final bundle, ready for redeploy) — Stripe catalog startup validation
- **`tier_catalog.validate_catalog_against_stripe()`** — iterates all 6 TIER_CATALOG entries, verifies product+price exist & active in Stripe, compares amount_eur to Stripe's unit_amount. Runs in a background thread with 20s hard timeout. Never raises on network errors — soft-fails with an error report so a Stripe outage cannot block boot.
- **FastAPI startup hook `_validate_stripe_catalog_on_startup()`** — runs the validator at process boot; result cached in `_CATALOG_HEALTH` dict (`boot_status`: 'ok'|'failed'|'error'|'skipped'|'pending').
- **`POST /api/checkout/tier/session`** — new 503 hard-block when `boot_status == 'failed'`. Users cannot get stuck on 502 from a known-stale catalog anymore.
- **New `GET /api/tier/catalog/health`** — public ops endpoint reporting last validation state (no PII, no secrets).
- **`SKIP_STRIPE_STARTUP_CHECK=1|true|yes`** env override for emergency boot without validation. Not set by default.
- **Code review nit fixed:** `import asyncio` + `import stripe` moved from inline in create_tier_checkout_session to module top of tier_catalog.py.
- **Test isolation fix:** old `test_non_flagged_user_requires_2fa_setup` used legacy `asyncio.get_event_loop()` which broke when adjacent tests used `asyncio.run()`. Modernized to `asyncio.run(...)`.

**Test suite (bundle regression):** 41 passed + 1 intentional skip.
- 22 QA account tests (test_qa_kickstart_provisioning.py)
- 11 provisioning helper tests (test_tier_provisioning_helper.py)
- 5 catalog startup tests (test_stripe_catalog_startup.py, 3 new)
- Testing agent report: `/app/test_reports/iteration_28.json`

### 2026-07-20 (email quota fix) — Email alerts filtered to real paid tier purchases
User's Resend daily quota (100/day) was being exhausted by test traffic (QA seed accounts, founder testing, 100%-off coupons). Added a two-tier guard to `email_service.send_stripe_alert()`:

1. **Zero-revenue guard**: for `kind in ('subscribe', 'upgrade')` where `amount_eur is None or <= 0`, skip the send (covers 100%-off coupons like ZYNTHORO-QA). Cancellations & payment failures still send regardless of amount.
2. **Non-real-customer guard**: looks up the user in MongoDB and skips the send if ANY of `is_qa_test`, `is_demo`, `is_founder`, `billing_exempt` is true. Errors on the DB lookup fall through and send anyway (safer to over-notify than to miss a real customer).

Verified with 5 direct calls: QA user, founder, demo, zero-euro → all correctly return None (skipped, logged at INFO). Real customer with real amount → email sent (Resend returned an ID). 41-test regression suite still passes.

**Estimated quota savings:** ≥90% of prior test-traffic sends now filtered. Every subsequent QA checkout via `ZYNTHORO-QA` will be silent from an email perspective (still logs in activity feed via `db.activity_events`).


### 2026-07-21 — AI Assistant File Uploads (P1 SHIPPED)
Users can now attach files to any AI assistant (Zyntha, Thoro, Zyona, Zynthoro Assist) so the assistant can answer using the file's contents.

**Backend**
- New route `POST /api/ai/upload` (multipart) — accepts PDF, DOCX, XLSX, PPTX, CSV, max 10 MB. Extracts text, stores in `ai_uploads` collection, returns `{file_id, filename, size, mime, chars_extracted, truncated, preview}`.
- New route `DELETE /api/ai/upload/{file_id}` — owner-scoped removal.
- Extended `AssistChatIn` with optional `file_ids: List[str]`. `/api/ai/chat` and `/api/ai/stream` now fetch the extracted text for each `file_id` (owner-scoped) and inject it into the assistant's system prompt under a "## Attached files" section.
- New module `/app/backend/file_extract.py` — synchronous extractors for all 5 formats, dispatched by extension. Output capped at `MAX_CHARS = 200_000` with a truncation note. Called via `asyncio.to_thread(...)`.
- Storage strategy: MongoDB `ai_uploads` collection with a **TTL index on `created_at` (expireAfterSeconds=86_400)** — files auto-purge after 24h. This is deliberately session-temporary storage, not a document library.
- Dependencies added: `python-docx`, `openpyxl`, `python-pptx` (pypdf already present, CSV is stdlib).

**Frontend**
- New helper `/app/frontend/src/lib/aiUpload.js` — `uploadAiFile`, `deleteAiFile`, `validateUpload`, `AI_UPLOAD_ACCEPT_ATTR`, `formatBytes`.
- New reusable component `AttachmentChip.jsx` — supports `uploading` / `ready` / `error` states, `compact` mode for in-bubble rendering.
- `AssistantPage.jsx` (Zyntha/Thoro/Zyona) and `AssistFloating.jsx` (Zynthoro Assist) now render a paperclip button + hidden multi-file `<input type="file">` + pending-chip row above the composer. Attachments upload immediately, block Send while in-flight, and are stamped onto the user message bubble after send.
- `aiStream.js` forwards the `file_ids` array in the SSE POST body.
- Client-side validation mirrors the server: extension whitelist + 10 MB cap + empty-file check.

**Testing**
- 11 unit tests in `/app/backend/tests/test_file_extract.py` (all pass — CSV/DOCX/XLSX/PPTX/PDF extraction, truncation, error paths).
- 22-test E2E suite in `/app/backend/tests/test_ai_upload_e2e.py` (100% pass) — validation paths, owner isolation, cross-user isolation, file-context injection across all 4 assistants, streaming path, TTL index verified.
- Frontend E2E verified via testing_agent (100% pass) — paperclip renders, upload chip flow, unsupported/oversize file toasts, multi-file, `Gadget` answered correctly from uploaded sales CSV, floating panel mirror.

**Test-drive**
Log in as founder → `/dashboard/zyona` → paperclip → upload a CSV with sales data → ask "Which product has the highest revenue?" → Zyona reads the file and answers.

### 2026-07-21 — P0 Bug Fixes: Top-up preservation, Month expiry, Promo abuse
Fixed three P0 defects surfaced in the code review + security audit.

**Bug 1 — Top-up must not overwrite a paying customer's plan**
- `_provision_tier_purchase` used to unconditionally `$set` `subscription_plan` / `is_lifetime` / module fields for every purchase, including AI+Social Week/Month top-ups. Buying a €59 add-on would downgrade a Kickstart 3 (€199) lifetime customer to AI+Social Month's limited feature set.
- Fix: top-ups now take an additive-only code path. When the user has a paying plan (`is_lifetime` OR `subscription_plan not in [None, "", "Presale"]`), we only update credit fields + record `active_top_up`. When the user has no paying plan yet (Presale), the top-up becomes their effective plan (unchanged behaviour). Applies to `ai_social_week` and `ai_social_month`.

**Bug 2 — AI+Social Month never expired**
- `tier_catalog.TIER_FEATURES["AI+Social Month"]["ai_credits_period"]` was `"month"` — this hit the monthly-RESET branch in `_consume_ai_credit`, so the `ai_credits_period_ends_at` (30d) was never checked. A single €59.99 payment refilled 150 credits every 30 days forever.
- Fix: changed to `"one_time"` (matching AI+Social Week), so the elif expiry branch fires. `_provision_tier_purchase` was already setting `period_ends_at` correctly; only the period label was wrong.

**Bug 3 — ZYNTHORO-QA promo abuse (defense-in-depth)**
- Two layers of protection:
  1. `create_tier_checkout_session` now takes `allow_promo: bool` (default False). `checkout_tier_session` sets it to `True` only for `is_qa_test` users. Real customers no longer see the "Add promotion code" input on Stripe Checkout.
  2. `_provision_tier_purchase` now accepts `amount_total_cents` and refuses to grant entitlement when the amount actually charged is <50% of the tier list price AND the buyer is not internal (`is_qa_test`/`is_founder`/`is_demo`/`billing_exempt`). Blocked incidents are logged to a new `security_incidents` collection and emailed to ops via `send_stripe_alert(kind="alert")`.
- 100%-off provisioning still works for founders / QA / demo users, so nothing breaks for internal accounts.

**Testing**
- 15 new regression tests in `/app/backend/tests/test_p0_fixes_20260721.py` — top-up preserves Kickstart 3 lifetime + Compleet subscription; Month/Week both `one_time`; expiry raises 402; amount<50% blocks non-internal; QA/founder still provision at €0; partial legitimate discount still works; `allow_promo` off by default at checkout creation.
- All 15 pass. Existing tier-provisioning suite (14 tests) still passes. File-extract unit tests (11) still pass.

**Files touched**
- `/app/backend/tier_catalog.py` — AI+Social Month period → `one_time`; added `TOP_UP_TIER_KEYS` + `is_top_up()`; `create_tier_checkout_session` gained `allow_promo` kwarg.
- `/app/backend/server.py` — `checkout_tier_session` passes `allow_promo=bool(user.get("is_qa_test"))`. `_provision_tier_purchase` rewritten with `amount_total_cents` param, top-up branch, and amount-tamper guard. Both callers (webhook + status self-heal) now forward `session.amount_total`.
- `/app/backend/tests/test_p0_fixes_20260721.py` — new (15 tests).


### 2026-07-21 — P1 Reliability & Security Batch
Five P1 fixes from the code-review + security-audit landed in one pass.

**P1-1 — Refund AI credit on LLM failure**
- Previously `/api/ai/chat` and `/api/ai/stream` charged the credit up-front and kept it even when the LLM provider returned an error. During an outage a Kickstart 1 customer could burn all 50 credits with zero replies.
- Added `_refund_ai_credit(user)` helper (defensive: only decrements when the counter is `> 0`, skips for unlimited/founder/demo).
- `ai_chat` refunds on `RuntimeError` (provider errors) and generic `Exception`.
- `ai_stream` refunds when the generator errors AND no `delta` frame was delivered — a stream that produced partial output is NOT refunded.

**P1-2 — Idempotent webhook provisioning (CR-4)**
- `_provision_tier_purchase` now performs an atomic check-and-set on `payment_transactions.provisioned` before any side effects. Stripe event replays and concurrent webhook + self-heal paths can no longer double-provision, send duplicate emails, or reset `ai_credits_used_this_period` to 0.
- Amount-tamper blocks now set `provisioning_blocked=True` without setting `provisioned=True` so a legitimate follow-up call (e.g. after a refund) can re-run. Both callers (webhook + status self-heal) no longer force-set `provisioned` externally.

**P1-3 — Rate-limit + alert on `/api/admin/disable-2fa` (SEC-004)**
- New `_rate_limit_admin_disable_2fa(client_ip)` — MongoDB-backed sliding window: **5 calls per 60 min per client IP**. Rate limit runs BEFORE the admin-key comparison so it also protects against brute-force key guessing.
- Every call (success or failure) is recorded in `admin_call_attempts` with reason. Collection has a 7-day TTL index.
- Every successful call fires `email_service.send_stripe_alert(kind="alert", event_type="admin_disable_2fa")` to ops with client IP, target email, and `set_founder` flag.

**P1-4 — Cookie `Secure=True` + pinned `CORS_ORIGINS` (SEC-005)**
- `_set_auth_cookies` now sets `secure=True` by default. Local dev can opt out via `COOKIE_SECURE=false`.
- CORS middleware refuses to install with wildcard `*` when `allow_credentials=True`. Default origins now: `https://zynthoro.ai`, `https://www.zynthoro.ai`, `https://zynthoro-foundation.preview.emergentagent.com`.
- `backend/.env` `CORS_ORIGINS` updated to the same explicit list.

**P1-5 — Fail-closed founder/demo seeds (SEC-001/002)**
- `seed_founder()` — no more source-code default. Refuses to seed if `FOUNDER_PASSWORD` env is missing or shorter than 12 chars (existing founder record is preserved). Password rotation is a dedicated reset flow, not a boot-time overwrite.
- `seed_jury_demo()` — password now comes from `JURY_DEMO_PASSWORD` env (added to `backend/.env`). If unset or too short, demo seed is skipped entirely with a WARNING log.

**Testing** — 15 new regression tests in `tests/test_p1_fixes_20260721.py` (all pass). No regressions in P0 (15/15), file-extract (11/11), or tier-provisioning-helper (14/14) suites.

**Files touched**
- `/app/backend/server.py` — refactored `_consume_ai_credit`, `_provision_tier_purchase`, `admin_disable_2fa`, `seed_founder`, `seed_jury_demo`, `ai_chat`, `ai_stream`; added `_refund_ai_credit`, `_rate_limit_admin_disable_2fa`, `_log_admin_call`; changed `_set_auth_cookies` (Secure=True) and CORS middleware.
- `/app/backend/.env` — pinned `CORS_ORIGINS`; added `JURY_DEMO_PASSWORD`.
- `/app/backend/tests/test_p1_fixes_20260721.py` — new (15 tests).

**Deployment note**
Deploy will need `JURY_DEMO_PASSWORD` set in the production env for the XPRIZE demo to keep seeding. If not set, the jury account already in Mongo is preserved — no data loss.


### 2026-07-21 — Session A: Landing bundle + Socials + Terms
Everything from the "high business impact" Session A bundle landed.

**Landing page**
- Kickstart pricing moved to the top of the marketing sections (right after Hero + SocialProof) for maximum conversion prominence.
- Meta description updated: "AI-native ERP for European SMEs · Kickstart lifetime deals from €79 · Starting at €79 lifetime."
- Monthly ↔ Annual toggle added to `Pricing.jsx` — annual = 10× monthly = 2 months free, "2 MONTHS FREE" badge on the annual button. Applies to Starter/Creator/Business/Agency/Enterprise.

**Founder / privileged bypass on module locks**
- Added `hr` slug to `tier_catalog.ALL_MODULES` (was missing → founder was getting `Upgrade to unlock` on `/dashboard/hr`).
- Belt-and-braces client bypass in `Sidebar.jsx` + `ModulePlaceholder.jsx`: any user with `is_founder | is_unlimited | billing_exempt | is_demo` is now `isPrivileged` and never sees the lock icon regardless of the server's `tier.modules` payload.

**Admin backdoor endpoints removed**
- `POST /api/admin/seed-qa-accounts` and `POST /api/admin/disable-2fa` — deleted along with helpers (`_rate_limit_admin_disable_2fa`, `_log_admin_call`, `QA_SEED_ACCOUNTS`, `DisableTwofaIn`).
- Removed `ADMIN_SEED_KEY` from `backend/.env`.
- Related tests removed: `test_admin_disable_2fa.py` deleted; TestAdminDisable2faRateLimit and E2E test stripped from `test_p1_fixes_20260721.py` (12/12 remaining tests still pass).
- 404 confirmed on both endpoints in the running preview.

**Social OAuth stubs (Meta + LinkedIn)**
- `GET /api/social/connections` — returns user's connected accounts (empty list is valid, not an error).
- `GET /api/social/oauth/start?provider=facebook|instagram|linkedin` — if env creds (`META_APP_ID` / `LINKEDIN_CLIENT_ID`) are set, returns real authorize URL; otherwise **501 with `coming_soon: True`** so the client can show a friendly toast.
- `GET /api/social/oauth/callback` — placeholder that closes the loop safely (token exchange stubbed until app credentials are added; `TODO(prod)` marker in code).
- `POST /api/social/disconnect` — removes a stored connection.
- New collection `social_oauth_states` for CSRF `state` values.

**Marketing Content UI**
- Facebook / Instagram / LinkedIn buttons wired to the new `/api/social/oauth/start`. On 501 the button shows a toast "Social connect for this platform is coming soon…"; on success, redirects to the OAuth authorize URL.
- **TikTok / X / YouTube** buttons now show "Coming soon" (visibly disabled, yellow chip). Their status field is `coming_soon` in the `PLATFORMS` config.
- Photo + Video panels honestly labelled "Coming soon" (Nano Banana / Sora 2 not yet wired) — no false promises.

**Legal**
- Terms of Service — split billing clause 3 into: "3. Plans, billing & Kickstart lifetime deals" (new pricing incl. Kickstart 1/2/3 + Compleet + AI+Social top-ups), "3a. Kickstart lifetime — specific terms" (5-year platform commitment, non-transferable, fair-use), "3b. EU right of withdrawal — waiver (herroepingsrecht)" (Art. 6(1)(1) waiver). Cancellation clause 4 rewritten to distinguish subscription plans from one-time lifetime purchases.
- Privacy Policy — added "Kickstart lifetime purchase records" collection item (10-year retention per Dutch Art. 52 AWR); removed stale "founder-discount eligibility" and "€99/month founder discount" text; documented 24h auto-purge for AI file uploads.

**Files touched**
- `/app/frontend/src/pages/Home.jsx` — meta description + Kickstart section moved to top
- `/app/frontend/src/components/sections/Pricing.jsx` — annual toggle + `price_annual` data
- `/app/frontend/src/pages/dashboard/MarketingContent.jsx` — coming-soon labels + Connect button wired + Photo/Video honesty
- `/app/frontend/src/components/dashboard/Sidebar.jsx` — `isPrivileged` bypass
- `/app/frontend/src/pages/dashboard/ModulePlaceholder.jsx` — `isPrivileged` bypass
- `/app/frontend/src/pages/legal/TermsOfService.jsx` — Kickstart + herroepingsrecht sections
- `/app/frontend/src/pages/legal/PrivacyPolicy.jsx` — Kickstart record retention
- `/app/backend/server.py` — social OAuth endpoints; admin backdoor endpoints deleted; RedirectResponse/JSONResponse imports
- `/app/backend/tier_catalog.py` — added "hr" to `ALL_MODULES`
- `/app/backend/.env` — removed `ADMIN_SEED_KEY`
- Deleted: `/app/backend/tests/test_admin_disable_2fa.py`

**Verified live in preview**
- ✅ Cookie has `Secure` flag
- ✅ Social OAuth returns 501 + `coming_soon: True`
- ✅ Admin endpoints return 404
- ✅ Kickstart section renders near top
- ✅ Annual toggle switches all plan prices (Starter €499↔€4,990, etc.)
- ✅ All 4 test suites still green


### 2026-07-21 — Weekly Digest + Deploy Blocker Fix

**Weekly Digest (from daily)** — `daily_digest.py` rewritten:
- **Cadence**: every Monday at **07:00 UTC** (was: every day at 07:00 UTC). Configurable via `DIGEST_WEEKDAY` + `DIGEST_HOUR_UTC`.
- **Window**: last **7 days** (was: 24h). Configurable via `DIGEST_WINDOW_DAYS`.
- **New signals tracked**: `new_users_count`, `purchases` (from `payment_transactions` where `provisioned=True` and not blocked), revenue total (€), and `ai_messages_count`.
- **No-activity skip**: `_has_activity()` returns True only if there's at least one presale/voice-lead/anonymous-tryout/purchase/AI-message/new-user in the window. If all zero, `send_digest_now` records a `skipped_no_activity` state and returns without emailing.
- **Idempotency**: switched from per-UTC-day to per-ISO-week (`_iso_week_key` returns `YYYY-Www`). New system_state key `weekly_digest`.
- **`force=True`** bypasses both the ISO-week dedupe AND the no-activity skip (for founder QA / manual trigger).

**Subject line** now: `Zynthoro weekly · 2026-W29 · N signups · N purchases · €X.XX`. Body copy switched from "daily" to "weekly" throughout.

**`/api/founder/digest/preview`** — updated response to also expose `has_activity`, `purchase_count`, `ai_messages_count`, `new_users_count`, `window_days`.

**Deploy blocker fix (CORS)**
- Reverted the P1 SEC-005 CORS pinning: the deployment agent revealed that Emergent's ingress requires `CORS_ORIGINS="*"` because the production hostname isn't known at build time. My "no wildcard with credentials" hardening blocked the k8s readiness probe → deploy timed out.
- Restored `CORS_ORIGINS="*"` in `backend/.env` and reverted the middleware code to honour the env value as-is (comment explains the platform tradeoff).
- Updated `test_cors_origins_no_wildcard` → `test_cors_origins_configured` (now asserts the middleware is installed with a non-empty list; wildcard is acceptable on this platform).

**Testing**
- 6 new tests in `tests/test_weekly_digest.py` — `_has_activity`, ISO-week key format, no-activity skip, ISO-week dedupe, `force=True` bypass. All pass.
- All 12 P1 tests still green.
- End-to-end verified: `/api/founder/digest/preview` returns `has_activity=True` with real counts (32 purchases, 13 AI msgs, 1 new user, 7-day window); scheduler log confirms `Mon 07:00Z, window=7d`.

**Files touched**
- `/app/backend/daily_digest.py` — complete rewrite (weekly, 7-day, activity-gated)
- `/app/backend/server.py` — updated `/founder/digest/*` routes; CORS middleware reverted to wildcard-friendly
- `/app/backend/.env` — `CORS_ORIGINS="*"`
- `/app/backend/tests/test_p1_fixes_20260721.py` — CORS test updated
- `/app/backend/tests/test_weekly_digest.py` — new (6 tests)

**Ready to redeploy** — click Deploy in the dashboard. The k8s readiness timeout should be gone now.


### 2026-07-21 — Session B: HR + Accounting + Communication + Compliance (all shipped)

**All 4 modules built with real CRUD, live in `/dashboard/{hr,accounting,communication,compliance}`.**

**HR module** (`hr_module.py` + `HRModule.jsx`)
- `GET/POST/PUT/DELETE /api/hr/employees` — full CRUD with cascade delete of contracts + leave.
- `GET/POST/DELETE /api/hr/contracts` — permanent/fixed-term/freelance/internship.
- `GET/POST /api/hr/leave-requests` + `PUT /decide` (approve/reject) + `DELETE`.
- UI: 3-tab layout (Employees / Contracts / Leave). Auto-computed leave days. Colour-coded status badges (pending/approved/rejected).

**Accounting module** (`accounting_module.py` + `AccountingModule.jsx`)
- **Auto-seeded 23-account chart of accounts** (assets / liabilities / equity / revenue / expenses) — RGS-inspired SME set.
- `POST /api/accounting/journal-entries` — **real double-entry validation** (each line one-sided, sum of debits = sum of credits, total > 0).
- `GET /api/accounting/trial-balance?as_of=` — includes zero-balance accounts; reports `balanced: true/false`.
- `GET /api/accounting/pnl?date_from=&date_to=` — revenue − expenses = net income.
- UI: 3-tab (Journal / Trial balance / P&L). Journal builder shows live "Balanced" indicator + disables Save until balanced. P&L has date filters.

**Communication module** (`communication_module.py` + `CommunicationModule.jsx`)
- `GET/POST/DELETE /api/comm/channels` — auto-seeds an "Inbox" per workspace (protected, non-deletable).
- `GET /api/comm/messages?channel_id=` + `POST /api/comm/messages` + `DELETE`.
- UI: Slack-style split view (channel sidebar + message pane). 12-second polling. Enter to send. Message counter per channel.

**Compliance module** (`compliance_module.py` + `ComplianceModule.jsx`)
- **GDPR checklist**: 12 curated items auto-seeded per workspace (data inventory, privacy notice, consent records, DPAs, DSAR, breach runbook, retention, access controls, encryption, staff training, DPO, log retention). Toggle checked state + notes.
- **Audit log viewer**: unified feed from `activity_events` + `security_incidents` + blocked `payment_transactions`. Filters by source. Founder/unlimited sees system-wide; regular users see own events only.
- **Policy library**: 6 policy templates auto-seeded (Data Protection & Privacy, InfoSec, Retention, Breach Response, Third-Party Register, Acceptable Use). Full CRUD with versioning (`version++` on save).
- UI: 3-tab (Checklist / Audit log / Policy library). Progress bar on checklist. Rich cards on policies.

**Routing**
- `App.js` now maps `/dashboard/hr`, `/dashboard/accounting`, `/dashboard/communication`, `/dashboard/compliance` to the new pages (before falling through to `ModulePlaceholder`).

**Backend verification (curl smoke)**
```
HR: employee created (id ✓)
Accounting: 23 accounts seeded, journal entry #1 balanced, TB balanced, P&L net €1,000
Communication: Inbox auto-created
Compliance: 12 checklist items + 6 policy templates seeded
```

**Screenshot confirms**: all 4 module routes render, sidebar unlocked for founder, GDPR checklist shows 12/12 items ready.

**Files created**
- `/app/backend/hr_module.py`, `/app/backend/accounting_module.py`, `/app/backend/communication_module.py`, `/app/backend/compliance_module.py`
- `/app/frontend/src/pages/dashboard/HRModule.jsx`, `AccountingModule.jsx`, `CommunicationModule.jsx`, `ComplianceModule.jsx`

**Files touched**
- `/app/backend/server.py` — registered 4 new routers
- `/app/frontend/src/App.js` — imported + routed 4 new pages

**Ready for XPRIZE Aug 17 jury review.**



### 2026-02-15 — Session C1: Finance & Sales (shipped)

**Scope**: Full CRUD for the last two P0 ERP modules ahead of Aug 17 jury review.

**Finance & Invoicing** (`/app/backend/finance_module.py` + `FinanceModule.jsx`)
- Invoices CRUD with line items (qty · unit_price · tax_rate) — auto-computed subtotal / tax / total
- Auto-numbered `INV-YYYY-####` sequence per workspace (atomic Mongo counter)
- PDF export via `reportlab` — includes company header, bill-to, line items, totals, **payment terms + bank details** (user pref 2b), notes
- Send invoice by email via Resend with PDF attached — surfaces real error messages back to UI
- Mark-paid + payment history (partial payments auto-flip status when cumulative ≥ total)
- Company settings tab (name/address/VAT/currency/prefix/default payment terms/default bank details)
- Auto-mark overdue (persisted on list read so status doesn't flip back)
- Stat pills: Invoiced / Paid / Outstanding / Overdue

**Sales** (`/app/backend/sales_module.py` + `SalesModule.jsx`)
- Leads CRUD (name, company, email, phone, source, value, expected_close, notes)
- Kanban pipeline: New → Contacted → Proposal → Won / Lost — HTML5 drag-and-drop between columns
- Stage change history (`stage_history[]` with timestamp + actor)
- Aggregate `/pipeline` endpoint (count + total_value per column, open_value/won_value totals)
- Table view for list-based ops + row-level edit/delete
- Stat pills: Total leads / Open value / Won value / Lost

**Backend endpoints added (all `/api`)**
- Finance: `GET|PUT /finance/settings`, `GET|POST /finance/invoices`, `GET|PUT|DELETE /finance/invoices/{id}`, `GET /finance/invoices/{id}/pdf`, `POST /finance/invoices/{id}/send-email`, `POST /finance/invoices/{id}/payments`, `POST /finance/invoices/{id}/mark-paid`, `DELETE /finance/payments/{pid}`
- Sales: `GET|POST /sales/leads`, `GET|PUT|DELETE /sales/leads/{id}`, `PUT /sales/leads/{id}/stage`, `GET /sales/pipeline`

**Collections**
- `finance_settings`, `finance_invoices`, `finance_payments`, `sales_leads`

**Testing status** — 100% pass
- Backend unit tests: `/app/backend/tests/test_session_c1_20260215.py` (7/7)
- Backend HTTP API tests: `/app/backend/tests/test_session_c1_api_20260215.py` (23/23, created by testing agent)
- Frontend flows: 100% passing via testing_agent_v3_fork iteration_32 (create/edit/mark-paid invoice, settings persistence, kanban CRUD, stage change, HR regression)

**Files created**
- `/app/backend/finance_module.py` — full router + PDF renderer
- `/app/backend/sales_module.py` — leads router + pipeline aggregator
- `/app/frontend/src/pages/dashboard/FinanceModule.jsx` — invoices, editor modal, detail drawer, settings
- `/app/frontend/src/pages/dashboard/SalesModule.jsx` — kanban + table + editor
- `/app/backend/tests/test_session_c1_20260215.py`, `/app/backend/tests/test_session_c1_api_20260215.py`

**Files touched**
- `/app/backend/server.py` — registered finance + sales routers
- `/app/backend/email_service.py` — added `send_invoice_email()` (Resend + attachment, returns `{email_id, error}` shape)
- `/app/frontend/src/App.js` — imported + routed `FinanceModule` and `SalesModule`
- `/app/frontend/src/index.css` — added `.zy-input` shared form-input class

**Session C1 P0 modules — SHIPPED, jury-ready.**

### Remaining backlog (P1/P2)
- **P1** — Session C2: Projects · Planning · Time Tracking CRUD
- **P2** — Replace Meta (FB/IG) + LinkedIn OAuth stubs with real integrations
- **P2** — Photo/Video AI generation (fal.ai) — replace 'Coming soon' stubs
- **P2** — Accounting bank statement CSV auto-ingestion + journal drafting
- **BLOCKED** — Website builder custom-domain routing (awaiting Emergent Support)


### 2026-02-15 (later) — Jury demo workspace seeded for Finance & Sales

**Purpose**: When the XPRIZE jury logs into `jury@zynthoro.ai`, both Finance and Sales modules must show populated data on first click (no empty states during the walkthrough).

**Added** (`server.py` — new helper `_seed_finance_and_sales_demo`, called from `seed_jury_demo()`; idempotent, only inserts if collections empty):
- **finance_settings** — Zynthoro Demo Workspace branding (Amsterdam address, IBAN, VAT, 14-day terms, `ZY-` prefix)
- **6 finance_invoices** (all with realistic line items + tax):
  - `ZY-2026-0001` Aurora Studios — **PAID** €6,618.70
  - `ZY-2026-0002` Helix Robotics — **PAID** €10,164.00
  - `ZY-2026-0003` Lumen Therapeutics — **SENT** €13,418.90
  - `ZY-2026-0004` Sable & Co. Architects — **SENT** €169.38
  - `ZY-2026-0005` Verdant Foods — **DRAFT** €3,012.90
  - `ZY-2026-0006` Northwind Capital — **OVERDUE** €30,237.90
  - Totals: €63,621 invoiced · €16,782 paid · €43,826 outstanding
- **2 finance_payments** (auto-linked to the 2 paid invoices)
- **9 sales_leads** distributed across all 5 kanban stages:
  - **New** (2): Sophie Laurent · Élégance Paris, Marco Bianchi · Bianchi Automotive
  - **Contacted** (2): Emma van der Berg · GreenGrocer, James O'Connor · Dublin Digital
  - **Proposal** (2): Isabella Rossi · Rossi Interiors, David Nakamura · Kyoto Sake
  - **Won** (2): Fatima Al-Rashid · Desert Bloom, Klaus Weber · Weber Präzision
  - **Lost** (1): Priya Menon · Bengaluru Textiles
  - Totals: 9 leads · €142K open · €46K won · 1 lost
- All records flagged `is_demo: true` for future cleanup filtering.
- Bumped `next_invoice_seq` to 7 so the jury's first manually-created invoice is `ZY-2026-0007`.

**Verified**: Jury login → `/dashboard/sales` shows populated kanban with correct totals and Jury Tour overlay firing on top.

### 2026-02-15 — Session C2: Projects · Planning · Time Tracking (shipped)

**Scope**: 3 more P1 ERP modules with full CRUD, in the same pattern as C1. All P0/P1 core ERP modules now shipped ahead of XPRIZE Aug 17 jury review.

**Projects** (`/app/backend/projects_module.py` + `ProjectsModule.jsx` @ `/dashboard/projects`)
- Projects CRUD (name, description, status, domain, owner, dates, progress %, colour)
- Tasks CRUD nested under projects (title, assignee, due, priority, status: todo/in_progress/done)
- Milestones CRUD (title, due, toggleable completed state)
- **Auto-progress recomputation** — parent project's `progress` field is recomputed from (# done tasks / total tasks) whenever a task is created / updated / status-changed / deleted
- Cascade delete: deleting a project also removes its tasks + milestones + time_entries
- Stats: Total / On track / At risk / Completed

**Planning** (`/app/backend/planning_module.py` + `PlanningModule.jsx` @ `/dashboard/planning`)
- Workspace-wide sprints (per user's C2 choice — sprints not tied to a single project)
- Sprint CRUD (name, goal, dates, status planned/active/completed, capacity_hours)
- Task linking works by writing `sprint_id` on the existing `project_tasks` doc → **no duplication**, task appears in both Projects and Planning views
- `/planning/available-tasks` returns un-sprinted tasks (candidates for the picker)
- Deleting a sprint DETACHES tasks (they remain, just un-linked)
- Sprint summary: task_count / done / in_progress / todo / progress %
- Two-pane UI: left sprint list · right selected-sprint board with burndown + task picker

**Time Tracking** (`/app/backend/time_tracking_module.py` + `TimeTrackingModule.jsx` @ `/dashboard/time-tracking`)
- **Live timer** — one running per user; starting a new one auto-commits the old one to a `time_entry`
- Timer displays elapsed time with client-side tick
- Manual entries CRUD (date, hours, project/task, notes, billable Y/N)
- **Weekly timesheet** — grid grouped by (project, task) × 7 days of the week starting Monday (ISO week)
- Prev / Next / This-week navigation
- **CSV export** — `/api/time-tracking/entries/export.csv` returns `text/csv` with header `date,user_email,project,task,hours,billable,notes,source`; exposed on both Timer and Timesheet tabs
- Stats: Entries / Total hours / Billable hours

**Backend endpoints added** (all `/api`)
- Projects: `GET|POST /projects`, `GET|PUT|DELETE /projects/{id}`, `GET /projects/{id}/tasks`, `POST /projects/tasks`, `PUT /projects/tasks/{tid}`, `PUT /projects/tasks/{tid}/status`, `DELETE /projects/tasks/{tid}`, `POST /projects/milestones`, `PUT /projects/milestones/{mid}/toggle`, `DELETE /projects/milestones/{mid}`
- Planning: `GET|POST /planning/sprints`, `GET|PUT|DELETE /planning/sprints/{sid}`, `POST /planning/sprints/{sid}/tasks`, `DELETE /planning/sprints/{sid}/tasks/{tid}`, `GET /planning/available-tasks`
- Time Tracking: `GET /time-tracking/timer`, `POST /time-tracking/timer/start`, `POST /time-tracking/timer/stop`, `DELETE /time-tracking/timer`, `GET|POST /time-tracking/entries`, `PUT|DELETE /time-tracking/entries/{eid}`, `GET /time-tracking/timesheet`, `GET /time-tracking/entries/export.csv`

**Collections**
- `projects`, `project_tasks`, `project_milestones`, `sprints`, `time_entries`, `time_timers`

**Jury demo seed** (auto-called on startup, idempotent, `is_demo=true`):
- 5 projects (mix of statuses/domains, realistic descriptions)
- 15 tasks distributed across projects with mix of done/in-progress/todo
- 7 milestones (5 upcoming, 2 completed)
- 1 active sprint "Sprint 12 · Jury week" with 5 tasks pulled from 2 projects
- 8 time entries across the current week totalling 23.5h

**Founder Reset extended** — `POST /api/founder/reset-jury-demo` now also wipes+re-seeds all C2 collections. UI toast updated.

**Testing** — 100% pass
- Backend unit tests: `/app/backend/tests/test_session_c2_20260215.py` (7/7)
- Backend HTTP integration tests via testing_agent_v3_fork iteration_33: 10/10
- Frontend flows via Playwright: all critical paths pass (create project + task, sprint + task-link, timer start/stop, manual entry, weekly timesheet, CSV export)
- Regression: Sessions B (HR/Accounting/Communication/Compliance) + C1 (Finance/Sales) still working.

**Files created**
- `/app/backend/projects_module.py`
- `/app/backend/planning_module.py`
- `/app/backend/time_tracking_module.py`
- `/app/frontend/src/pages/dashboard/ProjectsModule.jsx`
- `/app/frontend/src/pages/dashboard/PlanningModule.jsx`
- `/app/frontend/src/pages/dashboard/TimeTrackingModule.jsx`
- `/app/backend/tests/test_session_c2_20260215.py`

**Files touched**
- `/app/backend/server.py` — 3 new router registrations + `_seed_projects_planning_time_demo` helper + extended founder-reset endpoint
- `/app/frontend/src/App.js` — 3 new routes
- `/app/frontend/src/pages/dashboard/Settings.jsx` — updated founder-reset toast copy

**All P0/P1 core ERP modules — SHIPPED, jury-ready.**

### Updated remaining backlog (P2)
- Replace Meta (FB/IG) + LinkedIn OAuth stubs with real integrations
- Photo/Video AI generation (fal.ai) — replace 'Coming soon' stubs
- Accounting bank statement CSV auto-ingestion + journal drafting
- BLOCKED: Website builder custom-domain routing (awaiting Emergent Support)


### 2026-02-15 (later) — Time Tracking → Finance: "Bill hours" shortcut

**Purpose**: One-click conversion of a project's unbilled billable time into a draft invoice — closes the end-to-end loop between Time Tracking and Finance.

**User choices**:
- Client comes from **existing Sales leads at Won stage** (dropdown in the modal)
- Line items grouped **one per task** (task title × hours × rate)
- After invoicing, entries are marked `invoiced=True` + store `invoice_id` — deleting the resulting invoice releases them back to the unbilled pool

**Backend** (`/app/backend/projects_module.py`)
- `GET /api/projects/{pid}/billable-summary` — returns unbilled billable hours grouped by task (used by the UI to preview the line items before creation)
- `POST /api/projects/{pid}/invoice-billable-time` — body `{lead_id, hourly_rate, currency?, due_in_days?, tax_rate?}`. Validates the lead belongs to the workspace AND has `stage="won"`, groups entries by task, creates a `finance_invoices` doc using the existing finance settings + auto-numbered sequence, marks the used entries as `invoiced=True, invoice_id=<new>`, and logs an activity event.

**Finance delete cascade** (`/app/backend/finance_module.py`)
- `DELETE /api/finance/invoices/{id}` now also un-marks any time_entries with `invoice_id={id}` (sets `invoiced=false, invoice_id=null`) so the hours become invoiceable again — reversible workflow.

**Frontend** (`ProjectsModule.jsx` — Project detail drawer)
- Green banner card "€ 10.5h of unbilled billable time · Across 3 tasks" with a **"Bill hours → invoice draft"** button
- Modal shows:
  - Won-lead dropdown (auto-selects first)
  - Rate + currency + tax + due-days inputs
  - Live preview table of line items grouped by task with running subtotal + VAT total
  - After creation, toast with "View" action navigates directly to `/dashboard/finance`
- If no won leads exist, shows a friendly prompt to move a lead to Won first.

**Testing**
- Backend regression tests: `/app/backend/tests/test_bill_hours_20260215.py` (2/2 pass) — verifies non-billable + already-invoiced entries are correctly excluded, and delete-invoice releases entries.
- E2E manual verification: jury workspace 10.5h across 3 tasks → invoice `ZY-2026-0007` for €1,905.75 (10.5h × €150 + 21% VAT). Deleting the invoice restored 10.5h to unbilled pool.

**Files touched**
- `/app/backend/projects_module.py` — 2 new endpoints (billable-summary, invoice-billable-time) + BillHoursIn schema + finance_module helper imports
- `/app/backend/finance_module.py` — delete-invoice cascade updated to release time entries
- `/app/frontend/src/pages/dashboard/ProjectsModule.jsx` — new BillHoursModal + green banner card in the project detail drawer + useNavigate import
- `/app/backend/tests/test_bill_hours_20260215.py` — new regression test


### 2026-02-15 (later) — Invoice PDF: company logo on header

**Purpose**: Match the invoice PDF to the workspace's brand. The logo the user uploads in Settings → Company logo (already stored as base64 on the user record via `/api/account/logo`) is now embedded at the top-right of every invoice PDF, above the "INVOICE + number" title.

**Backend** (`/app/backend/finance_module.py`)
- `_render_invoice_pdf(inv, settings, logo_bytes=None)` — new optional param. When provided, decodes the bytes into a reportlab `Image` object, constrains to max 42×28mm preserving aspect ratio, right-aligns above the "INVOICE" heading. Silently falls back to text-only if the image can't be decoded (corrupt or unsupported format) — never fails the PDF.
- `_get_logo_bytes(wo)` helper fetches `users.company_logo_data` (base64) for the workspace owner and returns raw bytes.
- Both `/api/finance/invoices/{id}/pdf` and `/api/finance/invoices/{id}/send-email` now call `_get_logo_bytes` and pass to the renderer, so the client always sees the logo whether they download or receive it by email.

**Testing** — `/app/backend/tests/test_session_c1_20260215.py` (8/8 pass)
- New `test_finance_pdf_embeds_logo_when_provided` — verifies that passing logo bytes results in a larger PDF containing `/XObject` (reportlab's image dict).
- Manual visual check via pdftoppm: founder-generated invoice shows the uploaded logo top-right; jury user with no logo gets the clean text-only header as before.

**Files touched**
- `/app/backend/finance_module.py` — Image import, `_render_invoice_pdf` signature + header layout, `_get_logo_bytes` helper, both endpoints pass logo to renderer
- `/app/backend/tests/test_session_c1_20260215.py` — extra test for logo embedding


### 2026-02-15 (later) — Code review fixes: 3 P0/P1 defects in Finance & Billing

Following an internal code review of Sessions B/C1/C2 modules, fixed the 3 most impactful defects (option D of the plan — pagination truncation deferred to a later session).

**FIX #1 — HIGH · Invoice PDF crash on `<` in user-supplied fields** (`finance_module.py`)
- **Bug**: Any customer whose name/notes/bank details contained `<` (e.g. `"Acme <div> Corp"`, `"IBAN NL01 <bank>"`) crashed the PDF renderer with `ValueError: Parse error` — HTTP 500 on both `/pdf` and `/send-email` endpoints. Broke core billing for any customer with punctuation resembling markup.
- **Fix**: New `_rl(text)` helper — `xml.sax.saxutils.escape` + `\n` → `<br/>` — applied to every user-controlled field embedded in reportlab `Paragraph` markup: `company_name`, `company_address`, `company_email`, `company_vat`, `client_name`, `client_address`, `client_email`, `notes`, `payment_terms`, `bank_details`, `item.description`, `invoice.number`, and the email body HTML.
- **Verified** — E2E curl created an invoice with `<div>`, `<font color=red>`, `<b>` fragments in every field. PDF now renders successfully (200, 3.3kb valid `%PDF-` stream) instead of 500.

**FIX #2 — MED · Invoice status flipped to "sent" even when email failed** (`finance_module.py`)
- **Bug**: `send-email` endpoint unconditionally updated `status='sent'` + `sent_at=now()` regardless of Resend outcome. A quota failure, bad key, or oversized attachment silently marked the invoice sent → the founder believed the client received it → collections/overdue tracking was wrong.
- **Fix**: Gate the status update on `email_id.get('email_id')` — only flip when Resend returned a real ID. Response now returns `ok: false` + the error message when send fails, so the UI toast correctly says "Email failed" and the invoice stays draft.

**FIX #3 — MED · Bill-Hours race allowed double-billing** (`projects_module.py`)
- **Bug**: `POST /api/projects/{pid}/invoice-billable-time` read unbilled entries, built the invoice, then marked entries — three separate ops. Two simultaneous calls (double-click, client retry) could both see the same unbilled set and each create a full invoice → the same hours appeared on two draft invoices.
- **Fix**: Two-step **claim-then-commit** pattern:
  1. Atomic `update_many` with a unique `claim_token` — MongoDB's per-doc atomicity guarantees each entry is claimed by exactly one concurrent request.
  2. Fetch only entries with THIS request's claim token.
  3. Build invoice, then `update_many` swaps `invoice_id` from claim_token to real invoice id.
  4. On any downstream failure (401, 500, etc.), the `try/except` releases claimed entries back to the unbilled pool → no orphaned "invoiced with no invoice" state.
- **Verified** — 3 concurrent httpx calls to the same endpoint: **1 succeeded** (201, 10.5h across 3 entries), **2 correctly returned 400** ("No unbilled billable time entries"). Pre-fix same test would have created 3 invoices for 31.5h phantom hours.

**Tests** — `/app/backend/tests/test_code_review_fixes_20260215.py` (5/5 pass)
- `test_pdf_renders_when_client_name_contains_angle_brackets`
- `test_rl_escape_helper_escapes_and_preserves_newlines`
- `test_invoice_status_unchanged_when_email_returns_no_id`
- `test_atomic_claim_prevents_double_billing`
- `test_claim_release_on_failure_puts_entries_back`

**Deferred (P2 backlog)**
- LOW: Float money math → Decimal for cent-perfect totals at scale
- LOW: Overdue-flip should move from GET handler into scheduled job
- MED: Finance dashboard pagination — currently `to_list(500)` silently truncates for very-high-volume workspaces (below current customer scale, but worth fixing before mass adoption).

**Files touched**
- `/app/backend/finance_module.py` — `_rl` helper + all user-string interpolations + email HTML + email-failure gating
- `/app/backend/projects_module.py` — atomic claim-then-commit for `invoice-billable-time`
- `/app/backend/tests/test_code_review_fixes_20260215.py` — new regression suite (5 tests)



### 2026-02-24 — Footer social proof: "As seen on" strip (shipped)
Consolidated the TAAFT / Product Hunt / Uneed badges (previously stacked inside the brand column of the footer) into a **dedicated horizontal "As seen on" strip** placed just above the copyright bar. Cleaner hierarchy, consistent badge height (48–54px), and gives the social-proof block its own row so it reads as a credibility signal rather than clutter next to the tagline.

- Kept all three original `data-testid`s (`footer-taaft-badge`, `footer-producthunt-badge`, `footer-uneed-badge`) — no test breakage.
- New wrapper `data-testid="footer-as-seen-on"` for the strip.
- Static `<a>` anchors in `/app/frontend/public/index.html` **untouched** — TAAFT/PH/Uneed crawlers keep verifying via those non-JS anchors.
- JSON-LD `sameAs` block untouched.

**Files touched**
- `/app/frontend/src/components/layout/Footer.jsx` — removed inline badges from brand column, added `footer-as-seen-on` strip section.


### 2026-07-26 — Meta OAuth: unmock-ready (real live-mode wiring)
The Meta OAuth code path already implemented the full live flow (code → short → long → Page tokens with IG discovery, encrypted at rest with Fernet, publish + schedule via APScheduler tick). Two gaps were preventing an actual go-live once `META_APP_ID`/`META_APP_SECRET` land:

1. **No frontend landing page** for Meta's browser redirect. Meta was configured to redirect to `/dashboard/marketing/meta-callback`, but that React route didn't exist — the callback would 404.
2. **`requires_reauth`** flag surfaced by the backend when Meta returned OAuth error code 190 was never rendered in the UI.

**Fixes shipped**
- New `/app/frontend/src/pages/dashboard/MetaCallback.jsx` — accepts `?code=…&state=…` from Meta, forwards it to `GET /api/oauth/meta/callback` with the user's JWT (auto-attached via axios interceptor since the page mounts inside `ProtectedRoute`), then toasts + redirects back to `/dashboard/ai-studio`. Handles Meta's `?error=access_denied` branch too. Testids: `meta-callback-page`, `meta-callback-title`, `meta-callback-message`.
- Route registered in `/app/frontend/src/App.js` **before** the `:slug` catch-all so it isn't shadowed.
- `META_REDIRECT_URI` in `/app/backend/.env` retargeted to `https://zynthoro.ai/dashboard/meta-callback` (simpler than nesting under `/marketing`, and matches the new route). Mock fallback default updated to match.
- Reauth banner in `AIStudio.jsx` — when any connected Page returns `requires_reauth: true` from `GET /api/oauth/meta/status`, a compact yellow banner appears above the Page picker with a Reconnect button (`ai-studio-meta-reauth-banner`, `ai-studio-meta-reconnect`).
- Housekeeping: OAuth state docs older than 15 min are cleaned up on each callback hit (`meta_oauth_module.py`).

**What the user must do when Meta App is approved**
1. Set `META_APP_ID` + `META_APP_SECRET` in `/app/backend/.env` (or via Secrets in prod).
2. In the Meta App dashboard, register `https://zynthoro.ai/dashboard/meta-callback` as an authorized OAuth Redirect URI (Facebook Login for Business → Settings).
3. Ensure the App has these scopes approved via App Review: `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, `business_management`.
4. Restart backend (`sudo supervisorctl restart backend`) — the module auto-switches from mock to live mode once both env vars are present.

**Verified**
- Full mock flow via curl: `/start` → `/callback` → `/status` → `/disconnect` (all green).
- Frontend `/dashboard/meta-callback?code=…&state=bogus` correctly renders "Connection failed · Invalid or expired OAuth state." then redirects to AI Studio.
- No regressions in existing scheduling loop (APScheduler tick still fires every 60s).

**Files touched**
- `/app/backend/.env` — updated `META_REDIRECT_URI`
- `/app/backend/meta_oauth_module.py` — state TTL cleanup + redirect default
- `/app/frontend/src/App.js` — new route
- `/app/frontend/src/pages/dashboard/MetaCallback.jsx` — created
- `/app/frontend/src/pages/dashboard/AIStudio.jsx` — reauth banner + compact reconnect variant

### 2026-07-27 — Homepage slim-down + dedicated public pages
**Problem**: Homepage was ~15 stacked sections (Hero → SocialProof → KickstartPricing → WhyZynthoro → Domains → ProductionSection → Assistants → VoiceAI → Pricing → PricingComparisonTables → EnterpriseSection → Assist → Comparison → AnyDevice → LatestArticles). A visitor couldn't understand what Zynthoro is in 10 seconds — too much text per screen, no clear signposting.

**Restructure** (approved by user 2026-07-27):

Homepage `/` now contains **only**:
1. `Hero` — tagline + CTA
2. `SocialProof` — short strip
3. `HomeIntro` (new) — one-line explainer: *"One AI-native platform that replaces the 8–15 disconnected tools your business runs on — with four AI specialists that already know your company."*
4. `HomeAssistantsBrief` (new) — 4-card grid (Zyntha · Thoro · Zyona · Zynthoro Assist) with "Explore the assistants →" CTA to `/assistants`
5. `HomePricingBrief` (new) — 3-card teaser (Kickstart from €79 / Subscriptions from €24.99/mo / Enterprise custom) with "See full pricing & compare tiers →" CTA to `/pricing`
6. `LatestArticles`

Three new public pages:
- **`/modules`** — Domains (12 modules) + ProductionSection + WhyZynthoro + AnyDeviceSection
- **`/assistants`** — Assistants (Zyntha/Thoro/Zyona detail) + Assist (Zynthoro Assist) + VoiceAISection
- **`/pricing`** — KickstartPricing + Pricing (full tiers) + PricingComparisonTables + EnterpriseSection + Comparison (vs SAP/HubSpot)

Each new page has its own SEO title + meta description + wraps in `PresaleDialogProvider` + Navbar + Footer.

**Navbar** rebuilt to link-based (was anchor-based): `Modules` · `Assistants` · `Pricing` · `Blog` (+ Book a call · Log in · Get started). Active state highlights the current route. Logo now goes to `/`. Testids: `nav-platform` (Modules), `nav-assistants` (new), `nav-pricing` (Pricing), `nav-blog` (new).

**Sitemap** updated — `/modules`, `/assistants`, `/pricing` added to `/api/sitemap.xml` at priority 0.9.

**Founder-only blog delete** — new `DELETE /api/blog/posts/{slug}` guarded by `get_founder_user`. Returns 403 for non-founder, 404 for missing slug, 200 `{ok:true, slug, deleted:1}` on success. Bundled into this deploy so we can purge the leftover Outrank test post `sample-article-title-for-testing` from prod after redeploy.

**Files created**
- `/app/frontend/src/pages/Modules.jsx`
- `/app/frontend/src/pages/AssistantsPage.jsx`
- `/app/frontend/src/pages/PricingPage.jsx`
- `/app/frontend/src/components/sections/HomeIntro.jsx`
- `/app/frontend/src/components/sections/HomeAssistantsBrief.jsx`
- `/app/frontend/src/components/sections/HomePricingBrief.jsx`

**Files rewritten / updated**
- `/app/frontend/src/pages/Home.jsx` — reduced from 15 sections to 6
- `/app/frontend/src/components/layout/Navbar.jsx` — anchor-based → route-based, active-link styling
- `/app/frontend/src/App.js` — 3 new routes registered before `/dashboard/*`
- `/app/backend/blog_module.py` — DELETE endpoint + sitemap additions
- `/app/backend/server.py` — pass `get_founder_user` to `blog_module.build_router`

**Verified**
- Homepage renders slim (screenshot confirmed): only the 6 intended sections present; old dense sections absent.
- `/modules`, `/assistants`, `/pricing` all render with correct titles + wrapped in shared Navbar+Footer.
- `DELETE /api/blog/posts/{slug}` with founder JWT → 200 delete; jury JWT → 403; nonexistent slug → 404. Full curl round-trip: create test post via Outrank webhook → delete → verify 404.
- Nav "Modules" link correctly highlights on `/modules`.


### 2026-07-30 — Trial-leak fix + prerender flash fix + TAAFT10 UX warning
**Bug**: `/auth/signup` was creating users with `subscription_plan="Presale"` AND `is_trial=False`, which unintentionally bypassed the trial gate in `DashboardLayout.jsx` (line 43: `if (!user?.is_trial) return "not_trial"`) — the "not_trial" branch treats a user as fully paying, so new external signups were getting unpaid full access to all 12 modules. Four external accounts hit this state between 20–29 July.

**Fixes shipped**
1. **`SignupIn` model** — removed the client-controlled `is_trial` field entirely. All new signups now unconditionally get `is_trial=True`, `trial_started_at=now`, `trial_expires_at=now+24h`. Real tier access is only granted post-payment (via Stripe webhook) or by explicit founder action.
2. **New founder endpoint** `POST /api/founder/users/convert-to-trial` — takes `{email}`, sets `is_trial=True` + fresh 24h expiry, refuses to touch `is_founder/is_demo/is_qa_test/is_unlimited` accounts. Non-destructive (leaves `subscription_plan`, invoices, projects intact).
3. **Prerender flash fix** — `<div id="prerender-content">` now hidden by CSS (`display:none`) with a `<noscript>` counter-block that reveals it for JS-off users. Eliminates the ~6-second flash of raw prerender HTML on every route (including SPA fallback pages `/login`, `/signup`, `/dashboard/*` which use `build/index.html`).
4. **TAAFT10 promo UX** — `validate-promo` now returns `first_time_only` flag; SubscribeTier UI shows a "first-time customers only" warning before checkout.

**Entitlement audit (invariant proven)**
Every write to `subscription_plan` outside of `/auth/signup="Presale"` is gated by either:
- Paid Stripe transaction (`payment_transactions.paid == True`), or
- Founder-only admin call (`Depends(get_founder_user)`), or
- Seed function (founder self-owner, jury demo)

No public endpoint exists that lets a user self-escalate. Verified end-to-end on production by testing_agent (iteration_34.json): PATCH/PUT on `/api/auth/me` and `/api/users/me` with `subscription_plan` all return 405/404/422.

**Migration executed on production 2026-07-30 13:57 UTC**
- `weedoraugustinek89@gmail.com` — converted to trial (24h expiry)
- `hesoka1674@gicont.com` — converted to trial (24h expiry)
- `alin@theresanaiforthat.com` — **UNCHANGED** (TAAFT reviewer, keeps current access)
- `stefan@theresanaiforthat.com` — **UNCHANGED** (TAAFT reviewer, keeps current access)

**Known open issue (not shipped in this deploy)**
TAAFT10 promo (`promo_1TweW85sy2phCvUrlsxtqpKy`) resolves on preview backend but fails on production with "Deze promocode bestaat niet of is verlopen". Same code path, same tier_catalog.py — root cause is likely a Stripe account mismatch between preview `STRIPE_SECRET_KEY` and production `STRIPE_SECRET_KEY` (or the promo is not `active=True` in the account prod is talking to). Separate follow-up.

**Files touched**
- `/app/backend/server.py` — SignupIn model + /auth/signup body + new /founder/users/convert-to-trial endpoint + first_time_only in validate-promo response
- `/app/backend/tier_catalog.py` — resolve_promotion_code now returns first_time_only flag
- `/app/frontend/scripts/prerender.js` — hide-CSS injection with <noscript> fallback
- `/app/frontend/src/pages/SubscribeTier.jsx` — first-time-only warning UI

