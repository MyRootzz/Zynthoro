import { Mic, MicOff } from "lucide-react";
import { toast } from "sonner";
import { useEffect, useRef } from "react";
import { useVoiceInput } from "@/lib/useVoiceInput";

/**
 * Reusable mic button. On click:
 *  - Asks browser for mic permission
 *  - Shows pulsing red dot while recording
 *  - Streams interim transcription into `onInterim`
 *  - Calls `onFinal(text)` when the user pauses
 *
 * Falls back to a disabled state with a tooltip on unsupported browsers.
 */
export default function VoiceButton({
  onFinal,
  onInterim,
  testId = "voice-mic-btn",
  size = 15,
  className = "",
}) {
  const { supported, listening, interim, error, toggle } = useVoiceInput({
    onFinal: (text) => onFinal?.(text),
  });
  const lastInterim = useRef("");

  useEffect(() => {
    if (interim && interim !== lastInterim.current) {
      lastInterim.current = interim;
      onInterim?.(interim);
    }
    if (!interim) lastInterim.current = "";
  }, [interim, onInterim]);

  useEffect(() => {
    if (error) toast.error(error);
  }, [error]);

  if (!supported) {
    return (
      <button
        type="button"
        disabled
        title="Voice input requires Chrome or Edge"
        data-testid={`${testId}-unsupported`}
        className={`p-2 rounded-md border border-[#eee] text-[#bbb] cursor-not-allowed ${className}`}
      >
        <MicOff size={size} />
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={toggle}
      data-testid={testId}
      aria-pressed={listening}
      aria-label={listening ? "Stop voice input" : "Start voice input"}
      title={listening ? "Listening… click to stop" : "Speak your message"}
      className={`relative p-2 rounded-md border transition-colors ${
        listening
          ? "border-red-500 bg-red-50 text-red-600"
          : "border-[#eee] text-[#555] hover:border-[#1A4FFF] hover:text-[#1A4FFF]"
      } ${className}`}
    >
      <Mic size={size} />
      {listening && (
        <span
          className="absolute -top-0.5 -right-0.5 w-2.5 h-2.5 rounded-full bg-red-500 animate-pulse"
          aria-hidden="true"
        />
      )}
    </button>
  );
}
