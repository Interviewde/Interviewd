import { useCallback, useRef, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, type PracticeQuestionDetail } from "../api/client";
import AgentSpeaker from "../components/AgentSpeaker";
import AudioRecorder from "../components/AudioRecorder";

interface ConversationTurn {
  role: "agent" | "user";
  text: string;
}

export default function PracticeSession() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const initState = location.state as {
    question: PracticeQuestionDetail;
    index: number;
    total: number;
  } | null;

  const [question, setQuestion] = useState<PracticeQuestionDetail | null>(
    initState?.question ?? null
  );
  const [index, setIndex] = useState(initState?.index ?? 0);
  const [total, setTotal] = useState(initState?.total ?? 0);

  // The latest agent utterance — drives AgentSpeaker TTS playback
  const [latestAgentText, setLatestAgentText] = useState<string>("");
  // Full conversation log for the current question
  const [conversation, setConversation] = useState<ConversationTurn[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isAdvancing, setIsAdvancing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const conversationEndRef = useRef<HTMLDivElement>(null);

  const appendTurn = (turn: ConversationTurn) => {
    setConversation((prev) => [...prev, turn]);
    // Scroll to bottom on next tick
    setTimeout(() => {
      conversationEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, 50);
  };

  const handleAudio = useCallback(
    async (blob: Blob) => {
      if (!sessionId) return;
      setError(null);
      setIsLoading(true);
      try {
        const res = await api.submitPracticeAnswer(sessionId, blob);
        appendTurn({ role: "user", text: res.transcript });
        appendTurn({ role: "agent", text: res.agent_text });
        setLatestAgentText(res.agent_text);
      } catch (err) {
        setError(String(err));
      } finally {
        setIsLoading(false);
      }
    },
    [sessionId]
  );

  const handleNext = useCallback(async () => {
    if (!sessionId) return;
    setIsAdvancing(true);
    setError(null);
    try {
      const res = await api.nextPracticeQuestion(sessionId);
      if (res.status === "complete") {
        navigate("/practice");
      } else if (res.question) {
        setQuestion(res.question);
        setIndex(res.index ?? 0);
        setTotal(res.total ?? total);
        setConversation([]);
        setLatestAgentText("");
      }
    } catch (err) {
      setError(String(err));
    } finally {
      setIsAdvancing(false);
    }
  }, [sessionId, navigate, total]);

  if (!question) {
    return (
      <p className="text-gray-500 text-sm">
        Session lost —{" "}
        <a href="/practice" className="text-brand-600 underline">
          start a new practice session
        </a>
        .
      </p>
    );
  }

  const isLast = index === total - 1;

  return (
    <div className="max-w-2xl mx-auto space-y-5">
      {/* Header: progress + next button */}
      <div className="flex items-center justify-between">
        <div className="space-y-1 flex-1">
          <div className="flex justify-between text-xs text-gray-400">
            <span>Practice</span>
            <span>
              {index + 1} / {total}
            </span>
          </div>
          <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
            <div
              className="h-full bg-brand-600 rounded-full transition-all duration-500"
              style={{ width: `${((index + 1) / total) * 100}%` }}
            />
          </div>
        </div>

        <button
          type="button"
          onClick={handleNext}
          disabled={isAdvancing}
          className="ml-4 shrink-0 rounded-lg border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 hover:border-brand-400 hover:text-brand-700 disabled:opacity-50 transition-colors"
        >
          {isAdvancing
            ? "…"
            : isLast
            ? "Finish practice"
            : "Next question →"}
        </button>
      </div>

      {/* Question card — always visible in practice mode */}
      <div className="bg-white rounded-xl border border-gray-200 shadow-sm p-6 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-brand-600">
            Question {index + 1}
          </span>
          <DiffBadge difficulty={question.difficulty} />
          {question.tags.slice(0, 2).map((t) => (
            <span
              key={t}
              className="rounded-full bg-gray-100 text-gray-500 px-2 py-0.5 text-xs"
            >
              {t}
            </span>
          ))}
        </div>
        <p className="text-lg font-medium leading-relaxed text-gray-800">
          {question.text}
        </p>
        {question.rationale && (
          <p className="text-xs text-gray-400 italic">{question.rationale}</p>
        )}
      </div>

      {/* Conversation history */}
      {conversation.length > 0 && (
        <div className="space-y-3">
          {conversation.map((turn, i) => (
            <ChatBubble key={i} turn={turn} />
          ))}
          <div ref={conversationEndRef} />
        </div>
      )}

      {/* Agent speaker — plays TTS for latest agent response */}
      {latestAgentText && (
        <AgentSpeaker text={latestAgentText} label="Coach" />
      )}

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      {/* Recorder */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-6 flex flex-col items-center space-y-3">
        <p className="text-sm font-medium text-gray-600">
          {isLoading ? "Processing…" : "Record your answer"}
        </p>
        <AudioRecorder onAudioReady={handleAudio} />
        <p className="text-xs text-gray-400">
          Ask for clarification or answer the question — the coach will respond.
        </p>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Small components
// ---------------------------------------------------------------------------

function ChatBubble({ turn }: { turn: ConversationTurn }) {
  const isAgent = turn.role === "agent";
  return (
    <div className={`flex ${isAgent ? "justify-start" : "justify-end"}`}>
      <div
        className={`max-w-[80%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed ${
          isAgent
            ? "bg-brand-50 text-brand-900 rounded-tl-sm"
            : "bg-gray-100 text-gray-800 rounded-tr-sm"
        }`}
      >
        <span
          className={`block text-xs font-semibold mb-0.5 ${
            isAgent ? "text-brand-600" : "text-gray-500"
          }`}
        >
          {isAgent ? "Coach" : "You"}
        </span>
        {turn.text}
      </div>
    </div>
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
