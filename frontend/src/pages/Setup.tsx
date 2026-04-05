import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type GeneratedPlan } from "../api/client";
import ModeToggle from "../components/ModeToggle";
import PlanCard from "../components/PlanCard";

const TYPES = ["behavioral", "technical", "hr", "system_design"] as const;
const DIFFICULTIES = ["entry", "mid", "senior", "staff"] as const;
const PERSONAS = ["friendly", "neutral", "adversarial"] as const;

type Tab = "manual" | "plan";

// ---------------------------------------------------------------------------
// Main page
// ---------------------------------------------------------------------------

export default function Setup() {
  const [searchParams] = useSearchParams();
  const [tab, setTab] = useState<Tab>(
    searchParams.get("tab") === "plan" ? "plan" : "manual"
  );

  return (
    <div className="max-w-xl mx-auto space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-gray-800">New Interview</h1>
        <p className="text-gray-500 mt-1 text-sm">
          Configure your session and hit Start when ready.
        </p>
      </div>

      {/* Tab toggle */}
      <div className="flex rounded-xl border border-gray-200 bg-gray-50 p-1 gap-1">
        <TabButton active={tab === "manual"} onClick={() => setTab("manual")}>
          Configure manually
        </TabButton>
        <TabButton active={tab === "plan"} onClick={() => setTab("plan")}>
          Use a plan
        </TabButton>
      </div>

      {tab === "manual" ? <ManualTab /> : <PlanTab />}
    </div>
  );
}

