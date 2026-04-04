import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { MemoryRouter } from "react-router-dom";
import SessionsTable from "../components/SessionsTable";
import type { SessionRow } from "../api/client";

const ROWS: SessionRow[] = [
  {
    id: "aaaaaaaa-0000-0000-0000-000000000001",
    created_at: "2026-04-04T10:00:00",
    interview_type: "behavioral",
    difficulty: "mid",
    avg_overall: 7.5,
  },
  {
    id: "aaaaaaaa-0000-0000-0000-000000000002",
    created_at: "2026-04-03T09:00:00",
    interview_type: "technical",
    difficulty: "senior",
    avg_overall: null,
  },
];

function wrap(ui: React.ReactElement) {
  return render(<MemoryRouter>{ui}</MemoryRouter>);
}

describe("SessionsTable", () => {
  it("shows empty state with link when no rows", () => {
    wrap(<SessionsTable rows={[]} />);
    expect(screen.getByText(/no sessions yet/i)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /start your first interview/i })).toBeInTheDocument();
  });

  it("renders a row for each session", () => {
    wrap(<SessionsTable rows={ROWS} />);
    expect(screen.getAllByRole("row")).toHaveLength(ROWS.length + 1); // +1 header
  });

  it("displays interview type badges", () => {
    wrap(<SessionsTable rows={ROWS} />);
    expect(screen.getByText("behavioral")).toBeInTheDocument();
    expect(screen.getByText("technical")).toBeInTheDocument();
  });

  it("shows score when present", () => {
    wrap(<SessionsTable rows={ROWS} />);
    expect(screen.getByText("7.5")).toBeInTheDocument();
  });

  it("shows dash when score is null", () => {
    wrap(<SessionsTable rows={ROWS} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it("renders a 'View report' link per row", () => {
    wrap(<SessionsTable rows={ROWS} />);
    const links = screen.getAllByRole("link", { name: /view report/i });
    expect(links).toHaveLength(ROWS.length);
  });
});
