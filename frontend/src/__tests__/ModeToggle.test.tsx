import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import ModeToggle from "../components/ModeToggle";

describe("ModeToggle", () => {
  it("renders both Pipeline and Live buttons", () => {
    render(<ModeToggle value="pipeline" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /pipeline/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /live/i })).toBeInTheDocument();
  });

  it("Live button is disabled", () => {
    render(<ModeToggle value="pipeline" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /live/i })).toBeDisabled();
  });

  it("Pipeline button is not disabled", () => {
    render(<ModeToggle value="pipeline" onChange={vi.fn()} />);
    expect(screen.getByRole("button", { name: /pipeline/i })).not.toBeDisabled();
  });

  it("calls onChange with 'pipeline' when Pipeline is clicked", async () => {
    const onChange = vi.fn();
    render(<ModeToggle value="pipeline" onChange={onChange} />);
    await userEvent.click(screen.getByRole("button", { name: /pipeline/i }));
    expect(onChange).toHaveBeenCalledWith("pipeline");
  });

  it("shows pipeline description text", () => {
    render(<ModeToggle value="pipeline" onChange={vi.fn()} />);
    expect(screen.getByText(/STT.*LLM.*TTS/i)).toBeInTheDocument();
  });

  it("shows 'soon' badge on Live button", () => {
    render(<ModeToggle value="pipeline" onChange={vi.fn()} />);
    expect(screen.getByText("soon")).toBeInTheDocument();
  });
});
