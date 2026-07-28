/**
 * MarkdownMessage — renders assistant chat output through react-markdown
 * with GFM extensions (tables, task lists, strikethrough) so **bold**,
 * `code`, ordered/unordered lists, links and horizontal rules display as
 * intended instead of leaking their raw markdown characters into the UI.
 *
 * Only used for `role === "assistant"` messages — user-typed messages
 * stay as plain whitespace-preserved text so that a user pasting a snippet
 * of markdown sees it back verbatim.
 */
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

// Tailwind-friendly base styles for the rendered nodes. We deliberately
// don't pull in @tailwindcss/typography — a small, targeted stylesheet
// keeps the bubble tight and consistent with the surrounding chat UI.
const P = (props) => <p {...props} className="mb-2 last:mb-0" />;
const UL = (props) => <ul {...props} className="list-disc pl-5 space-y-1 mb-2 last:mb-0" />;
const OL = (props) => <ol {...props} className="list-decimal pl-5 space-y-1 mb-2 last:mb-0" />;
const LI = (props) => <li {...props} className="leading-relaxed" />;
const H1 = (props) => <h1 {...props} className="text-[16px] font-semibold mt-2 mb-1.5" />;
const H2 = (props) => <h2 {...props} className="text-[15px] font-semibold mt-2 mb-1.5" />;
const H3 = (props) => <h3 {...props} className="text-[14px] font-semibold mt-2 mb-1" />;
const HR = (props) => <hr {...props} className="my-3 border-t border-[#0A162820]" />;
const BLOCKQUOTE = (props) => (
  <blockquote {...props} className="border-l-[3px] border-[#0A162833] pl-3 my-2 text-[#0A1628]/75 italic" />
);
const CODE = ({ inline, children, ...props }) =>
  inline ? (
    <code {...props} className="px-1 py-0.5 rounded bg-[#0A162812] text-[13px] font-mono">
      {children}
    </code>
  ) : (
    <code {...props} className="block whitespace-pre-wrap p-3 my-2 rounded-md bg-[#0A162808] text-[13px] font-mono overflow-x-auto">
      {children}
    </code>
  );
const PRE = ({ children }) => <>{children}</>; // <code> handles its own wrapper
const A = (props) => (
  <a
    {...props}
    className="text-[var(--zy-blue)] underline hover:no-underline"
    target={props.href?.startsWith("http") ? "_blank" : undefined}
    rel={props.href?.startsWith("http") ? "noopener noreferrer" : undefined}
  />
);
const TABLE = (props) => (
  <div className="overflow-x-auto my-2">
    <table {...props} className="w-full border-collapse text-[13px]" />
  </div>
);
const TH = (props) => <th {...props} className="text-left border-b border-[#0A162833] px-2 py-1 font-semibold" />;
const TD = (props) => <td {...props} className="border-b border-[#0A162814] px-2 py-1 align-top" />;

const COMPONENTS = {
  p: P, ul: UL, ol: OL, li: LI,
  h1: H1, h2: H2, h3: H3, h4: H3, h5: H3, h6: H3,
  hr: HR, blockquote: BLOCKQUOTE,
  code: CODE, pre: PRE,
  a: A,
  table: TABLE, th: TH, td: TD,
};

export default function MarkdownMessage({ children }) {
  return (
    <div className="markdown-message">
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={COMPONENTS}>
        {children || ""}
      </ReactMarkdown>
    </div>
  );
}
