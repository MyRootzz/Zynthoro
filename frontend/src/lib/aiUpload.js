/**
 * Upload a file to /api/ai/upload for use as AI assistant context.
 *
 * Client-side validation mirrors the server:
 *   - Extension in {pdf, docx, xlsx, pptx, csv}
 *   - Size <= 10 MB
 *
 * Returns the server response `{ file_id, filename, size, mime, chars_extracted, truncated, preview }`
 * or throws an Error with a user-friendly message.
 */
import axios from "axios";
import { API } from "@/contexts/AuthContext";

export const AI_UPLOAD_MAX_BYTES = 10 * 1024 * 1024;
export const AI_UPLOAD_ALLOWED_EXTS = [".pdf", ".docx", ".xlsx", ".pptx", ".csv"];
export const AI_UPLOAD_ACCEPT_ATTR =
  ".pdf,.docx,.xlsx,.pptx,.csv,application/pdf," +
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document," +
  "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet," +
  "application/vnd.openxmlformats-officedocument.presentationml.presentation," +
  "text/csv";

export function validateUpload(file) {
  if (!file) return "No file selected.";
  const name = (file.name || "").toLowerCase();
  const ext = name.slice(name.lastIndexOf("."));
  if (!AI_UPLOAD_ALLOWED_EXTS.includes(ext)) {
    return "Only PDF, DOCX, XLSX, PPTX or CSV files are supported.";
  }
  if (file.size > AI_UPLOAD_MAX_BYTES) {
    return "File is too large. Maximum size is 10 MB.";
  }
  if (file.size === 0) return "File appears to be empty.";
  return null;
}

export async function uploadAiFile(file) {
  const err = validateUpload(file);
  if (err) throw new Error(err);
  const form = new FormData();
  form.append("file", file);
  const { data } = await axios.post(`${API}/ai/upload`, form, {
    // Let the browser set the multipart boundary
    headers: { "Content-Type": "multipart/form-data" },
    withCredentials: true,
  });
  return data;
}

export async function deleteAiFile(fileId) {
  await axios.delete(`${API}/ai/upload/${fileId}`, { withCredentials: true });
}

export function formatBytes(bytes) {
  if (bytes == null) return "";
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
  return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
}
