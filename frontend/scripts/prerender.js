#!/usr/bin/env node
/**
 * postbuild prerender — runs after `yarn build`.
 *
 * Why this exists
 * ---------------
 * Zynthoro is a CRA SPA: the built `index.html` ships with an empty
 * `<div id="root"></div>`, which means non-JS crawlers (Twitter/X cards,
 * LinkedIn preview, older Bing/DuckDuckGo, and Google's first-pass
 * indexer) see zero content and can't rank/preview the site.
 *
 * This script generates a per-route `build/<path>/index.html` with:
 *   - route-specific <title>, meta description, canonical + OG/Twitter tags
 *   - semantic HTML (H1/H2/paragraphs) inside `<div id="root">` matching
 *     what the React page shows on that route
 *   - existing default JSON-LD structured data preserved
 *
 * The React runtime uses `ReactDOM.createRoot()` (not `hydrateRoot`), so
 * on mount it simply replaces the initial DOM — no hydration mismatch.
 *
 * The static file server (Nginx `try_files $uri $uri/ /index.html`)
 * naturally serves the more specific per-route file first, falling back
 * to the root SPA shell for any route we didn't prerender.
 *
 * Failure mode
 * ------------
 * If the production blog API is unreachable at build time, blog-post
 * prerendering is skipped with a warning (the build itself never fails).
 * Static routes are always generated.
 */
const fs = require("fs");
const path = require("path");

const BUILD_DIR = path.join(__dirname, "..", "build");
const BASE_URL = "https://zynthoro.ai";
const API_URL = process.env.PRERENDER_API_URL || `${BASE_URL}/api`;
const FETCH_TIMEOUT_MS = 8000;