function TabButton({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 rounded-lg py-2 text-sm font-medium transition-colors ${
        active
          ? "bg-white text-brand-700 shadow-sm"
          : "text-gray-500 hover:text-gray-700"
      }`}
    >
      {children}
    </button>
  );
}

// ---------------------------------------------------------------------------
// Manual tab (existing flow)
// ---------------------------------------------------------------------------

function ManualTab() {
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
    <div className="space-y-6">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-6">
        <Field label="Interview type">
          <div className="grid grid-cols-2 gap-2">
            {TYPES.map((t) => (
              <ToggleBtn
                key={t}
                active={form.type === t}
                onClick={() => set("type", t)}
              >
                {t.replace("_", " ")}
              </ToggleBtn>
            ))}
          </div>
        </Field>

        <Field label="Difficulty">
          <div className="flex gap-2">
            {DIFFICULTIES.map((d) => (
              <ToggleBtn
                key={d}
                active={form.difficulty === d}
                onClick={() => set("difficulty", d)}
                className="flex-1"
              >
                {d}
              </ToggleBtn>
            ))}
          </div>
        </Field>

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

        <Field label="Interviewer persona">
          <div className="flex gap-2">
            {PERSONAS.map((p) => (
              <ToggleBtn
                key={p}
                active={form.persona === p}
                onClick={() => set("persona", p)}
                className="flex-1"
              >
                {p}
              </ToggleBtn>
            ))}
          </div>
        </Field>

        <ModeToggle value={form.mode} onChange={(m) => set("mode", m)} />
      </div>

      {mutation.isError && <ErrorBanner error={mutation.error} />}

      <StartButton
        pending={mutation.isPending}
        onClick={() => mutation.mutate()}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plan tab
// ---------------------------------------------------------------------------

type PlanSubTab = "standard" | "generate";

function PlanTab() {
  const [subTab, setSubTab] = useState<PlanSubTab>("standard");

  return (
    <div className="space-y-4">
      <div className="flex gap-3 border-b border-gray-200">
        <SubTabBtn
          active={subTab === "standard"}
          onClick={() => setSubTab("standard")}
        >
          Standard plans
        </SubTabBtn>
        <SubTabBtn
          active={subTab === "generate"}
          onClick={() => setSubTab("generate")}
        >
          Generate from JD + Resume
        </SubTabBtn>
      </div>

      {subTab === "standard" ? <StandardPlansSection /> : <GenerateSection />}
    </div>
  );
}

function SubTabBtn({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`pb-2 text-sm font-medium border-b-2 transition-colors ${
        active
          ? "border-brand-600 text-brand-700"
          : "border-transparent text-gray-500 hover:text-gray-700"
      }`}
    >
      {children}
    </button>
  );
}

// --- Standard plans ---

function StandardPlansSection() {
  const navigate = useNavigate();
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { data: plans = [], isLoading, isError } = useQuery({
    queryKey: ["plans"],
    queryFn: api.listPlans,
  });

  const mutation = useMutation({
    mutationFn: () =>
      api.startInterview({
        type: "behavioral",
        difficulty: "mid",
        num_questions: 5,
        persona: "neutral",
        plan_id: selectedId ?? undefined,
      }),
    onSuccess: (data) => {
      navigate(`/interview/${data.session_id}`, {
        state: { question: data.question },
      });
    },
  });

  if (isLoading) {
    return <p className="text-sm text-gray-400 py-4">Loading plans…</p>;
  }
  if (isError || plans.length === 0) {
    return (
      <p className="text-sm text-gray-500 py-4">
        No standard plans found in <code>config/plans/</code>.
      </p>
    );
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-3">
        {plans.map((p) => (
          <PlanCard
            key={p.id}
            plan={p}
            selected={selectedId === p.id}
            onSelect={() => setSelectedId(p.id)}
          />
        ))}
      </div>

      {mutation.isError && <ErrorBanner error={mutation.error} />}

      <StartButton
        pending={mutation.isPending}
        disabled={selectedId === null}
        onClick={() => mutation.mutate()}
        label={selectedId ? "Start interview with this plan →" : "Select a plan to continue"}
      />
    </div>
  );
}

// --- Generate from JD + Resume ---

function GenerateSection() {
  const navigate = useNavigate();

  const [type, setType] = useState<(typeof TYPES)[number]>("technical");
  const [difficulty, setDifficulty] =
    useState<(typeof DIFFICULTIES)[number]>("mid");
  const [numQuestions, setNumQuestions] = useState(5);
  const [jdFile, setJdFile] = useState<File | null>(null);
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [generatedPlan, setGeneratedPlan] = useState<GeneratedPlan | null>(null);

  const jdInputRef = useRef<HTMLInputElement>(null);
  const resumeInputRef = useRef<HTMLInputElement>(null);

  const generateMutation = useMutation({
    mutationFn: () => {
      const fd = new FormData();
      fd.append("jd_file", jdFile!);
      fd.append("resume_file", resumeFile!);
      fd.append("interview_type", type);
      fd.append("difficulty", difficulty);
      fd.append("num_questions", String(numQuestions));
      return api.generatePlan(fd);
    },
    onSuccess: (plan) => setGeneratedPlan(plan),
  });

  const startMutation = useMutation({
    mutationFn: () =>
      api.startInterview({
        type: generatedPlan!.interview_type,
        difficulty: generatedPlan!.difficulty,
        num_questions: generatedPlan!.num_questions,
        persona: generatedPlan!.persona,
        plan_data: generatedPlan!,
      }),
    onSuccess: (data) => {
      navigate(`/interview/${data.session_id}`, {
        state: { question: data.question },
      });
    },
  });

  // Show plan preview once generated
  if (generatedPlan) {
    return (
      <PlanPreview
        plan={generatedPlan}
        onReset={() => setGeneratedPlan(null)}
        onStart={() => startMutation.mutate()}
        starting={startMutation.isPending}
        startError={startMutation.isError ? startMutation.error : null}
      />
    );
  }

  const canGenerate = jdFile !== null && resumeFile !== null;

  return (
    <div className="space-y-5">
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-6">
        {/* File uploads */}
        <div className="grid grid-cols-2 gap-4">
          <FileDropZone
            label="Job Description"
            hint=".pdf, .txt, .md"
            file={jdFile}
            inputRef={jdInputRef}
            onChange={setJdFile}
          />
          <FileDropZone
            label="Resume / CV"
            hint=".pdf, .txt, .md"
            file={resumeFile}
            inputRef={resumeInputRef}
            onChange={setResumeFile}
          />
        </div>

        <Field label="Interview type">
          <div className="grid grid-cols-2 gap-2">
            {TYPES.map((t) => (
              <ToggleBtn
                key={t}
                active={type === t}
                onClick={() => setType(t)}
              >
                {t.replace("_", " ")}
              </ToggleBtn>
            ))}
          </div>
        </Field>

        <Field label="Difficulty">
          <div className="flex gap-2">
            {DIFFICULTIES.map((d) => (
              <ToggleBtn
                key={d}
                active={difficulty === d}
                onClick={() => setDifficulty(d)}
                className="flex-1"
              >
                {d}
              </ToggleBtn>
            ))}
          </div>
        </Field>

        <Field label={`Questions: ${numQuestions}`}>
          <input
            type="range"
            min={1}
            max={10}
            value={numQuestions}
            onChange={(e) => setNumQuestions(Number(e.target.value))}
            className="w-full accent-brand-600"
          />
          <div className="flex justify-between text-xs text-gray-400 mt-1">
            <span>1</span>
            <span>10</span>
          </div>
        </Field>
      </div>

      {generateMutation.isPending && <GeneratingIndicator />}
      {generateMutation.isError && <ErrorBanner error={generateMutation.error} />}

      <button
        type="button"
        disabled={!canGenerate || generateMutation.isPending}
        onClick={() => generateMutation.mutate()}
        className="w-full bg-brand-600 text-white font-semibold rounded-xl py-3 text-sm hover:bg-brand-700 disabled:opacity-50 transition-colors shadow"
      >
        {generateMutation.isPending ? "Analysing…" : "Generate plan →"}
      </button>

      {!canGenerate && (
        <p className="text-xs text-center text-gray-400">
          Upload both files to continue
        </p>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Plan preview (shown after generation)
// ---------------------------------------------------------------------------

function PlanPreview({
  plan,
  onReset,
  onStart,
  starting,
  startError,
}: {
  plan: GeneratedPlan;
  onReset: () => void;
  onStart: () => void;
  starting: boolean;
  startError: Error | null;
}) {
  const [showQuestions, setShowQuestions] = useState(false);
  const gaps = plan.skills_analysis.skill_gaps;

  return (
    <div className="space-y-4">
      {/* Summary card */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold text-gray-800">Plan ready</h2>
          <div className="flex gap-2 text-xs">
            <Badge>{plan.interview_type.replace("_", " ")}</Badge>
            <Badge>{plan.difficulty}</Badge>
            <Badge>{plan.num_questions} questions</Badge>
          </div>
        </div>

        <p className="text-sm text-gray-600">{plan.skills_analysis.summary}</p>

        {gaps.length > 0 && (
          <div>
            <p className="text-xs font-medium text-gray-500 uppercase tracking-wide mb-2">
              Focus areas
            </p>
            <div className="flex flex-wrap gap-2">
              {gaps.map((g) => (
                <span
                  key={g.skill}
                  className={`rounded-full px-2.5 py-0.5 text-xs font-medium ${
                    g.resume_level === "missing"
                      ? "bg-red-100 text-red-700"
                      : "bg-yellow-100 text-yellow-700"
                  }`}
                >
                  {g.skill}
                </span>
              ))}
            </div>
          </div>
        )}

        {/* Collapsible question list */}
        <button
          type="button"
          onClick={() => setShowQuestions((v) => !v)}
          className="text-xs text-brand-600 hover:underline"
        >
          {showQuestions ? "Hide questions ▲" : "Preview questions ▼"}
        </button>

        {showQuestions && (
          <ol className="space-y-3 mt-1">
            {plan.questions.map((q, i) => (
              <li key={q.id} className="text-sm">
                <span className="font-medium text-gray-700">Q{i + 1}.</span>{" "}
                <span className="text-gray-600">{q.text}</span>
                {q.rationale && (
                  <p className="text-xs text-gray-400 mt-0.5 italic">
                    {q.rationale}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </div>

      {startError && <ErrorBanner error={startError} />}

      <div className="flex gap-3">
        <button
          type="button"
          onClick={onReset}
          className="flex-1 rounded-xl border border-gray-200 py-3 text-sm font-medium text-gray-600 hover:border-gray-300 transition-colors"
        >
          ← Regenerate
        </button>
        <button
          type="button"
          disabled={starting}
          onClick={onStart}
          className="flex-[2] bg-brand-600 text-white font-semibold rounded-xl py-3 text-sm hover:bg-brand-700 disabled:opacity-60 transition-colors shadow"
        >
          {starting ? "Starting…" : "Start interview with this plan →"}
        </button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small shared components
// ---------------------------------------------------------------------------

function FileDropZone({
  label,
  hint,
  file,
  inputRef,
  onChange,
}: {
  label: string;
  hint: string;
  file: File | null;
  inputRef: React.RefObject<HTMLInputElement>;
  onChange: (f: File | null) => void;
}) {
  return (
    <div>
      <p className="text-xs font-medium text-gray-700 mb-1.5">{label}</p>
      <button
        type="button"
        onClick={() => inputRef.current?.click()}
        className={`w-full rounded-xl border-2 border-dashed px-3 py-4 text-center transition-colors ${
          file
            ? "border-brand-400 bg-brand-50"
            : "border-gray-200 hover:border-gray-300"
        }`}
      >
        {file ? (
          <span className="text-xs text-brand-700 font-medium truncate block">
            {file.name}
          </span>
        ) : (
          <span className="text-xs text-gray-400">
            Click to upload
            <br />
            <span className="text-gray-300">{hint}</span>
          </span>
        )}
      </button>
      <input
        ref={inputRef}
        type="file"
        accept=".pdf,.txt,.md"
        className="hidden"
        onChange={(e) => onChange(e.target.files?.[0] ?? null)}
      />
    </div>
  );
}

function GeneratingIndicator() {
  const steps = [
    "Reading files",
    "Analysing skills",
    "Generating questions",
  ];
  return (
    <div className="bg-brand-50 rounded-xl px-4 py-3 space-y-1.5">
      {steps.map((s) => (
        <div key={s} className="flex items-center gap-2 text-sm text-brand-700">
          <span className="animate-pulse">•</span>
          {s}
        </div>
      ))}
    </div>
  );
}

function Badge({ children }: { children: React.ReactNode }) {
  return (
    <span className="rounded-full bg-brand-100 text-brand-700 px-2.5 py-0.5 capitalize">
      {children}
    </span>
  );
}

function ToggleBtn({
  active,
  onClick,
  children,
  className = "",
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-4 py-2 text-sm font-medium capitalize transition-colors ${
        active
          ? "border-brand-600 bg-brand-50 text-brand-700"
          : "border-gray-200 text-gray-600 hover:border-gray-300"
      } ${className}`}
    >
      {children}
    </button>
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

function StartButton({
  pending,
  disabled = false,
  onClick,
  label = "Start interview →",
}: {
  pending: boolean;
  disabled?: boolean;
  onClick: () => void;
  label?: string;
}) {
  return (
    <button
      type="button"
      disabled={pending || disabled}
      onClick={onClick}
      className="w-full bg-brand-600 text-white font-semibold rounded-xl py-3 text-sm hover:bg-brand-700 disabled:opacity-60 transition-colors shadow"
    >
      {pending ? "Starting…" : label}
    </button>
  );
}

function ErrorBanner({ error }: { error: unknown }) {
  return (
    <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
      {String(error)}
    </p>
  );
}
