/**
 * SSE streaming client for /api/ai/stream.
 *
 * Reads cookies (credentials: 'include') and emits frames via callbacks.
 *
 * Frame events:
 *   meta  -> { provider, model, badge, session_id, assistant }
 *   delta -> { content }
 *   error -> { message }
 *   done  -> { latency_ms, chars }
 */
import { API } from "@/contexts/AuthContext";

export async function streamAssistantChat({
  assistant,
  session_id,
  message,
  onMeta,
  onDelta,
  onError,
  onDone,
  signal,
}) {
  let res;
  try {
    res = await fetch(`${API}/ai/stream`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
      body: JSON.stringify({ assistant, session_id, message }),
      signal,
    });
  } catch (e) {
    onError?.({ message: "Connection failed. Please try again." });
    return;
  }

  if (!res.ok || !res.body) {
    onError?.({ message: `Assistant unavailable (HTTP ${res.status}).` });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder("utf-8");
  let buffer = "";

  // Each SSE frame is: "event: <name>\ndata: <json>\n\n"
  const dispatch = (rawFrame) => {
    const lines = rawFrame.split(/\n/).filter(Boolean);
    let event = "delta";
    const dataLines = [];
    for (const line of lines) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) dataLines.push(line.slice(5).trim());
    }
    if (!dataLines.length) return;
    let payload;
    try {
      payload = JSON.parse(dataLines.join("\n"));
    } catch {
      return;
    }
    if (event === "meta") onMeta?.(payload);
    else if (event === "delta") onDelta?.(payload);
    else if (event === "error") onError?.(payload);
    else if (event === "done") onDone?.(payload);
  };

  while (true) {
    let chunk;
    try {
      chunk = await reader.read();
    } catch (e) {
      onError?.({ message: "Stream interrupted." });
      return;
    }
    if (chunk.done) break;
    buffer += decoder.decode(chunk.value, { stream: true });

    // Split frames by double newline boundary
    let sep;
    while ((sep = buffer.indexOf("\n\n")) !== -1) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      if (frame.trim()) dispatch(frame);
    }
  }
  if (buffer.trim()) dispatch(buffer);
}
