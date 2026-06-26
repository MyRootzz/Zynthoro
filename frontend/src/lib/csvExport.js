/**
 * Tiny CSV exporter.
 *
 * Builds a CSV string from an array of objects and triggers a browser download.
 * Values are RFC-4180 escaped: doubled quotes + wrapped if they contain a comma,
 * newline or quote.
 */
function escapeCell(value) {
  if (value === null || value === undefined) return "";
  let s = typeof value === "string" ? value : String(value);
  if (/[",\n\r]/.test(s)) {
    s = `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

export function rowsToCsv(rows, columns) {
  const header = columns.map((c) => escapeCell(c.label)).join(",");
  const body = rows
    .map((row) =>
      columns
        .map((c) => escapeCell(typeof c.value === "function" ? c.value(row) : row[c.key]))
        .join(",")
    )
    .join("\r\n");
  return `${header}\r\n${body}`;
}

export function downloadCsv(filename, rows, columns) {
  const csv = rowsToCsv(rows, columns);
  // Prefix BOM so Excel correctly detects UTF-8 (€, é, ç, …).
  const blob = new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 1500);
}

export function todayStamp() {
  const d = new Date();
  return `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, "0")}${String(d.getDate()).padStart(2, "0")}`;
}
