/**
 * ModeToggle — switches between pipeline (STT→LLM→TTS chain) and live
 * (real-time voice LLM) interview modes.
 *
 * Live mode is a placeholder: the UI renders the toggle but keeps it
 * disabled until the LiveLLMAdapter is implemented (Sprint 3/4).
 * See docs/decisions/005-dual-path-interview-engine.md.
 */

interface Props {
  value: "pipeline" | "live";
  onChange: (mode: "pipeline" | "live") => void;
}

export default function ModeToggle({ value, onChange }: Props) {
  return (
    <div className="space-y-1">
      <label className="block text-sm font-medium text-gray-700">
        Interview mode
      </label>
      <div className="flex rounded-lg border border-gray-300 overflow-hidden w-fit">
        <button
          type="button"
          onClick={() => onChange("pipeline")}
          className={`px-4 py-2 text-sm font-medium transition-colors ${
            value === "pipeline"
              ? "bg-brand-600 text-white"
              : "bg-white text-gray-600 hover:bg-gray-50"
          }`}
        >
          Pipeline
        </button>
        <button
          type="button"
          disabled
          title="Live mode coming soon — requires real-time voice LLM adapter"
          className="px-4 py-2 text-sm font-medium bg-white text-gray-300 cursor-not-allowed border-l border-gray-300 flex items-center gap-1.5"
        >
          Live
          <span className="text-xs bg-gray-100 text-gray-400 rounded px-1.5 py-0.5 font-normal">
            soon
          </span>
        </button>
      </div>
      <p className="text-xs text-gray-500">
        {value === "pipeline"
          ? "Uses your configured STT → LLM → TTS adapters. Free / local-capable."
          : "Real-time voice API — not yet available."}
      </p>
    </div>
  );
}
