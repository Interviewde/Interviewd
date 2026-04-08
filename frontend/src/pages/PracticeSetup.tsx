import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type PlanMeta, type PracticeQuestionDetail } from "../api/client";
import PlanCard from "../components/PlanCard";

export default function PracticeSetup() {
  const [selectedPlan, setSelectedPlan] = useState<PlanMeta | null>(null);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const navigate = useNavigate();

  const { data: plans = [], isLoading: plansLoading } = useQuery({
    queryKey: ["plans"],
    queryFn: api.listPlans,
  });

  const {
    data: questions = [],
    isLoading: questionsLoading,
    isError: questionsError,
    error: questionsErrorObj,
  } = useQuery({
    queryKey: ["plan-questions", selectedPlan?.id],
    queryFn: () => api.listPlanQuestions(selectedPlan!.id),
    enabled: selectedPlan !== null,
  });

  const startMutation = useMutation({
    mutationFn: () =>
      api.startPractice({
        plan_id: selectedPlan!.id,
        question_ids: Array.from(selectedIds),
      }),
    onSuccess: (data) => {
      navigate(`/practice/${data.session_id}`, {
        state: {
          question: data.question,
          index: data.index,
          total: data.total,
        },
      });
    },
  });

  function handlePlanSelect(plan: PlanMeta) {
    setSelectedPlan(plan);
    setSelectedIds(new Set());
  }

  function toggleQuestion(id: string) {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function selectAll() {
    setSelectedIds(new Set(questions.map((q) => q.id)));
  }

  function deselectAll() {
    setSelectedIds(new Set());
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">Practice mode</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Pick a plan, select the questions you want to drill, and practice
          with full back-and-forth coaching on each one.
        </p>
      </div>

      {/* Step 1 — plan picker */}
      <Section label="1. Choose a plan">
        {plansLoading ? (
          <p className="text-sm text-gray-400">Loading plans…</p>
        ) : plans.length === 0 ? (
          <p className="text-sm text-gray-500">
            No standard plans found in <code>config/plans/</code>.
          </p>
        ) : (
          <div className="grid gap-3">
            {plans.map((p) => (
              <PlanCard
                key={p.id}
                plan={p}
                selected={selectedPlan?.id === p.id}
                onSelect={() => handlePlanSelect(p)}
              />
            ))}
          </div>
        )}
      </Section>

      {/* Step 2 — question picker */}
      {selectedPlan && (
        <Section label="2. Select questions to practice">
          {questionsLoading ? (
            <p className="text-sm text-gray-400">Loading questions…</p>
          ) : questionsError ? (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
              Failed to load questions: {String(questionsErrorObj)}
            </p>
          ) : (
            <>
              <div className="flex gap-3 mb-3">
                <button
                  type="button"
                  onClick={selectAll}
                  className="text-xs text-brand-600 hover:underline"
                >
                  Select all
                </button>
                <button
                  type="button"
                  onClick={deselectAll}
                  className="text-xs text-gray-400 hover:underline"
                >
                  Deselect all
                </button>
                <span className="text-xs text-gray-400 ml-auto">
                  {selectedIds.size} / {questions.length} selected
                </span>
              </div>

              <div className="space-y-2">
                {questions.map((q, i) => (
                  <QuestionRow
                    key={q.id}
                    index={i}
                    question={q}
                    selected={selectedIds.has(q.id)}
                    onToggle={() => toggleQuestion(q.id)}
                  />
                ))}
              </div>
            </>
          )}
        </Section>
      )}

      {/* Start button */}
      {selectedPlan && selectedIds.size > 0 && (
        <div className="space-y-2">
          {startMutation.isError && (
            <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
              {String(startMutation.error)}
            </p>
          )}
          <button
            type="button"
            disabled={startMutation.isPending}
            onClick={() => startMutation.mutate()}
            className="w-full bg-brand-600 text-white font-semibold rounded-xl py-3 text-sm hover:bg-brand-700 disabled:opacity-60 transition-colors shadow"
          >
            {startMutation.isPending
              ? "Starting…"
              : `Start practice (${selectedIds.size} question${selectedIds.size !== 1 ? "s" : ""}) →`}
          </button>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function Section({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <div className="space-y-3">
      <h2 className="text-sm font-semibold text-gray-700 uppercase tracking-wide">
        {label}
      </h2>
      {children}
    </div>
  );
}

function QuestionRow({
  index,
  question,
  selected,
  onToggle,
}: {
  index: number;
  question: PracticeQuestionDetail;
  selected: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={`w-full text-left rounded-xl border px-4 py-3 transition-colors ${
        selected
          ? "border-brand-400 bg-brand-50"
          : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="flex items-start gap-3">
        {/* Checkbox */}
        <div
          className={`mt-0.5 h-4 w-4 shrink-0 rounded border-2 flex items-center justify-center ${
            selected
              ? "border-brand-600 bg-brand-600"
              : "border-gray-300"
          }`}
        >
          {selected && (
            <svg
              className="w-2.5 h-2.5 text-white"
              fill="none"
              viewBox="0 0 10 8"
              stroke="currentColor"
              strokeWidth={2}
            >
              <path d="M1 4l3 3 5-5" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          )}
        </div>

        <div className="flex-1 min-w-0">
          <p className="text-sm text-gray-800 leading-snug">
            <span className="font-medium text-gray-500 mr-1">Q{index + 1}.</span>
            {question.text}
          </p>
          <div className="flex flex-wrap gap-1.5 mt-1.5">
            <DiffBadge difficulty={question.difficulty} />
            {question.tags.slice(0, 3).map((t) => (
              <span
                key={t}
                className="rounded-full bg-gray-100 text-gray-500 px-2 py-0.5 text-xs"
              >
                {t}
              </span>
            ))}
          </div>
          {question.rationale && (
            <p className="text-xs text-gray-400 mt-1 italic">{question.rationale}</p>
          )}
        </div>
      </div>
    </button>
  );
}

function DiffBadge({ difficulty }: { difficulty: string }) {
  const colour: Record<string, string> = {
    entry: "bg-green-100 text-green-700",
    mid: "bg-yellow-100 text-yellow-700",
    senior: "bg-orange-100 text-orange-700",
    staff: "bg-red-100 text-red-700",
  };
  return (
    <span
      className={`rounded-full px-2 py-0.5 text-xs font-medium capitalize ${
        colour[difficulty] ?? "bg-gray-100 text-gray-600"
      }`}
    >
      {difficulty}
    </span>
  );
}
