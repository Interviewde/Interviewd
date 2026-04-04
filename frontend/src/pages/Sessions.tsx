import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
import SessionsTable from "../components/SessionsTable";

export default function Sessions() {
  const { data: sessions = [], isLoading, isError } = useQuery({
    queryKey: ["sessions"],
    queryFn: api.listSessions,
  });

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Interview History</h1>
        <p className="text-gray-500 mt-1 text-sm">
          {sessions.length} session{sessions.length !== 1 ? "s" : ""} on record
        </p>
      </div>

      {isLoading && <p className="text-gray-400 text-sm">Loading…</p>}
      {isError && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
          Failed to load sessions. Is the server running?
        </p>
      )}
      {!isLoading && <SessionsTable rows={sessions} />}
    </div>
  );
}
