import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { ArrowRight, Calendar, Tag as TagIcon } from "lucide-react";
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

function PostCard({ post }) {
  return (
    <Link
      to={`/blog/${post.slug}`}
      data-testid={`blog-card-${post.slug}`}
      className="group flex flex-col rounded-2xl overflow-hidden bg-white ring-1 ring-black/[0.06] hover:ring-[var(--zy-blue)]/40 shadow-sm hover:shadow-xl transition-all duration-300"
    >
      <div
        className="relative overflow-hidden bg-[#F1F3F8]"
        style={{ aspectRatio: "16 / 9" }}
      >
        {post.cover_image_url ? (
          <img
            src={post.cover_image_url}
            alt={post.title}
            loading="lazy"
            className="absolute inset-0 w-full h-full object-cover transition-transform duration-500 group-hover:scale-[1.04]"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center text-[12px] font-semibold uppercase tracking-[0.18em] text-black/25">
            Zynthoro Blog
          </div>
        )}
      </div>
      <div className="p-6 flex flex-col flex-1">
        <div className="flex items-center gap-3 text-[12px] text-black/50 mb-3">
          <span className="inline-flex items-center gap-1.5">
            <Calendar size={13} />
            {formatDate(post.published_at)}
          </span>
          {Array.isArray(post.tags) && post.tags.length > 0 && (
            <span className="inline-flex items-center gap-1.5 truncate">
              <TagIcon size={13} />
              <span className="truncate">{post.tags.slice(0, 3).join(" · ")}</span>
            </span>
          )}
        </div>
        <h3 className="text-[19px] leading-tight font-bold text-[#0A1628] group-hover:text-[var(--zy-blue)] transition-colors">
          {post.title}
        </h3>
        {post.excerpt && (
          <p className="mt-3 text-[14px] text-black/60 leading-relaxed line-clamp-3">
            {post.excerpt}
          </p>
        )}
        <div className="mt-5 pt-4 border-t border-black/[0.06] flex items-center gap-1.5 text-[13px] font-semibold text-[var(--zy-blue)]">
          Read article
          <ArrowRight
            size={14}
            className="transition-transform duration-300 group-hover:translate-x-1"
          />
        </div>
      </div>
    </Link>
  );
}

export default function BlogIndex() {
  const [posts, setPosts] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    document.title = "Blog — Zynthoro";
    window.scrollTo(0, 0);
    axios
      .get(`${API}/blog/posts?limit=50`)
      .then(({ data }) => setPosts(data.posts || []))
      .catch(() => setError("Couldn't load posts. Please refresh."));
  }, []);

  return (
    <PresaleDialogProvider>
      <Navbar />

      {/* Hero */}
      <section
        style={{ background: "var(--zy-blue)" }}
        className="text-white"
        data-testid="blog-index-hero"
      >
        <div className="zy-container py-14 md:py-20">
          <p
            className="uppercase tracking-[0.18em] text-[12px] mb-3"
            style={{ color: "var(--zy-gold)" }}
          >
            Zynthoro · Blog
          </p>
          <h1 className="text-3xl md:text-5xl font-bold tracking-tight">
            Insights on AI-native ERP for SMEs
          </h1>
          <p className="mt-5 text-white/75 text-[15.5px] max-w-2xl leading-relaxed">
            Product notes, launch updates, and playbooks on running a
            European SME with a single AI-native platform.
          </p>
        </div>
      </section>

      {/* Body */}
      <section className="bg-[#FAFBFD]">
        <div className="zy-container py-14 md:py-20">
          {error && (
            <div
              data-testid="blog-index-error"
              className="max-w-xl rounded-lg border border-red-200 bg-red-50 text-red-800 px-4 py-3 text-[14px]"
            >
              {error}
            </div>
          )}

          {!error && posts === null && (
            <div
              data-testid="blog-index-loading"
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
            >
              {Array.from({ length: 6 }).map((_, i) => (
                <div
                  key={i}
                  className="rounded-2xl bg-white ring-1 ring-black/[0.06] overflow-hidden"
                >
                  <div className="bg-[#F1F3F8]" style={{ aspectRatio: "16 / 9" }} />
                  <div className="p-6 space-y-3">
                    <div className="h-3 w-24 bg-black/[0.06] rounded" />
                    <div className="h-5 w-3/4 bg-black/[0.08] rounded" />
                    <div className="h-4 w-full bg-black/[0.05] rounded" />
                    <div className="h-4 w-5/6 bg-black/[0.05] rounded" />
                  </div>
                </div>
              ))}
            </div>
          )}

          {!error && posts !== null && posts.length === 0 && (
            <div
              data-testid="blog-index-empty"
              className="max-w-xl rounded-2xl border border-dashed border-black/15 bg-white p-8 text-center"
            >
              <p className="text-[15px] text-black/70">
                No articles yet — check back soon.
              </p>
            </div>
          )}

          {posts && posts.length > 0 && (
            <div
              data-testid="blog-index-grid"
              className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
            >
              {posts.map((p) => (
                <PostCard key={p.id} post={p} />
              ))}
            </div>
          )}
        </div>
      </section>

      <Footer />
    </PresaleDialogProvider>
  );
}
