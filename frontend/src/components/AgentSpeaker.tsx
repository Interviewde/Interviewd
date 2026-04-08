import { useEffect, useRef } from "react";
import { api } from "../api/client";

interface Props {
  /** Text to speak. Changing this value re-triggers TTS playback. */
  text: string;
  label?: string;
}

/**
 * Renders the agent's voice for any utterance — questions, follow-ups,
 * clarification responses, coaching feedback, etc.
 *
 * Auto-plays TTS whenever `text` changes and shows audio controls so the
 * user can replay if needed.
 */
export default function AgentSpeaker({ text, label = "Interviewer" }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);

  useEffect(() => {
    if (audioRef.current && text) {
      audioRef.current.load();
      audioRef.current.play().catch(() => {
        // Autoplay may be blocked on first interaction — controls are shown as fallback.
      });
    }
  }, [text]);

  if (!text) return null;

  return (
    <div className="bg-brand-50 border border-brand-100 rounded-xl px-4 py-3 space-y-2">
      <span className="text-xs font-semibold uppercase tracking-wide text-brand-600">
        {label}
      </span>
      <audio
        ref={audioRef}
        controls
        className="w-full h-8"
        src={api.ttsUrl(text)}
      />
    </div>
  );
}
