import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import PlanCard from "../components/PlanCard";
import type { PlanMeta } from "../api/client";

const SWE_PLAN: PlanMeta = {
  id: "swe_technical_senior",
  title: "Swe Technical Senior",
  interview_type: "technical",
  difficulty: "senior",
  num_questions: 5,
  summary: "Standard senior SWE technical plan covering system design and algorithms.",
};

const PM_PLAN: PlanMeta = {
  id: "pm_behavioral_mid",
  title: "Pm Behavioral Mid",
  interview_type: "behavioral",
  difficulty: "mid",
  num_questions: 5,
  summary: "Standard mid-level PM behavioral plan.",
};

describe("PlanCard", () => {
  it("renders the plan title", () => {
    render(<PlanCard plan={SWE_PLAN} selected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("Swe Technical Senior")).toBeInTheDocument();
  });

  it("renders interview type and question count", () => {
    render(<PlanCard plan={SWE_PLAN} selected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("Technical")).toBeInTheDocument();
    expect(screen.getByText(/5 questions/i)).toBeInTheDocument();
  });

  it("renders difficulty badge", () => {
    render(<PlanCard plan={SWE_PLAN} selected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("senior")).toBeInTheDocument();
  });

  it("renders summary text", () => {
    render(<PlanCard plan={SWE_PLAN} selected={false} onSelect={vi.fn()} />);
    expect(screen.getByText(/system design and algorithms/i)).toBeInTheDocument();
  });

  it("does not show selected indicator when not selected", () => {
    render(<PlanCard plan={SWE_PLAN} selected={false} onSelect={vi.fn()} />);
    expect(screen.queryByText(/selected/i)).not.toBeInTheDocument();
  });

  it("shows selected indicator when selected", () => {
    render(<PlanCard plan={SWE_PLAN} selected={true} onSelect={vi.fn()} />);
    expect(screen.getByText(/selected/i)).toBeInTheDocument();
  });

  it("calls onSelect when clicked", async () => {
    const onSelect = vi.fn();
    render(<PlanCard plan={SWE_PLAN} selected={false} onSelect={onSelect} />);
    await userEvent.click(screen.getByRole("button"));
    expect(onSelect).toHaveBeenCalledOnce();
  });

  it("renders correctly for a behavioral plan", () => {
    render(<PlanCard plan={PM_PLAN} selected={false} onSelect={vi.fn()} />);
    expect(screen.getByText("Behavioral")).toBeInTheDocument();
    expect(screen.getByText("mid")).toBeInTheDocument();
  });

  it("applies selected border style when selected", () => {
    const { container } = render(
      <PlanCard plan={SWE_PLAN} selected={true} onSelect={vi.fn()} />
    );
    const button = container.querySelector("button");
    expect(button?.className).toMatch(/border-brand-600/);
  });

  it("does not apply selected border style when not selected", () => {
    const { container } = render(
      <PlanCard plan={SWE_PLAN} selected={false} onSelect={vi.fn()} />
    );
    const button = container.querySelector("button");
    expect(button?.className).not.toMatch(/border-brand-600/);
  });
});