// ---------- helpers ------------------------------------------------------
const esc = (s) =>
  String(s || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");

const fetchJson = async (url) => {
  const ac = new AbortController();
  const t = setTimeout(() => ac.abort(), FETCH_TIMEOUT_MS);
  try {
    const r = await fetch(url, { signal: ac.signal });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    return await r.json();
  } finally {
    clearTimeout(t);
  }
};

/** Rewrite <title>, description, canonical + OG/Twitter tags in the template. */
function applyMeta(template, { title, description, url, image, type }) {
  let html = template;
  html = html.replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`);
  html = html.replace(
    /<meta name="description" content="[^"]*"\s*\/?>/,
    `<meta name="description" content="${esc(description)}" />`
  );
  html = html.replace(
    /<link rel="canonical" href="[^"]*"\s*\/?>/,
    `<link rel="canonical" href="${esc(url)}" />`
  );
  html = html.replace(
    /<meta property="og:title" content="[^"]*"\s*\/?>/,
    `<meta property="og:title" content="${esc(title)}" />`
  );
  html = html.replace(
    /<meta property="og:description" content="[^"]*"\s*\/?>/,
    `<meta property="og:description" content="${esc(description)}" />`
  );
  html = html.replace(
    /<meta property="og:url" content="[^"]*"\s*\/?>/,
    `<meta property="og:url" content="${esc(url)}" />`
  );
  html = html.replace(
    /<meta property="og:type" content="[^"]*"\s*\/?>/,
    `<meta property="og:type" content="${esc(type || "website")}" />`
  );
  if (image) {
    html = html.replace(
      /<meta property="og:image" content="[^"]*"\s*\/?>/,
      `<meta property="og:image" content="${esc(image)}" />`
    );
    html = html.replace(
      /<meta name="twitter:image" content="[^"]*"\s*\/?>/,
      `<meta name="twitter:image" content="${esc(image)}" />`
    );
  }
  html = html.replace(
    /<meta name="twitter:title" content="[^"]*"\s*\/?>/,
    `<meta name="twitter:title" content="${esc(title)}" />`
  );
  html = html.replace(
    /<meta name="twitter:description" content="[^"]*"\s*\/?>/,
    `<meta name="twitter:description" content="${esc(description)}" />`
  );
  return html;
}

/** Inject the crawler-visible content inside the empty `<div id="root">`. */
function injectRootContent(template, contentHtml) {
  return template.replace(
    /<div id="root"><\/div>/,
    `<div id="root"><div id="prerender-content">${contentHtml}</div></div>`
  );
}

function writePage(routePath, html) {
  const outDir = routePath === "/" ? BUILD_DIR : path.join(BUILD_DIR, routePath.replace(/^\//, ""));
  fs.mkdirSync(outDir, { recursive: true });
  const outFile = path.join(outDir, "index.html");
  fs.writeFileSync(outFile, html);
  console.log(`  ✓ ${routePath}  →  ${path.relative(BUILD_DIR, outFile)}`);
}

// ---------- static page content ------------------------------------------
const home = `
<header>
  <p>The Next-Gen AI ERP</p>
  <h1>Zynthoro — One AI-native platform to replace the 8–15 disconnected tools your business runs on.</h1>
  <p>Four AI specialists that already know your company: Zyntha (Content &amp; SEO), Thoro (Process &amp; Implementation), Zyona (Strategy) and Zynthoro Assist (platform guide).</p>
  <p><a href="/signup">Get started</a> · <a href="/pricing">See pricing</a> · <a href="/modules">Explore modules</a></p>
</header>
<section>
  <h2>Four AI specialists. One platform.</h2>
  <p>Purpose-built AIs that already know your data. No prompt engineering required.</p>
  <ul>
    <li><strong>Zyntha</strong> — Content &amp; SEO. Creative, energetic.</li>
    <li><strong>Thoro</strong> — Process &amp; Implementation. Technical, precise.</li>
    <li><strong>Zyona</strong> — Strategy &amp; Growth. Sharp, board-level.</li>
    <li><strong>Zynthoro Assist</strong> — Your 24/7 platform guide.</li>
  </ul>
  <p><a href="/assistants">Explore the assistants</a></p>
</section>
<section>
  <h2>Three ways to buy Zynthoro.</h2>
  <p>Lifetime deals, monthly subscriptions, or Enterprise. No seat fees, no surprises.</p>
  <ul>
    <li><strong>Kickstart</strong> — from €79 lifetime. One-time payment. Own it forever.</li>
    <li><strong>Subscriptions</strong> — from €24.99/mo. Full platform + AI credits. Cancel any time.</li>
    <li><strong>Enterprise</strong> — Custom annual. SSO, dedicated support, unlimited seats.</li>
  </ul>
  <p><a href="/pricing">See full pricing &amp; compare tiers</a></p>
</section>
<section>
  <h2>Latest articles</h2>
  <p>Read the latest insights from the Zynthoro team on the <a href="/blog">Blog</a>.</p>
</section>
`;

const modules = `
<header>
  <p>The platform</p>
  <h1>12 modules. One AI. One truth.</h1>
  <p>Every module talks to every other module — no more copying data between disconnected tools. Zynthoro replaces 8–15 SaaS subscriptions with a single AI-native ERP built for European SMEs.</p>
</header>
<section>
  <h2>Business modules</h2>
  <ul>
    <li><strong>Planning &amp; Organisation</strong> — schedules, resources, project plans.</li>
    <li><strong>Time Tracking</strong> — timesheets, approvals, billable hours.</li>
    <li><strong>Sales</strong> — pipeline, quotes, deal management.</li>
    <li><strong>Finance &amp; Invoicing</strong> — invoices, payments, reminders.</li>
    <li><strong>Accounting</strong> — double-entry ledger, CSV bank import with AI categorisation, trial balance, PnL.</li>
    <li><strong>Projects</strong> — tasks, milestones, deliverables.</li>
    <li><strong>HR &amp; Personnel</strong> — employees, contracts, leave.</li>
    <li><strong>Operations</strong> — SOPs, workflows, escalations.</li>
    <li><strong>Marketing &amp; Content</strong> — AI-drafted captions, Outrank.so blog ingestion.</li>
    <li><strong>Communication &amp; Collaboration</strong> — channels and internal messaging.</li>
    <li><strong>Compliance &amp; Security</strong> — policies, audit trail.</li>
    <li><strong>AI Studio</strong> — photo generation (Nano Banana), video (in preview).</li>
  </ul>
</section>
`;

const assistants = `
<header>
  <p>AI assistants</p>
  <h1>Four AI specialists that already know your company.</h1>
  <p>Not a chatbot. Not a copilot. Four purpose-built AIs — each with its own personality, expertise and access to your live business data. Ask, delegate, ship.</p>
</header>
<section>
  <h2>Zyntha — Content &amp; SEO</h2>
  <p>Content strategy, content creation, SEO strategy and search optimisation. Grounded in real business context.</p>
</section>
<section>
  <h2>Thoro — Process &amp; Implementation</h2>
  <p>SOPs, automation logic and implementation architecture. Translates strategic decisions into executable process steps, sequencing, ownership and dependencies.</p>
</section>
<section>
  <h2>Zyona — Strategy</h2>
  <p>Board-level strategic guidance. Challenges assumptions, weighs trade-offs, names risks, and gives sharp prioritised advice at organisational level.</p>
</section>
<section>
  <h2>Zynthoro Assist — Platform guide</h2>
  <p>Always-on guide inside the platform. Explains how Zynthoro works, walks users through configuration and settings, and routes questions to the right specialist.</p>
</section>
`;

const pricing = `
<header>
  <p>Pricing</p>
  <h1>Simple, honest, European pricing.</h1>
  <p>Lifetime deals from €79, transparent monthly tiers, and an Enterprise plan for teams that outgrow SaaS. Cancel any subscription any time. No lock-in, no surprise seat fees.</p>
</header>
<section>
  <h2>Kickstart lifetime deals</h2>
  <ul>
    <li>Kickstart Solo — €79 lifetime</li>
    <li>Kickstart Team — €149 lifetime</li>
    <li>Kickstart Business — €199 lifetime</li>
  </ul>
</section>
<section>
  <h2>Monthly subscriptions</h2>
  <ul>
    <li>Starter — from €24.99/mo</li>
    <li>Creator — from €39.99/mo</li>
    <li>Business — from €79/mo</li>
    <li>Agency — from €149/mo</li>
    <li>Enterprise — custom</li>
  </ul>
</section>
<section>
  <h2>Enterprise</h2>
  <p>SSO, dedicated support, unlimited seats. Built for teams larger than 25 people.</p>
</section>
`;

const blogIndexShell = `
<header>
  <p>Blog</p>
  <h1>Zynthoro Blog — Insights on AI, ERP and business automation for SMEs</h1>
  <p>Latest articles from the Zynthoro team. Practical guides on AI-native ERP, workflow automation, accounting, sales and content operations for European small and medium businesses.</p>
</header>
`;

// ---------- runner -------------------------------------------------------
async function main() {
  const templatePath = path.join(BUILD_DIR, "index.html");
  if (!fs.existsSync(templatePath)) {
    console.error(`[prerender] no build/index.html found — run \`yarn build\` first.`);
    process.exit(0); // don't fail the build
  }
  const template = fs.readFileSync(templatePath, "utf8");
  console.log("[prerender] generating per-route HTML …");

  const staticRoutes = [
    {
      path: "/",
      title: "Zynthoro — The Next-Gen AI ERP Ecosystem | All-in-One Business Platform",
      description:
        "AI-native ERP for European SMEs · Kickstart lifetime deals from €79 · Starting at €24.99/mo.",
      content: home,
    },
    {
      path: "/modules",
      title: "Modules — Zynthoro | 12 AI-native ERP modules for SMEs",
      description:
        "Explore Zynthoro's 12 AI-native ERP modules — Finance, Sales, HR, Projects, Planning, Marketing, and more. One platform, one truth.",
      content: modules,
    },
    {
      path: "/assistants",
      title: "AI Assistants — Zynthoro | Zyntha · Thoro · Zyona · Zynthoro Assist",
      description:
        "Meet the four AI specialists inside Zynthoro — Zyntha for content & SEO, Thoro for workflows, Zyona for growth, and Zynthoro Assist your always-on guide.",
      content: assistants,
    },
    {
      path: "/pricing",
      title:
        "Pricing — Zynthoro | Lifetime deals from €79 · Subscriptions from €24.99/mo",
      description:
        "Zynthoro pricing — Kickstart lifetime deals from €79, monthly subscriptions from €24.99, and Enterprise plans. Compare every tier side-by-side.",
      content: pricing,
    },
    {
      path: "/blog",
      title: "Blog — Zynthoro | Insights on AI ERP for European SMEs",
      description:
        "Practical guides on AI-native ERP, workflow automation, accounting, sales and content ops for European SMEs. Latest articles from the Zynthoro team.",
      content: blogIndexShell,
    },
  ];

  for (const r of staticRoutes) {
    const url = `${BASE_URL}${r.path === "/" ? "/" : r.path}`;
    let html = applyMeta(template, {
      title: r.title,
      description: r.description,
      url,
      type: "website",
    });
    html = injectRootContent(html, r.content);
    writePage(r.path, html);
  }

  // ---- blog posts (dynamic) ---------------------------------------------
  try {
    console.log(`[prerender] fetching blog list from ${API_URL}/blog/posts …`);
    const list = await fetchJson(`${API_URL}/blog/posts?limit=200`);
    const posts = list.posts || [];
    if (!posts.length) {
      console.log("[prerender] no blog posts to prerender.");
      return;
    }

    // Update /blog index to also list every post so crawlers can discover.
    const blogListItems = posts
      .map(
        (p) =>
          `<li><a href="/blog/${esc(p.slug)}">${esc(p.title)}</a>${
            p.excerpt ? ` — ${esc(p.excerpt).slice(0, 200)}` : ""
          }</li>`
      )
      .join("\n");
    const blogListSection = `<section><h2>All articles</h2><ul>${blogListItems}</ul></section>`;
    const enrichedBlogHtml = injectRootContent(
      applyMeta(template, {
        title: "Blog — Zynthoro | Insights on AI ERP for European SMEs",
        description:
          "Practical guides on AI-native ERP, workflow automation, accounting, sales and content ops for European SMEs. Latest articles from the Zynthoro team.",
        url: `${BASE_URL}/blog`,
        type: "website",
      }),
      blogIndexShell + blogListSection
    );
    writePage("/blog", enrichedBlogHtml);

    // Individual post pages.
    for (const p of posts) {
      let post;
      try {
        post = await fetchJson(`${API_URL}/blog/posts/${p.slug}`);
      } catch (e) {
        console.warn(`  ! skip ${p.slug}: ${e.message}`);
        continue;
      }
      const title = `${post.title} — Zynthoro Blog`;
      const desc =
        post.excerpt ||
        (post.content_markdown || "").replace(/\s+/g, " ").slice(0, 160);
      const url = `${BASE_URL}/blog/${post.slug}`;
      const cover =
        post.cover_image_url || `${BASE_URL}/og-image.png`;
      const article = `
<article>
  <header>
    <p><a href="/blog">← Back to Blog</a></p>
    <h1>${esc(post.title)}</h1>
    <p>${post.published_at ? `Published ${esc(new Date(post.published_at).toDateString())}` : ""}${post.author ? ` · by ${esc(post.author)}` : ""}</p>
    ${post.cover_image_url ? `<p><img src="${esc(post.cover_image_url)}" alt="${esc(post.title)}" /></p>` : ""}
    ${post.excerpt ? `<p><em>${esc(post.excerpt)}</em></p>` : ""}
  </header>
  <div>
    ${post.content_html || ""}
  </div>
</article>
`;
      let html = applyMeta(template, {
        title,
        description: desc,
        url,
        image: cover,
        type: "article",
      });
      html = injectRootContent(html, article);
      writePage(`/blog/${post.slug}`, html);
    }
  } catch (e) {
    console.warn(
      `[prerender] blog API unreachable — skipping blog-post prerender: ${e.message}`
    );
  }

  console.log("[prerender] done.");
}

main().catch((e) => {
  // Never fail the build on prerender errors — SEO enhancement is best-effort.
  console.error("[prerender] unexpected error (non-fatal):", e);
  process.exit(0);
});
