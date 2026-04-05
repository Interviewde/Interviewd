import type { PlanMeta } from "../api/client";

const TYPE_LABELS: Record<string, string> = {
  behavioral: "Behavioral",
  technical: "Technical",
  hr: "HR",
  system_design: "System Design",
};

const DIFFICULTY_COLORS: Record<string, string> = {
  entry: "bg-green-100 text-green-700",
  mid: "bg-blue-100 text-blue-700",
  senior: "bg-orange-100 text-orange-700",
  staff: "bg-red-100 text-red-700",
};

interface Props {
  plan: PlanMeta;
  selected: boolean;
  onSelect: () => void;
}

export default function PlanCard({ plan, selected, onSelect }: Props) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className={`w-full text-left rounded-xl border p-4 transition-all ${
        selected
          ? "border-brand-600 bg-brand-50 shadow-sm ring-1 ring-brand-600"
          : "border-gray-200 bg-white hover:border-gray-300"
      }`}
    >
      <div className="flex items-start justify-between gap-3">
        <span className="font-semibold text-gray-800 text-sm leading-snug">
          {plan.title}
        </span>
        <span
          className={`shrink-0 rounded-full px-2 py-0.5 text-xs font-medium ${
            DIFFICULTY_COLORS[plan.difficulty] ?? "bg-gray-100 text-gray-600"
          }`}
        >
          {plan.difficulty}
        </span>
      </div>

      <div className="mt-1 flex items-center gap-2 text-xs text-gray-500">
        <span>{TYPE_LABELS[plan.interview_type] ?? plan.interview_type}</span>
        <span>·</span>
        <span>{plan.num_questions} questions</span>
      </div>

      {plan.summary && (
        <p className="mt-2 text-xs text-gray-500 leading-relaxed line-clamp-2">
          {plan.summary}
        </p>
      )}

      {selected && (
        <p className="mt-2 text-xs font-medium text-brand-600">Selected ✓</p>
      )}
    </button>
  );
}
