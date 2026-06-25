/**
 * Canonical Zynthoro plan catalog used across the dashboard for
 * upgrade nudges, the Change-Plan dialog (Fix 8) and feature gating.
 *
 * Keep `key` values in sync with backend `PLAN_PRICE_IDS`
 * in `/app/backend/stripe_subscriptions.py`.
 */
export const PLANS = [
  {
    key: "Starter",
    name: "Starter",
    price: 499,
    priceLabel: "€499 / month",
    tagline: "Foundation — start lean, scale smart.",
    workspaces: 1,
    maxLevel: 3,
    highlights: ["Connect 2 social accounts", "Manual posting", "Basic photo & video tools"],
  },
  {
    key: "Creator",
    name: "Creator",
    price: 699,
    priceLabel: "€699 / month",
    tagline: "Full AI creator suite.",
    workspaces: 1,
    maxLevel: 3,
    highlights: [
      "All social platforms (FB, IG, LinkedIn, TikTok, X, YouTube)",
      "Auto-post scheduler + content calendar",
      "AI photo suite (PicsArt-level)",
      "AI video suite (CapCut-level)",
      "AI funnels & landing pages",
    ],
  },
  {
    key: "Business",
    name: "Business",
    price: 899,
    priceLabel: "€899 / month",
    tagline: "Most Popular — full sales + accounting.",
    workspaces: 3,
    maxLevel: 5,
    badge: "Most Popular",
    highlights: [
      "Everything in Creator",
      "AI email campaigns",
      "Audience segmentation",
      "Post analytics & AI lead scoring",
      "Levels 1–5",
    ],
  },
  {
    key: "Agency",
    name: "Agency",
    price: 1199,
    priceLabel: "€1,199 / month",
    tagline: "Multi-client management.",
    workspaces: 5,
    maxLevel: 7,
    highlights: [
      "Everything in Business",
      "Multi-client social management",
      "Team workflows for approval",
      "White-label reports",
      "Levels 1–7",
    ],
  },
  {
    key: "Enterprise Basic",
    name: "Enterprise Basic",
    price: 2499,
    priceLabel: "€2,499 / month",
    tagline: "All 12 domains + full ERP.",
    workspaces: "Unlimited",
    maxLevel: 10,
    isEnterprise: true,
    highlights: [
      "Everything in Agency",
      "All 12 ERP domains",
      "Levels 1–10",
      "Unlimited workspaces",
      "Unlimited team members",
    ],
  },
  {
    key: "Enterprise Plus",
    name: "Enterprise Plus",
    price: 3999,
    priceLabel: "€3,999 / month",
    tagline: "Higher AI quotas + priority support.",
    workspaces: "Unlimited",
    maxLevel: 10,
    isEnterprise: true,
    highlights: [
      "Everything in Enterprise Basic",
      "3x AI generation quotas",
      "Dedicated CSM",
      "Priority Claude routing",
      "8h SLA support",
    ],
  },
  {
    key: "Enterprise Advanced",
    name: "Enterprise Advanced",
    price: 5999,
    priceLabel: "€5,999 / month",
    tagline: "Mission-critical SLA + custom integrations.",
    workspaces: "Unlimited",
    maxLevel: 10,
    isEnterprise: true,
    highlights: [
      "Everything in Enterprise Plus",
      "99.99% uptime SLA",
      "Custom integrations",
      "24/7 phone support",
      "Custom level names",
    ],
  },
];

export const PLAN_BY_KEY = Object.fromEntries(PLANS.map((p) => [p.key, p]));

/** Plan order index. Presale → -1. Any Enterprise tier maps to its own index. */
export function planOrder(key) {
  if (!key) return -1;
  const idx = PLANS.findIndex((p) => p.key === key);
  if (idx >= 0) return idx;
  // Legacy / shorthand 'Enterprise' label → first Enterprise tier
  if (key.startsWith("Enterprise")) return PLANS.findIndex((p) => p.isEnterprise);
  return -1;
}

/** Is the user's plan at or above the required plan? */
export function planAtLeast(userPlan, requiredPlanKey) {
  return planOrder(userPlan) >= planOrder(requiredPlanKey);
}

/** Returns the plan immediately above the user's current plan, or null if on top. */
export function nextPlanAfter(currentKey) {
  const idx = planOrder(currentKey);
  if (idx < 0) return PLANS[1];
  return PLANS[idx + 1] || null;
}
