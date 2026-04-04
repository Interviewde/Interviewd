import asyncio
import io
import wave
from collections import deque

import sounddevice as sd

from interviewd.adapters.stt.base import STTAdapter
from interviewd.adapters.tts.base import TTSAdapter
from interviewd.adapters.vad.base import VADAdapter


class VoiceLoop:
    """Wires VAD → STT → TTS into a single turn-based voice interaction.

    One "turn" = listen() then speak():
    - listen(): records the mic until speech is detected and ends, then
      transcribes and returns the text.
    - speak(): synthesizes text and plays it through the speaker.

    Usage:
        loop = VoiceLoop(vad_adapter, stt_adapter, tts_adapter)
        transcript = await loop.listen()   # blocks until user stops speaking
        await loop.speak(response_text)    # plays TTS response
    """

    _CHUNK_MS = 96  # 1536 samples at 16 kHz; matches the live VAD test script

    def __init__(
        self,
        vad: VADAdapter,
        stt: STTAdapter,
        tts: TTSAdapter,
        *,
        silence_timeout_ms: int = 800,
        pre_speech_pad_ms: int = 200,
        max_duration_s: int = 60,
    ):
        """Initialise the voice loop.

        Args:
            vad: VAD adapter used for speech detection.
            stt: STT adapter used for transcription.
            tts: TTS adapter used for playback.
            silence_timeout_ms: How many ms of consecutive silence after speech
                triggers end-of-utterance detection (default 800 ms).
            pre_speech_pad_ms: How many ms of audio before the first speech
                frame to include in the transcription buffer, so the very first
                syllable isn't clipped (default 200 ms).
            max_duration_s: Hard cap on recording time per utterance. If no
                speech is detected within this window a RuntimeError is raised
                (default 60 s).
        """
        self.vad = vad
        self.stt = stt
        self.tts = tts
        self._silence_timeout_ms = silence_timeout_ms
        self._pre_speech_pad_ms = pre_speech_pad_ms
        self._max_duration_s = max_duration_s

    @property
    def _sample_rate(self) -> int:
        return self.vad.config.sample_rate

    @property
    def _chunk_samples(self) -> int:
        return int(self._sample_rate * self._CHUNK_MS / 1000)

    def _encode_wav(self, pcm_frames: list[bytes]) -> bytes:
        """Wrap raw 16-bit mono PCM frames in a WAV container.

        Args:
            pcm_frames: List of raw PCM byte strings captured from the mic.

        Returns:
            WAV-encoded bytes ready to pass to an STT adapter.
        """
        buf = io.BytesIO()
        with wave.open(buf, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)  # 16-bit = 2 bytes per sample
            wf.setframerate(self._sample_rate)
            for frame in pcm_frames:
                wf.writeframes(frame)
        return buf.getvalue()

    async def listen(self) -> str:
        """Record from the microphone until speech ends, then transcribe.

        Recording state machine:
        1. WAITING  — accumulate a rolling pre-speech pad; no output yet.
        2. SPEAKING — flush the pre-pad into the output buffer; keep recording.
        3. AFTER_SPEECH — keep recording while counting consecutive silent
           chunks; once the count reaches silence_timeout_ms, stop.

        The microphone read (sounddevice) is blocking, so it runs in a thread
        executor to avoid blocking the async event loop.

        Returns:
            Transcribed text string.

        Raises:
            RuntimeError: If max_duration_s elapses with no speech detected.
        """
        silence_chunks = max(1, self._silence_timeout_ms // self._CHUNK_MS)
        pad_chunks = max(1, self._pre_speech_pad_ms // self._CHUNK_MS)
        max_chunks = int(self._max_duration_s * 1000 / self._CHUNK_MS)

        pre_pad: deque[bytes] = deque(maxlen=pad_chunks)
        speech_frames: list[bytes] = []
        trailing_silence = 0
        speech_detected = False

        loop = asyncio.get_running_loop()

        with sd.InputStream(
            samplerate=self._sample_rate, channels=1, dtype="int16"
        ) as stream:
            for _ in range(max_chunks):
                data, _ = await loop.run_in_executor(
                    None, stream.read, self._chunk_samples
                )
                chunk_bytes = data.tobytes()

                is_speech = await self.vad.is_speech(chunk_bytes)

                if not speech_detected:
                    if is_speech:
                        # Flush the pre-pad first (without the current chunk),
                        # then add the current chunk so older pad frames aren't evicted.
                        speech_detected = True
                        speech_frames.extend(pre_pad)
                        speech_frames.append(chunk_bytes)
                        pre_pad.clear()
                    else:
                        pre_pad.append(chunk_bytes)
                else:
                    speech_frames.append(chunk_bytes)
                    if is_speech:
                        trailing_silence = 0
                    else:
                        trailing_silence += 1
                        if trailing_silence >= silence_chunks:
                            break

        if not speech_frames:
            raise RuntimeError(
                f"No speech detected within {self._max_duration_s}s."
            )

        return await self.stt.transcribe(self._encode_wav(speech_frames))

    async def speak(self, text: str) -> None:
        """Synthesise text and play it through the speakers.

        Args:
            text: The text to speak aloud.
        """
        await self.tts.speak(text)
