import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import ScoreCard from "../components/ScoreCard";
import type { AnswerScore } from "../api/client";

const SCORE: AnswerScore = {
  question_id: "b001",
  question_text: "Tell me about a time you led a project.",
  answer: "I led the migration of our monolith to microservices.",
  star_score: 8,
  relevance_score: 9,
  clarity_score: 7,
  overall: 8.3,
  feedback: "Strong STAR structure with concrete outcomes.",
};

describe("ScoreCard", () => {
  it("renders the question text", () => {
    render(<ScoreCard score={SCORE} questionNumber={1} />);
    expect(screen.getByText(SCORE.question_text)).toBeInTheDocument();
  });

  it("renders the candidate answer", () => {
    render(<ScoreCard score={SCORE} questionNumber={1} />);
    expect(screen.getByText(SCORE.answer)).toBeInTheDocument();
  });

  it("renders the overall score", () => {
    render(<ScoreCard score={SCORE} questionNumber={1} />);
    expect(screen.getByText("8.3")).toBeInTheDocument();
  });

  it("renders STAR, Relevance and Clarity labels", () => {
    render(<ScoreCard score={SCORE} questionNumber={1} />);
    expect(screen.getByText("STAR")).toBeInTheDocument();
    expect(screen.getByText("Relevance")).toBeInTheDocument();
    expect(screen.getByText("Clarity")).toBeInTheDocument();
  });

  it("renders individual scores", () => {
    render(<ScoreCard score={SCORE} questionNumber={1} />);
    expect(screen.getByText("8/10")).toBeInTheDocument(); // star
    expect(screen.getByText("9/10")).toBeInTheDocument(); // relevance
    expect(screen.getByText("7/10")).toBeInTheDocument(); // clarity
  });

  it("renders the feedback text", () => {
    render(<ScoreCard score={SCORE} questionNumber={1} />);
    expect(screen.getByText(/Strong STAR structure/i)).toBeInTheDocument();
  });

  it("renders Q prefix with question number", () => {
    render(<ScoreCard score={SCORE} questionNumber={3} />);
    expect(screen.getByText("Q3")).toBeInTheDocument();
  });
});
