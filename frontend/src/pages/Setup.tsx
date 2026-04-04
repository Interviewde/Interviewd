import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { api } from "../api/client";
import ModeToggle from "../components/ModeToggle";

const TYPES = ["behavioral", "technical", "hr", "system_design"] as const;
const DIFFICULTIES = ["entry", "mid", "senior", "staff"] as const;
const PERSONAS = ["friendly", "neutral", "adversarial"] as const;

export default function Setup() {
  const navigate = useNavigate();

  const [form, setForm] = useState({
    type: "behavioral" as (typeof TYPES)[number],
    difficulty: "mid" as (typeof DIFFICULTIES)[number],
    num_questions: 5,
    persona: "neutral" as (typeof PERSONAS)[number],
    mode: "pipeline" as "pipeline" | "live",
  });

  const mutation = useMutation({
    mutationFn: () =>
      api.startInterview({
        type: form.type,
        difficulty: form.difficulty,
        num_questions: form.num_questions,
        persona: form.persona,
      }),
    onSuccess: (data) => {
      navigate(`/interview/${data.session_id}`, {
        state: { question: data.question },
      });
    },
  });

  function set<K extends keyof typeof form>(key: K, val: (typeof form)[K]) {
    setForm((f) => ({ ...f, [key]: val }));
  }

  return (
    <div className="max-w-xl mx-auto space-y-8">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">New Interview</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Configure your session and hit Start when ready.
        </p>
      </div>

      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-6">
        {/* Type */}
        <Field label="Interview type">
          <div className="grid grid-cols-2 gap-2">
            {TYPES.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => set("type", t)}
                className={`rounded-lg border px-4 py-2 text-sm font-medium capitalize transition-colors ${
                  form.type === t
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 text-gray-600 hover:border-gray-300"
                }`}
              >
                {t.replace("_", " ")}
              </button>
            ))}
          </div>
        </Field>

        {/* Difficulty */}
        <Field label="Difficulty">
          <div className="flex gap-2">
            {DIFFICULTIES.map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => set("difficulty", d)}
                className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium capitalize transition-colors ${
                  form.difficulty === d
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 text-gray-600 hover:border-gray-300"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </Field>

        {/* Number of questions */}
        <Field label={`Questions: ${form.num_questions}`}>
          <input
            type="range"
            min={1}
            max={10}
            value={form.num_questions}
            onChange={(e) => set("num_questions", Number(e.target.value))}
            className="w-full accent-brand-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>1</span>
            <span>10</span>
          </div>
        </Field>

        {/* Persona */}
        <Field label="Interviewer persona">
          <div className="flex gap-2">
            {PERSONAS.map((p) => (
              <button
                key={p}
                type="button"
                onClick={() => set("persona", p)}
                className={`flex-1 rounded-lg border px-3 py-2 text-sm font-medium capitalize transition-colors ${
                  form.persona === p
                    ? "border-brand-600 bg-brand-50 text-brand-700"
                    : "border-gray-200 text-gray-600 hover:border-gray-300"
                }`}
              >
                {p}
              </button>
            ))}
          </div>
        </Field>

        {/* Mode toggle */}
        <ModeToggle value={form.mode} onChange={(m) => set("mode", m)} />
      </div>

      {mutation.isError && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
          {String(mutation.error)}
        </p>
      )}

      <button
        type="button"
        disabled={mutation.isPending}
        onClick={() => mutation.mutate()}
        className="w-full bg-brand-600 text-white font-semibold rounded-xl py-3 text-sm hover:bg-brand-700 disabled:opacity-60 transition-colors shadow"
      >
        {mutation.isPending ? "Starting…" : "Start interview →"}
      </button>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-gray-700">{label}</label>
      {children}
    </div>
  );
}
