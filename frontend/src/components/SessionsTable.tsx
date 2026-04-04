import { Link } from "react-router-dom";
import type { SessionRow } from "../api/client";

interface Props {
  rows: SessionRow[];
}

function badge(type: string) {
  const map: Record<string, string> = {
    behavioral: "bg-purple-100 text-purple-700",
    technical: "bg-blue-100 text-blue-700",
    hr: "bg-green-100 text-green-700",
    system_design: "bg-orange-100 text-orange-700",
  };
  return map[type] ?? "bg-gray-100 text-gray-600";
}

function scoreColor(avg: number | null) {
  if (avg === null) return "text-gray-400";
  if (avg >= 8) return "text-green-600 font-semibold";
  if (avg >= 6) return "text-yellow-600 font-semibold";
  return "text-red-500 font-semibold";
}

export default function SessionsTable({ rows }: Props) {
  if (rows.length === 0) {
    return (
      <div className="text-center py-16 text-gray-400">
        <p className="text-4xl mb-3">🎤</p>
        <p className="font-medium">No sessions yet</p>
        <p className="text-sm mt-1">
          <Link to="/setup" className="text-brand-600 hover:underline">
            Start your first interview
          </Link>
        </p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-xl border border-gray-200 shadow-sm">
      <table className="min-w-full text-sm">
        <thead className="bg-gray-50 border-b border-gray-200">
          <tr>
            <th className="text-left px-4 py-3 font-semibold text-gray-600">Type</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600">Difficulty</th>
            <th className="text-right px-4 py-3 font-semibold text-gray-600">Score</th>
            <th className="text-left px-4 py-3 font-semibold text-gray-600">Date</th>
            <th className="px-4 py-3" />
          </tr>
        </thead>
        <tbody className="divide-y divide-gray-100 bg-white">
          {rows.map((row) => (
            <tr key={row.id} className="hover:bg-gray-50 transition-colors">
              <td className="px-4 py-3">
                <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium ${badge(row.interview_type)}`}>
                  {row.interview_type}
                </span>
              </td>
              <td className="px-4 py-3 text-gray-600 capitalize">{row.difficulty}</td>
              <td className={`px-4 py-3 text-right ${scoreColor(row.avg_overall)}`}>
                {row.avg_overall !== null ? row.avg_overall.toFixed(1) : "—"}
              </td>
              <td className="px-4 py-3 text-gray-500">
                {row.created_at.slice(0, 10)}
              </td>
              <td className="px-4 py-3 text-right">
                <Link
                  to={`/report/${row.id}`}
                  className="text-brand-600 hover:underline text-xs font-medium"
                >
                  View report →
                </Link>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
