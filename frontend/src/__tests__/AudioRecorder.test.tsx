import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import AudioRecorder from "../components/AudioRecorder";

describe("AudioRecorder", () => {
  it("renders the record button in idle state", () => {
    render(<AudioRecorder onAudioReady={vi.fn()} />);
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("shows idle prompt text", () => {
    render(<AudioRecorder onAudioReady={vi.fn()} />);
    expect(screen.getByText(/click to record/i)).toBeInTheDocument();
  });

  it("button is disabled when disabled prop is true", () => {
    render(<AudioRecorder onAudioReady={vi.fn()} disabled />);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("shows waiting text when disabled", () => {
    render(<AudioRecorder onAudioReady={vi.fn()} disabled />);
    expect(screen.getByText(/waiting/i)).toBeInTheDocument();
  });

  it("starts recording on click and requests microphone access", async () => {
    render(<AudioRecorder onAudioReady={vi.fn()} />);
    await userEvent.click(screen.getByRole("button"));
    expect(navigator.mediaDevices.getUserMedia).toHaveBeenCalledWith({ audio: true });
  });
});
