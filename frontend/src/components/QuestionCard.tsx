import { useEffect, useRef } from "react";
import { api, type QuestionPayload } from "../api/client";

interface Props {
  question: QuestionPayload;
  autoPlayTts?: boolean;
}

export default function QuestionCard({ question, autoPlayTts = true }: Props) {
  const audioRef = useRef<HTMLAudioElement>(null);

  // Re-trigger audio whenever the question changes
  useEffect(() => {
    if (autoPlayTts && audioRef.current) {
      audioRef.current.load();
      audioRef.current.play().catch(() => {
        // Autoplay blocked by browser policy — user will see the audio controls
      });
    }
  }, [question.id, question.is_follow_up, autoPlayTts]);

  const label = question.is_follow_up ? "Follow-up question" : `Question ${question.index + 1} of ${question.total}`;

  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-4">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold uppercase tracking-wide text-brand-600">
          {label}
        </span>
        <span className="text-xs text-gray-400">
          {question.index + 1} / {question.total}
        </span>
      </div>

      <p className="text-lg font-medium leading-relaxed text-gray-800">
        {question.text}
      </p>

      {autoPlayTts && (
        <audio
          ref={audioRef}
          controls
          className="w-full h-8 mt-2"
          src={api.ttsUrl(question.text)}
        />
      )}
    </div>
  );
}
