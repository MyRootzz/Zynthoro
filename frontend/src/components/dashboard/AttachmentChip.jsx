/**
 * Small chip UI for an uploaded / uploading AI assistant attachment.
 * Used above the composer AND inside the user message bubble after send.
 */
import { FileText, FileSpreadsheet, Presentation, X, Loader2, AlertCircle } from "lucide-react";
import { formatBytes } from "@/lib/aiUpload";

function iconFor(filename) {
  const n = (filename || "").toLowerCase();
  if (n.endsWith(".xlsx") || n.endsWith(".csv")) return FileSpreadsheet;
  if (n.endsWith(".pptx")) return Presentation;
  return FileText; // pdf, docx, default
}

/**
 * @param {{
 *   filename: string,
 *   size?: number,
 *   status?: "uploading"|"ready"|"error",
 *   onRemove?: () => void,
 *   compact?: boolean,   // true when rendered inside a message bubble
 *   testId?: string,
 * }} props
 */
export default function AttachmentChip({
  filename,
  size,
  status = "ready",
  onRemove,
  compact = false,
  testId,
}) {
  const Icon = iconFor(filename);
  const base = compact
    ? "inline-flex items-center gap-1.5 text-[12px] px-2 py-1 rounded-md bg-white/15 text-white border border-white/25"
    : "inline-flex items-center gap-2 text-[12.5px] px-2.5 py-1.5 rounded-full bg-[#F4F6FB] border border-[#e2e6ef] text-[#333]";

  return (
    <span className={base} data-testid={testId}>
      {status === "uploading" ? (
        <Loader2 size={13} className="animate-spin shrink-0" />
      ) : status === "error" ? (
        <AlertCircle size={13} className="shrink-0 text-red-500" />
      ) : (
        <Icon size={13} className="shrink-0" />
      )}
      <span className="truncate max-w-[220px]" title={filename}>{filename}</span>
      {!compact && size != null && (
        <span className="text-[11px] text-[#888]">{formatBytes(size)}</span>
      )}
      {onRemove && status !== "uploading" && (
        <button
          type="button"
          onClick={onRemove}
          className={compact
            ? "ml-0.5 opacity-80 hover:opacity-100"
            : "ml-0.5 opacity-60 hover:opacity-100 text-[#666]"}
          aria-label={`Remove ${filename}`}
          data-testid={testId ? `${testId}-remove` : undefined}
        >
          <X size={12} />
        </button>
      )}
    </span>
  );
}
