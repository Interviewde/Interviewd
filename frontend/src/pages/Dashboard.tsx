import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import SessionsTable from "../components/SessionsTable";

export default function Dashboard() {
  const { data: sessions = [], isLoading } = useQuery({
    queryKey: ["sessions"],
    queryFn: api.listSessions,
  });

  const avgScore =
    sessions.length > 0
      ? (
          sessions
            .filter((s) => s.avg_overall !== null)
            .reduce((sum, s) => sum + (s.avg_overall ?? 0), 0) /
          sessions.filter((s) => s.avg_overall !== null).length
        ).toFixed(1)
      : null;

  return (
    <div className="space-y-8">
      {/* Hero */}
      <div className="bg-gradient-to-br from-brand-600 to-brand-700 rounded-2xl px-8 py-10 text-white shadow">
        <h1 className="text-3xl font-bold">Ready to practise?</h1>
        <p className="mt-2 text-brand-100 max-w-md">
          Pick an interview type, answer questions with your voice, and get
          instant AI feedback.
        </p>
        <div className="mt-6 flex gap-3">
          <Link
            to="/setup"
            className="inline-block bg-white text-brand-700 font-semibold rounded-lg px-5 py-2.5 text-sm hover:bg-brand-50 transition-colors"
          >
            Start preset interview →
          </Link>
          <Link
            to="/setup?tab=plan"
            className="inline-block bg-brand-500 text-white font-semibold rounded-lg px-5 py-2.5 text-sm hover:bg-brand-400 transition-colors"
          >
            Plan interview →
          </Link>
          <Link
            to="/practice"
            className="inline-block bg-brand-700 text-white font-semibold rounded-lg px-5 py-2.5 text-sm hover:bg-brand-800 transition-colors"
          >
            Practice questions →
          </Link>
        </div>
      </div>

      {/* Stats row */}
      {sessions.length > 0 && (
        <div className="grid grid-cols-3 gap-4">
          <Stat label="Total sessions" value={String(sessions.length)} />
          <Stat label="Avg overall score" value={avgScore ? `${avgScore}/10` : "—"} />
          <Stat
            label="Last session"
            value={sessions[0]?.created_at.slice(0, 10) ?? "—"}
          />
        </div>
      )}

      {/* Recent sessions */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-gray-800">Recent sessions</h2>
          {sessions.length > 5 && (
            <Link to="/sessions" className="text-sm text-brand-600 hover:underline">
              View all →
            </Link>
          )}
        </div>
        {isLoading ? (
          <p className="text-gray-400 text-sm">Loading…</p>
        ) : (
          <SessionsTable rows={sessions.slice(0, 5)} />
        )}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="bg-white rounded-xl border border-gray-200 shadow-sm px-5 py-4">
      <p className="text-xs text-gray-500 uppercase tracking-wide font-medium">{label}</p>
      <p className="text-2xl font-bold text-gray-800 mt-1">{value}</p>
    </div>
  );
}
