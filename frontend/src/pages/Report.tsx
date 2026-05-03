import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api/client";
import ScoreCard from "../components/ScoreCard";

function ScoreStat({ label, value }: { label: string; value: number }) {
  const color =
    value >= 8 ? "text-green-600" : value >= 6 ? "text-yellow-600" : "text-red-500";
  return (
    <div className="text-center">
      <p className={`text-3xl font-bold ${color}`}>{value.toFixed(1)}</p>
      <p className="text-xs text-gray-500 mt-0.5">{label}</p>
    </div>
  );
}

const STATUS_BADGE: Record<string, { label: string; className: string }> = {
  ended_early: {
    label: "Ended early",
    className: "bg-amber-50 text-amber-700 border-amber-200",
  },
  timed_out: {
    label: "Timed out",
    className: "bg-orange-50 text-orange-700 border-orange-200",
  },
  ended_by_voice: {
    label: "Ended by voice",
    className: "bg-purple-50 text-purple-700 border-purple-200",
  },
};

export default function Report() {
  const { sessionId } = useParams<{ sessionId: string }>();

  const { data, isLoading, isError } = useQuery({
    queryKey: ["session", sessionId],
    queryFn: () => api.getSession(sessionId!),
    enabled: !!sessionId,
  });

  if (isLoading) return <p className="text-gray-400">Loading report…</p>;
  if (isError || !data)
    return (
      <p className="text-red-600 bg-red-50 rounded-lg px-4 py-3 text-sm">
        Session not found.{" "}
        <Link to="/sessions" className="underline">
          Back to history
        </Link>
      </p>
    );

  const { session, report } = data;
  const cfg = session.config;
  const scoreMap = Object.fromEntries(report.scores.map((s) => [s.question_id, s]));

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-gray-800">Interview Report</h1>
            {session.completion_status &&
              STATUS_BADGE[session.completion_status] && (
                <span
                  className={`text-xs font-medium px-2 py-0.5 rounded-full border ${
                    STATUS_BADGE[session.completion_status].className
                  }`}
                >
                  {STATUS_BADGE[session.completion_status].label}
                </span>
              )}
          </div>
          <p className="text-sm text-gray-500 mt-1 capitalize">
            {cfg.type.replace("_", " ")} · {cfg.difficulty} · {session.turns.length} question
            {session.turns.length !== 1 ? "s" : ""}
          </p>
        </div>
        <Link to="/sessions" className="text-sm text-brand-600 hover:underline">
          ← History
        </Link>
      </div>

      {/* Summary scores */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm px-6 py-6 space-y-4">
        <h2 className="font-semibold text-gray-700">Overall performance</h2>
        <div className="grid grid-cols-4 gap-4">
          <ScoreStat label="Overall" value={report.average_overall} />
          <ScoreStat label="STAR" value={report.average_star} />
          <ScoreStat label="Relevance" value={report.average_relevance} />
          <ScoreStat label="Clarity" value={report.average_clarity} />
        </div>
        {report.summary && (
          <p className="text-sm text-gray-600 bg-gray-50 rounded-lg px-4 py-3 mt-2">
            {report.summary}
          </p>
        )}
      </div>

      {/* Per-question breakdown */}
      <div className="space-y-4">
        <h2 className="font-semibold text-gray-700">Question breakdown</h2>
        {session.turns.map((turn, i) => {
          const score = scoreMap[turn.question.id];
          return (
            <div key={turn.question.id} className="space-y-2">
              {score && <ScoreCard score={score} questionNumber={i + 1} />}
              {turn.follow_up_asked && (
                <div className="ml-4 pl-4 border-l-2 border-gray-200 space-y-1">
                  <p className="text-xs text-gray-400 font-medium uppercase tracking-wide">
                    Follow-up
                  </p>
                  <p className="text-sm text-gray-600 italic">{turn.question.follow_up}</p>
                  <p className="text-sm text-gray-700">"{turn.follow_up_answer}"</p>
                </div>
              )}
            </div>
          );
        })}
      </div>

      <div className="flex gap-3">
        <Link
          to="/setup"
          className="bg-brand-600 text-white font-semibold rounded-xl px-5 py-2.5 text-sm hover:bg-brand-700 transition-colors"
        >
          Try another interview →
        </Link>
        <Link
          to="/sessions"
          className="border border-gray-200 text-gray-600 font-medium rounded-xl px-5 py-2.5 text-sm hover:bg-gray-50 transition-colors"
        >
          All sessions
        </Link>
      </div>
    </div>
  );
}
