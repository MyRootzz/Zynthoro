/**
 * Canonical Zynthoro plan catalog used across the dashboard for
 * upgrade nudges, change-plan dialog, and feature gating.
 *
 * Keep names in sync with backend `PLAN_MAX_LEVEL` and Stripe price IDs
 * once they are configured.
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
    upgradePath: "/subscribe/starter",
    comingSoon: false,
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
    upgradePath: "/subscribe/creator",
    comingSoon: true,
  },
  {
    key: "Business",
    name: "Business",
    price: 899,
    priceLabel: "€899 / month",
    tagline: "Most Popular — full sales + accounting.",
    workspaces: 3,
    maxLevel: 5,
    highlights: [
      "Everything in Creator",
      "AI email campaigns",
      "Audience segmentation",
      "Post analytics & AI lead scoring",
      "Levels 1–5",
    ],
    upgradePath: "/subscribe/business",
    badge: "Most Popular",
    comingSoon: true,
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
    upgradePath: "/subscribe/agency",
    comingSoon: true,
  },
  {
    key: "Enterprise",
    name: "Enterprise",
    price: 2499,
    priceLabel: "from €2,499 / month",
    tagline: "All 12 domains + full ERP.",
    workspaces: "Unlimited",
    maxLevel: 10,
    highlights: [
      "Everything in Agency",
      "All 12 ERP domains",
      "Levels 1–10 + custom level names",
      "Unlimited workspaces",
      "Unlimited team members",
    ],
    upgradePath: "/subscribe/enterprise",
    comingSoon: true,
  },
];

export const PLAN_BY_KEY = Object.fromEntries(PLANS.map((p) => [p.key, p]));

/** Returns the plan ABOVE the user's current plan, or null if already on top. */
export function nextPlanAfter(currentKey) {
  // Normalise enterprise variants
  const cur = currentKey?.startsWith("Enterprise") ? "Enterprise" : currentKey || "Presale";
  const idx = PLANS.findIndex((p) => p.key === cur);
  if (idx < 0) return PLANS[1]; // Presale → Creator
  return PLANS[idx + 1] || null;
}

/** Plan order index (0 = Starter, … 4 = Enterprise). Presale → -1. */
export function planOrder(key) {
  if (!key) return -1;
  if (key.startsWith("Enterprise")) return 4;
  return PLANS.findIndex((p) => p.key === key);
}

/** Is the user's plan at or above the required plan? */
export function planAtLeast(userPlan, requiredPlanKey) {
  return planOrder(userPlan) >= planOrder(requiredPlanKey);
}
