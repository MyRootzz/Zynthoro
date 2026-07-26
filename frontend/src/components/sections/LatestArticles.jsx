import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import axios from "axios";
import { ArrowRight, Calendar } from "lucide-react";

const API = `${process.env.REACT_APP_BACKEND_URL}/api`;

function formatDate(iso) {
  if (!iso) return "";
  try {
    return new Date(iso).toLocaleDateString("en-GB", {
      day: "numeric",
      month: "short",
      year: "numeric",
    });
  } catch {
    return iso;
  }
}

function ArticleCard({ post }) {
  return (
    <Link
      to={`/blog/${post.slug}`}
      data-testid={`home-article-${post.slug}`}
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
          <div className="absolute inset-0 flex items-center justify-center text-[11px] font-semibold uppercase tracking-[0.18em] text-black/25">
            Zynthoro Blog
          </div>
        )}
      </div>
      <div className="p-5 flex flex-col flex-1">
        <div className="flex items-center gap-1.5 text-[11.5px] text-black/50 mb-2">
          <Calendar size={12} />
          {formatDate(post.published_at)}
        </div>
        <h3 className="text-[17px] leading-tight font-bold text-[#0A1628] group-hover:text-[var(--zy-blue)] transition-colors line-clamp-2">
          {post.title}
        </h3>
        {post.excerpt && (
          <p className="mt-2.5 text-[13.5px] text-black/60 leading-relaxed line-clamp-3">
            {post.excerpt}
          </p>
        )}
        <span className="mt-4 inline-flex items-center gap-1 text-[12.5px] font-semibold text-[var(--zy-blue)]">
          Read article
          <ArrowRight
            size={13}
            className="transition-transform duration-300 group-hover:translate-x-1"
          />
        </span>
      </div>
    </Link>
  );
}

export default function LatestArticles() {
  const [posts, setPosts] = useState(null);

  useEffect(() => {
    axios
      .get(`${API}/blog/posts?limit=3`)
      .then(({ data }) => setPosts(data.posts || []))
      .catch(() => setPosts([]));
  }, []);

  // Don't render the section on the homepage until we know we have posts —
  // an empty "Latest articles" strip would look broken.
  if (!posts || posts.length === 0) return null;

  return (
    <section
      id="latest-articles"
      data-testid="home-latest-articles"
      className="bg-white"
      style={{ paddingTop: 96, paddingBottom: 96 }}
    >
      <div className="zy-container">
        <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-4 mb-10">
          <div>
            <p className="zy-eyebrow">From the blog</p>
            <h2 className="zy-h2 mt-3">Latest articles</h2>
            <p className="text-[15px] text-[#555] mt-3 max-w-xl leading-relaxed">
              Product updates, launch notes and SME playbooks from the Zynthoro team.
            </p>
          </div>
          <Link
            to="/blog"
            data-testid="home-latest-articles-view-all"
            className="inline-flex items-center gap-1.5 text-[13.5px] font-semibold text-[var(--zy-blue)] hover:underline"
          >
            View all articles <ArrowRight size={14} />
          </Link>
        </div>

        <div
          className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6"
          data-testid="home-latest-articles-grid"
        >
          {posts.map((p) => (
            <ArticleCard key={p.id} post={p} />
          ))}
        </div>
      </div>
    </section>
  );
}
