// Typed API client — all fetch calls go through here.

export interface SessionRow {
  id: string;
  created_at: string;
  interview_type: string;
  difficulty: string;
  avg_overall: number | null;
}

export interface QuestionPayload {
  index: number;
  total: number;
  id: string;
  text: string;
  is_follow_up: boolean;
}

export interface PlanMeta {
  id: string;
  title: string;
  interview_type: string;
  difficulty: string;
  num_questions: number;
  summary: string;
}

export interface SkillGap {
  skill: string;
  required_level: "high" | "medium" | "low";
  resume_level: "strong" | "partial" | "missing";
}

export interface GeneratedPlan {
  generated_at: string;
  jd_source: string;
  resume_source: string;
  interview_type: string;
  difficulty: string;
  num_questions: number;
  time_limit_per_question: number;
  persona: string;
  language: string;
  skills_analysis: {
    required_skills: string[];
    skill_gaps: SkillGap[];
    summary: string;
  };
  questions: {
    id: string;
    text: string;
    tags: string[];
    difficulty: string;
    follow_up: string;
    rationale: string;
  }[];
}

export interface StartRequest {
  type: string;
  difficulty: string;
  num_questions: number;
  persona: string;
  plan_id?: string;
  plan_data?: GeneratedPlan;
}

export interface StartResponse {
  session_id: string;
  question: QuestionPayload;
}

export interface AnswerResponse {
  status: "next_question" | "follow_up" | "complete";
  question?: QuestionPayload;
  session_id?: string;
  transcript?: string;
}

export interface AnswerScore {
  question_id: string;
  question_text: string;
  answer: string;
  star_score: number;
  relevance_score: number;
  clarity_score: number;
  overall: number;
  feedback: string;
}

export interface ScoreReport {
  scores: AnswerScore[];
  average_overall: number;
  average_star: number;
  average_relevance: number;
  average_clarity: number;
  summary: string;
}

export interface Turn {
  question: {
    id: string;
    text: string;
    tags: string[];
    difficulty: string;
    follow_up: string;
  };
  answer: string;
  follow_up_asked: boolean;
  follow_up_answer: string;
}

export interface SessionDetail {
  session: {
    config: {
      type: string;
      difficulty: string;
      num_questions: number;
      persona: string;
      mode: string;
    };
    turns: Turn[];
  };
  report: ScoreReport;
}

// ---------------------------------------------------------------------------

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, init);
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  listSessions: () => request<SessionRow[]>("/api/sessions"),

  getSession: (id: string) => request<SessionDetail>(`/api/sessions/${id}`),

  listPlans: () => request<PlanMeta[]>("/api/plans"),

  generatePlan: (formData: FormData) =>
    request<GeneratedPlan>("/api/plans/generate", {
      method: "POST",
      body: formData,
    }),

  startInterview: (body: StartRequest) =>
    request<StartResponse>("/api/interview/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),

  submitAnswer: (sessionId: string, audioBlob: Blob): Promise<AnswerResponse> => {
    const form = new FormData();
    form.append("audio", audioBlob, "audio.webm");
    return request<AnswerResponse>(`/api/interview/${sessionId}/answer`, {
      method: "POST",
      body: form,
    });
  },

  ttsUrl: (text: string) =>
    `/api/interview/tts?text=${encodeURIComponent(text)}`,
};
