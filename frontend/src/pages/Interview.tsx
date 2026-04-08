import { useCallback, useState } from "react";
import { useLocation, useNavigate, useParams } from "react-router-dom";
import { api, type QuestionPayload } from "../api/client";
import AudioRecorder from "../components/AudioRecorder";
import QuestionCard from "../components/QuestionCard";

type Phase = "answering" | "complete";

export default function Interview() {
  const { sessionId } = useParams<{ sessionId: string }>();
  const location = useLocation();
  const navigate = useNavigate();

  const [question, setQuestion] = useState<QuestionPayload>(
    location.state?.question as QuestionPayload
  );
  const [phase, setPhase] = useState<Phase>("answering");
  const [error, setError] = useState<string | null>(null);
  const [lastTranscript, setLastTranscript] = useState<string | null>(null);
  const [clarificationText, setClarificationText] = useState<string | null>(null);
  const [isEnding, setIsEnding] = useState(false);

  const handleAudio = useCallback(
    async (blob: Blob) => {
      setError(null);
      try {
        const res = await api.submitAnswer(sessionId!, blob);
        setLastTranscript(res.transcript ?? null);

        if (res.status === "complete" && res.session_id) {
          setPhase("complete");
          // Brief pause so user sees the "complete" state before redirect
          setTimeout(() => navigate(`/report/${res.session_id}`), 1500);
        } else if (res.status === "clarification") {
          // Agent responded to a clarifying question — stay on same question
          setClarificationText(res.clarification_text ?? null);
          if (res.question) setQuestion(res.question);
        } else if (res.question) {
          setClarificationText(null);
          setQuestion(res.question);
        }
      } catch (err) {
        setError(String(err));
      }
    },
    [sessionId, navigate]
  );

  const handleEndInterview = useCallback(async () => {
    if (!confirm("End the interview now? Answers recorded so far will be scored.")) return;
    setIsEnding(true);
    setError(null);
    try {
      const res = await api.endInterview(sessionId!);
      if (res.session_id) {
        navigate(`/report/${res.session_id}`);
      } else {
        navigate("/setup");
      }
    } catch (err) {
      setError(String(err));
      setIsEnding(false);
    }
  }, [sessionId, navigate]);

  if (!question) {
    return (
      <p className="text-gray-500 text-sm">
        Session state lost — please{" "}
        <a href="/setup" className="text-brand-600 underline">
          start a new interview
        </a>
        .
      </p>
    );
  }

  if (phase === "complete") {
    return (
      <div className="flex flex-col items-center justify-center py-24 space-y-4 text-center">
        <p className="text-5xl">✅</p>
        <h2 className="text-2xl font-bold text-gray-800">Interview complete!</h2>
        <p className="text-gray-500 text-sm">Scoring your answers…</p>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Progress bar + session info */}
      <div>
        <div className="flex justify-between text-xs text-gray-400 mb-1">
          <span>Progress</span>
          <span className="flex items-center gap-3">
            <span className="font-mono opacity-60">
              Session: {sessionId?.slice(0, 8)}
            </span>
            <span>
              {question.index + 1} / {question.total}
            </span>
          </span>
        </div>
        <div className="h-1.5 bg-gray-100 rounded-full overflow-hidden">
          <div
            className="h-full bg-brand-600 rounded-full transition-all duration-500"
            style={{ width: `${((question.index + 1) / question.total) * 100}%` }}
          />
        </div>
      </div>

      {/* Question */}
      <QuestionCard question={question} autoPlayTts />

      {/* Interviewer clarification response */}
      {clarificationText && (
        <div className="bg-brand-50 border border-brand-200 rounded-lg px-4 py-3 text-sm text-brand-800">
          <span className="font-semibold text-brand-600">Interviewer: </span>
          {clarificationText}
        </div>
      )}

      {/* Transcript preview */}
      {lastTranscript && (
        <div className="bg-gray-50 rounded-lg px-4 py-3 text-sm text-gray-600">
          <span className="font-medium text-gray-500">You said: </span>
          {lastTranscript}
        </div>
      )}

      {/* Recorder */}
      <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-8 flex flex-col items-center space-y-4">
        <p className="text-sm font-medium text-gray-600">
          {question.is_follow_up
            ? "Record your follow-up answer"
            : "Record your answer"}
        </p>
        <AudioRecorder onAudioReady={handleAudio} />
        <p className="text-xs text-gray-400">
          Make sure your microphone is permitted in the browser.
        </p>
      </div>

      {error && (
        <p className="text-sm text-red-600 bg-red-50 rounded-lg px-4 py-3">
          {error}
        </p>
      )}

      {/* End interview */}
      <div className="flex justify-center pt-2">
        <button
          type="button"
          onClick={handleEndInterview}
          disabled={isEnding}
          className="text-xs text-gray-400 hover:text-red-500 transition-colors disabled:opacity-50"
        >
          {isEnding ? "Ending…" : "End interview early"}
        </button>
      </div>
    </div>
  );
}
