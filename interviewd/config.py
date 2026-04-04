from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class STTConfig(BaseModel):
    # Literal used here — built-in providers are a closed set (groq, whisper_local).
    # When a contributor adds a new built-in STT adapter, they update this Literal
    # as part of the same PR. That one-line diff makes the addition explicit and
    # reviewable. See docs/decisions/001-adapter-strategy.md.
    provider: Literal["groq", "whisper_local"] = "groq"
    model: str = "whisper-large-v3-turbo"
    language: str = "en"


class TTSConfig(BaseModel):
    # Same reasoning as STTConfig.provider — closed set of built-in providers.
    # See docs/decisions/001-adapter-strategy.md.
    provider: Literal["edge_tts", "piper"] = "edge_tts"
    voice: str = "en-US-AriaNeural"


class VADConfig(BaseModel):
    # Same reasoning as STTConfig.provider — closed set of built-in providers.
    # See docs/decisions/001-adapter-strategy.md.
    provider: Literal["silero"] = "silero"
    threshold: float = 0.5
    sample_rate: int = 16000


class LLMConfig(BaseModel):
    # Plain str — LiteLLM supports 100+ providers via config alone so this is
    # genuinely open-ended. Validation happens at adapter lookup time.
    # See docs/decisions/001-adapter-strategy.md.
    provider: str = "litellm"
    model: str = "gemini/gemini-1.5-flash"
    temperature: float = 0.7
    max_tokens: int = 1024
    streaming: bool = True


class InterviewConfig(BaseModel):
    # Literal used here — interview types and difficulty levels are a closed,
    # product-defined set. Adding a new type requires changes to the question
    # bank and engine logic, not just an adapter.
    type: Literal["behavioral", "technical", "hr", "system_design"] = "behavioral"
    difficulty: Literal["entry", "mid", "senior", "staff"] = "mid"
    num_questions: int = 5
    time_limit_per_question: int = 120  # seconds
    persona: Literal["friendly", "neutral", "adversarial"] = "neutral"
    language: str = "en"


class PathsConfig(BaseModel):
    question_bank: str = "config/questions"
    session_store: str = ".interviewd/sessions"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="INTERVIEWD_",
        env_nested_delimiter="__",
        env_file=".env",
        env_file_encoding="utf-8",
    )

    stt: STTConfig = STTConfig()
    tts: TTSConfig = TTSConfig()
    vad: VADConfig = VADConfig()
    llm: LLMConfig = LLMConfig()
    interview: InterviewConfig = InterviewConfig()
    paths: PathsConfig = PathsConfig()

    log_level: str = "INFO"


def load_settings(config_path: str = "config/default.yaml") -> Settings:
    path = Path(config_path)
    if not path.exists():
        return Settings()

    with path.open() as f:
        data = yaml.safe_load(f)

    return Settings.model_validate(data)
