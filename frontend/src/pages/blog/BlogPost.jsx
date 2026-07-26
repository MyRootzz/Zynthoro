import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import axios from "axios";
import { ArrowLeft, Calendar, Tag as TagIcon, Clock } from "lucide-react";
import Navbar from "@/components/layout/Navbar";
import Footer from "@/components/layout/Footer";
import { PresaleDialogProvider } from "@/components/sections/PresaleDialog";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "long",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

// Estimate read time from stripped HTML at 220 wpm.
function readTimeMinutes(html) {
  if (!html) return 1;
  const words = html.replace(/<[^>]+>/g, " ").trim().split(/\s+/).filter(Boolean).length;
  return Math.max(1, Math.round(words / 220));
}

export default function BlogPost() {
  const { slug } = useParams();
  const [post, setPost] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    window.scrollTo(0, 0);
    setPost(null);
    setError("");
    axios
      .get(`${API}/blog/posts/${slug}`)
      .then(({ data }) => {
        setPost(data);
        document.title = `${data.title} — Zynthoro`;
        // Update meta description for SEO.
        const desc = data.excerpt || (data.content_markdown || "").slice(0, 160);
        let tag = document.querySelector('meta[name="description"]');
        if (!tag) {
          tag = document.createElement("meta");
          tag.setAttribute("name", "description");
          document.head.appendChild(tag);
        }
        tag.setAttribute("content", desc);

        // Inject Article JSON-LD schema — helps Google index each post as
        // a rich result. Removed on unmount so we don't leak across posts.
        const ldTag = document.createElement("script");
        ldTag.type = "application/ld+json";
        ldTag.id = "blog-article-jsonld";
        const canonical = `${window.location.origin}/blog/${data.slug}`;
        ldTag.textContent = JSON.stringify({
          "@context": "https://schema.org",
          "@type": "Article",
          headline: data.title,
          description: desc,
          image: data.cover_image_url ? [data.cover_image_url] : undefined,
          datePublished: data.published_at,
          dateModified: data.updated_at || data.published_at,
          author: { "@type": "Organization", name: "Zynthoro" },
          publisher: {
            "@type": "Organization",
            name: "Zynthoro",
            logo: {
              "@type": "ImageObject",
              url: `${window.location.origin}/favicon.ico`,
            },
          },
          mainEntityOfPage: { "@type": "WebPage", "@id": canonical },
          url: canonical,
          keywords: Array.isArray(data.tags) ? data.tags.join(", ") : undefined,
        });
        // Remove any previous instance before appending.
        document.getElementById("blog-article-jsonld")?.remove();
        document.head.appendChild(ldTag);
      })
      .catch((e) => {
        if (e?.response?.status === 404) {
          setError("This article doesn't exist or was removed.");
          document.title = "Article not found — Zynthoro";
        } else {
          setError("Couldn't load this article. Please refresh.");
        }
      });

    return () => {
      // Cleanup: strip the JSON-LD block when navigating away.
      document.getElementById("blog-article-jsonld")?.remove();
    };
  }, [slug]);

  const readMins = post ? readTimeMinutes(post.content_html || post.content_markdown) : 0;

  return (
    <PresaleDialogProvider>
      <Navbar />

      {/* Hero */}
      <section
        style={{ background: "var(--zy-blue)" }}
        className="text-white"
        data-testid="blog-post-hero"
      >
        <div className="zy-container py-14 md:py-20 max-w-[860px]">
          <Link
            to="/blog"
            data-testid="blog-post-back"
            className="inline-flex items-center gap-1.5 text-white/70 hover:text-white text-[13px] mb-6 transition-colors"
          >
            <ArrowLeft size={14} />
            Back to blog
          </Link>

          {post ? (
            <>
              <p
                className="uppercase tracking-[0.18em] text-[12px] mb-3"
                style={{ color: "var(--zy-gold)" }}
              >
                Zynthoro · Blog
              </p>
              <h1
                data-testid="blog-post-title"
                className="text-3xl md:text-5xl font-bold tracking-tight leading-[1.15]"
              >
                {post.title}
              </h1>
              <div
                data-testid="blog-post-meta"
                className="mt-6 flex flex-wrap items-center gap-x-5 gap-y-2 text-[13.5px] text-white/75"
              >
                <span className="inline-flex items-center gap-1.5">
                  <Calendar size={14} />
                  Published {formatDate(post.published_at)}
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <Clock size={14} />
                  {readMins} min read
                </span>
                {Array.isArray(post.tags) && post.tags.length > 0 && (
                  <span className="inline-flex items-center gap-1.5">
                    <TagIcon size={14} />
                    {post.tags.slice(0, 4).join(" · ")}
                  </span>
                )}
              </div>
            </>
          ) : (
            <div className="animate-pulse">
              <div className="h-3 w-32 bg-white/20 rounded mb-4" />
              <div className="h-10 w-3/4 bg-white/20 rounded mb-3" />
              <div className="h-10 w-1/2 bg-white/20 rounded" />
            </div>
          )}
        </div>
      </section>

      {/* Body */}
      <section className="bg-white">
        <div className="zy-container py-12 md:py-16 max-w-[860px]">
          {error && (
            <div
              data-testid="blog-post-error"
              className="rounded-lg border border-red-200 bg-red-50 text-red-800 px-4 py-3 text-[14px]"
            >
              {error}
              <div className="mt-3">
                <Link
                  to="/blog"
                  className="text-[var(--zy-blue)] font-semibold text-[14px] inline-flex items-center gap-1.5"
                >
                  <ArrowLeft size={14} /> Back to all articles
                </Link>
              </div>
            </div>
          )}

          {!error && !post && (
            <div data-testid="blog-post-loading" className="animate-pulse space-y-4">
              <div className="h-4 w-full bg-black/[0.06] rounded" />
              <div className="h-4 w-11/12 bg-black/[0.06] rounded" />
              <div className="h-4 w-10/12 bg-black/[0.06] rounded" />
              <div className="h-4 w-9/12 bg-black/[0.06] rounded" />
            </div>
          )}

          {post && (
            <>
              {post.cover_image_url && (
                <img
                  src={post.cover_image_url}
                  alt={post.title}
                  data-testid="blog-post-cover"
                  className="w-full rounded-2xl mb-10 shadow-[0_25px_60px_-30px_rgba(10,22,40,0.45)]"
                  style={{ aspectRatio: "16 / 9", objectFit: "cover" }}
                />
              )}

              <article
                data-testid="blog-post-content"
                className="blog-prose"
                dangerouslySetInnerHTML={{ __html: post.content_html || "" }}
              />

              <div className="mt-14 pt-8 border-t border-black/[0.08] flex items-center justify-between text-[13.5px]">
                <Link
                  to="/blog"
                  className="inline-flex items-center gap-1.5 text-[var(--zy-blue)] font-semibold hover:underline"
                >
                  <ArrowLeft size={14} /> All articles
                </Link>
                <span className="text-black/45">
                  Last updated {formatDate(post.updated_at)}
                </span>
              </div>
            </>
          )}
        </div>
      </section>

      <Footer />
    </PresaleDialogProvider>
  );
}
