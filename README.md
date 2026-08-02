# Zynthoro

AI-native ERP platform for SMEs powered by Google Gemini 2.5 Flash and Anthropic Claude Sonnet 4.6.

---

## Overview

This repository contains the production source code and supporting evidence for our Build with Gemini XPRIZE submission.

Zynthoro is an AI-native Enterprise Resource Planning platform for small and medium-sized businesses. It combines business management, AI automation and operational workflows into a single integrated environment, replacing the eight to fifteen disconnected tools most SMEs run on.

**Public launch:** 30 June 2026

**Platform:** https://zynthoro.ai
---

## Core Business Domains

Twelve integrated business domains:

- Planning & Organisation
- Time Tracking
- Sales Administration
- Finance & Invoicing
- Accounting
- Project Management
- HR & Personnel
- Operations
- Marketing & Content
- Communication & Collaboration
- Compliance & Security
- AI Studio

---

## AI Assistants

Four specialised assistants, each with a defined role and an enforced boundary.

### Zyntha — Content & SEO
Google Gemini 2.5 Flash (all plans)

Blog posts, social copy, SEO strategy and campaigns, written from the company's own business context.

### Thoro — Process & Implementation
Google Gemini 2.5 Flash (Starter & Creator)
Anthropic Claude Sonnet 4.6 (Business and above)

Workflows, SOPs, automation logic and implementation architecture.

### Zyona — Strategy & Growth
Anthropic Claude Sonnet 4.6 (all plans)

Board-level strategy, growth planning and financial analysis. Challenges assumptions rather than confirming them.

### Zynthoro Assist — Platform Guide
Anthropic Claude Sonnet 4.6 (all plans)

Platform orientation and account guidance. No strategy, no marketing.

All four work from the same shared business context rather than isolated prompts.

---

## AI Features

- Multi-model routing per assistant and subscription plan
- AI business registration verification
- AI-assisted bank statement categorisation
- Voice input via Web Speech API
- Automated daily operational digest
- Full AI execution logging

---

## Stripe Integration

Production Stripe environment.

- Live subscriptions across nine tiers
- Three lifetime licence tiers
- Subscription lifecycle management
- Seat add-ons
- Stripe webhooks

---

## Technology

**AI models**
- Google Gemini 2.5 Flash
- Anthropic Claude Sonnet 4.6

**Stack**
- React and TypeScript (frontend)
- FastAPI and Python (backend)
- MongoDB (data layer)
- Stripe (billing)
- JWT authentication with two-factor support
- EU-hosted, GDPR-ready

---

## Evidence

Supporting documentation for the XPRIZE submission:

- `EVIDENCE.md` — evidence of product running in production
- `PROFIT_EVIDENCE.md` — financial evidence for the competition period
- `Product_Evidence/` — production screenshots, AI execution logs demonstrating multi-model routing, API usage evidence and supporting operational documentation

---

## Founder

**Ramona Vijfvinkel**
Founder & CEO
Casa Haya International BV · KvK 99196581 · The Netherlands

https://zynthoro.ai

---

*Built with Google Gemini 2.5 Flash and Anthropic Claude Sonnet 4.6*
*Production launch: 30 June 2026*
