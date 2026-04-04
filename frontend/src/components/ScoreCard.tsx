import type { AnswerScore } from "../api/client";

interface Props {
  score: AnswerScore;
  questionNumber: number;
}

function ScoreBar({ label, value }: { label: string; value: number }) {
  const pct = (value / 10) * 100;
  const color =
    value >= 8 ? "bg-green-500" : value >= 6 ? "bg-yellow-500" : "bg-red-400";
  return (
    <div className="space-y-0.5">
      <div className="flex justify-between text-xs text-gray-500">
        <span>{label}</span>
        <span className="font-medium text-gray-700">{value}/10</span>
      </div>
      <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
        <div
          className={`h-full rounded-full ${color} transition-all`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}

export default function ScoreCard({ score, questionNumber }: Props) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-5 space-y-4">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-gray-400">
            Q{questionNumber}
          </p>
          <p className="font-medium text-gray-800 mt-0.5">{score.question_text}</p>
        </div>
        <div className="shrink-0 text-center">
          <p className="text-2xl font-bold text-brand-600">
            {score.overall.toFixed(1)}
          </p>
          <p className="text-xs text-gray-400">/ 10</p>
        </div>
      </div>

      <blockquote className="text-sm text-gray-600 bg-gray-50 rounded-lg px-4 py-3 italic border-l-2 border-gray-200">
        {score.answer}
      </blockquote>

      <div className="grid grid-cols-3 gap-3">
        <ScoreBar label="STAR" value={score.star_score} />
        <ScoreBar label="Relevance" value={score.relevance_score} />
        <ScoreBar label="Clarity" value={score.clarity_score} />
      </div>

      <p className="text-sm text-gray-700 bg-blue-50 rounded-lg px-4 py-3">
        <span className="font-medium text-blue-700">Feedback: </span>
        {score.feedback}
      </p>
    </div>
  );
}
