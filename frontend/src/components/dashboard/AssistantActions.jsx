import { useState } from "react";
import { Copy, Download, Check } from "lucide-react";
import { stripMarkdown, downloadAssistantPdf } from "@/lib/aiExport";

/**
 * Action row that sits under every assistant message.
 *
 * Provides:
 *   - Copy (plain text, no markdown symbols)
 *   - Download PDF (Zynthoro-branded, blue accents, white background)
 */
export default function AssistantActions({ content, assistantName, testIdPrefix = "assist-msg" }) {
  const [copied, setCopied] = useState(false);

  const handleCopy = async () => {
    const clean = stripMarkdown(content);
    try {
      await navigator.clipboard.writeText(clean);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    } catch {
      // Fallback for browsers without clipboard API
      const ta = document.createElement("textarea");
      ta.value = clean;
      document.body.appendChild(ta);
      ta.select();
      try { document.execCommand("copy"); } catch { /* ignored */ }
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 1400);
    }
  };

  const handleDownload = () => {
    downloadAssistantPdf({ assistantName, content });
  };

  return (
    <div className="flex items-center gap-1.5 mt-1.5">
      <button
        type="button"
        onClick={handleCopy}
        data-testid={`${testIdPrefix}-copy`}
        aria-label="Copy message"
        className="inline-flex items-center gap-1 text-[11px] font-medium text-[#555] hover:text-[#1A4FFF] px-2 py-1 rounded-md border border-[#eee] hover:border-[#1A4FFF] bg-white transition-colors"
      >
        {copied ? <Check size={12} /> : <Copy size={12} />}
        {copied ? "Copied" : "Copy"}
      </button>
      <button
        type="button"
        onClick={handleDownload}
        data-testid={`${testIdPrefix}-pdf`}
        aria-label="Download as PDF"
        className="inline-flex items-center gap-1 text-[11px] font-medium text-[#555] hover:text-[#1A4FFF] px-2 py-1 rounded-md border border-[#eee] hover:border-[#1A4FFF] bg-white transition-colors"
      >
        <Download size={12} />
        Download PDF
      </button>
    </div>
  );
}
