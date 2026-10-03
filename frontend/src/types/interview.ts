/**
 * Interview Agent types mirroring interview-agent-service backend schemas.
 *
 * Types for interview session lifecycle, turns, dynamic questions,
 * performance summaries, and proctoring integrity events.
 */

export type InterviewSessionStatus =
  | 'AVAILABLE'
  | 'IN_PROGRESS'
  | 'COMPLETED'
  | 'EXPIRED'
  | 'TERMINATED_VIOLATION';

export type ProctoringEventType =
  | 'TAB_BLUR'
  | 'FULLSCREEN_EXIT'
  | 'COPY_PASTE_ATTEMPT'
  | 'DEVTOOLS_DETECTED';

export interface OverallPerformanceSummary {
  communication_clarity: number;
  technical_depth: number;
  confidence_signals: number;
  overall_score: number;
  summary: string;
  key_strengths: string[];
  areas_for_improvement: string[];
}

export interface InterviewSessionResponse {
  id: string;
  user_id: string;
  task_id: string;
  evaluation_id: string;
  status: InterviewSessionStatus;
  available_from: string;
  expires_at: string;
  started_at: string | null;
  completed_at: string | null;
  violation_count: number;
  termination_reason: string | null;
  overall_performance_summary: OverallPerformanceSummary | null;
  created_at: string;
  time_remaining_seconds: number;
}

export interface InterviewTurnResponse {
  id: string;
  session_id: string;
  turn_number: number;
  question_text: string;
  answer_text: string | null;
  question_context: Record<string, unknown>;
  answer_duration_seconds: number | null;
  follow_up_of: string | null;
  created_at: string;
  answered_at: string | null;
}

export interface InterviewStartResponse {
  session: InterviewSessionResponse;
  first_question: InterviewTurnResponse;
  is_closing: boolean;
  id: string;
  user_id: string;
  task_id: string;
  evaluation_id: string;
  status: InterviewSessionStatus;
  available_from: string;
  expires_at: string;
  started_at: string | null;
  completed_at: string | null;
  violation_count: number;
  termination_reason: string | null;
  overall_performance_summary: OverallPerformanceSummary | null;
  created_at: string;
  time_remaining_seconds: number;
}

export interface InterviewResumeResponse {
  session: InterviewSessionResponse;
  turns: InterviewTurnResponse[];
  id: string;
  user_id: string;
  task_id: string;
  evaluation_id: string;
  status: InterviewSessionStatus;
  available_from: string;
  expires_at: string;
  started_at: string | null;
  completed_at: string | null;
  violation_count: number;
  termination_reason: string | null;
  overall_performance_summary: OverallPerformanceSummary | null;
  created_at: string;
  time_remaining_seconds: number;
}

export interface SubmitAnswerRequest {
  answer_text: string;
  duration_seconds: number;
}

export interface AnswerSubmissionResponse {
  session: InterviewSessionResponse;
  answered_turn: InterviewTurnResponse;
  next_turn: InterviewTurnResponse;
  question: InterviewTurnResponse;
  is_closing: boolean;
  status: string;
  overall_performance_summary: OverallPerformanceSummary | null;
}

export interface ProctoringEventCreate {
  event_type: ProctoringEventType;
  turn_number_at_event?: number | null;
}

export interface ProctoringEventResponse {
  id: string;
  session_id: string;
  event_type: ProctoringEventType;
  timestamp: string;
  turn_number_at_event: number | null;
}

export interface ProctoringEventSubmissionResponse {
  event: ProctoringEventResponse;
  session_status: InterviewSessionStatus;
  violation_count: number;
  max_violations: number;
  terminated: boolean;
  termination_reason: string | null;
}
