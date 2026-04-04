import { useCallback, useEffect, useRef, useState } from "react";

type RecorderState = "idle" | "recording" | "processing";

interface Props {
  onAudioReady: (blob: Blob) => Promise<void>;
  disabled?: boolean;
}

export default function AudioRecorder({ onAudioReady, disabled = false }: Props) {
  const [recorderState, setRecorderState] = useState<RecorderState>("idle");
  const [seconds, setSeconds] = useState(0);
  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      mediaRecorderRef.current?.stream
        .getTracks()
        .forEach((t) => t.stop());
    };
  }, []);

  const startRecording = useCallback(async () => {
    if (recorderState !== "idle") return;

    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });

    chunksRef.current = [];
    mr.ondataavailable = (e) => {
      if (e.data.size > 0) chunksRef.current.push(e.data);
    };

    mr.onstop = async () => {
      stream.getTracks().forEach((t) => t.stop());
      const blob = new Blob(chunksRef.current, { type: "audio/webm" });
      setRecorderState("processing");
      try {
        await onAudioReady(blob);
      } finally {
        setRecorderState("idle");
        setSeconds(0);
      }
    };

    mr.start(100); // collect chunks every 100 ms
    mediaRecorderRef.current = mr;
    setRecorderState("recording");
    setSeconds(0);

    timerRef.current = setInterval(() => setSeconds((s) => s + 1), 1000);
  }, [recorderState, onAudioReady]);

  const stopRecording = useCallback(() => {
    if (recorderState !== "recording") return;
    if (timerRef.current) clearInterval(timerRef.current);
    mediaRecorderRef.current?.stop();
  }, [recorderState]);

  const isIdle = recorderState === "idle";
  const isRecording = recorderState === "recording";
  const isProcessing = recorderState === "processing";

  return (
    <div className="flex flex-col items-center gap-3">
      <button
        type="button"
        disabled={disabled || isProcessing}
        onClick={isRecording ? stopRecording : startRecording}
        className={`w-20 h-20 rounded-full flex items-center justify-center text-white text-2xl shadow-lg transition-all
          ${isRecording
            ? "bg-red-500 hover:bg-red-600 animate-pulse"
            : isProcessing
            ? "bg-gray-400 cursor-not-allowed"
            : disabled
            ? "bg-gray-200 cursor-not-allowed"
            : "bg-brand-600 hover:bg-brand-700"
          }`}
      >
        {isRecording ? "⏹" : isProcessing ? "⏳" : "🎙"}
      </button>

      <p className="text-sm text-gray-500">
        {isRecording && (
          <span className="text-red-500 font-medium">
            Recording {seconds}s — click to stop
          </span>
        )}
        {isProcessing && "Transcribing…"}
        {isIdle && !disabled && "Click to record your answer"}
        {isIdle && disabled && "Waiting…"}
      </p>
    </div>
  );
}
