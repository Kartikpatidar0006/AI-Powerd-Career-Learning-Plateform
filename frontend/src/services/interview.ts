/**
 * Interview Agent Service API client.
 *
 * Wraps /interview/sessions/* API Gateway routes.
 * Handles session retrieval, start, resume, answer submission,
 * and client-side proctoring event reporting.
 */

import axios from 'axios';
import apiClient from './api';
import type {
  AnswerSubmissionResponse,
  InterviewResumeResponse,
  InterviewSessionResponse,
  InterviewStartResponse,
  ProctoringEventCreate,
  ProctoringEventSubmissionResponse,
  ProctoringEventType,
  SubmitAnswerRequest,
} from '../types/interview';

/**
 * Structured API Error class for interview endpoints, enabling
 * precise UI handling for 404, 409, 429, and 503 responses.
 */
export class InterviewApiError extends Error {
  statusCode: number;
  detail: string;
  code: 'NOT_FOUND' | 'CONFLICT' | 'SERVICE_UNAVAILABLE' | 'RATE_LIMITED' | 'UNAUTHORIZED' | 'UNKNOWN';

  constructor(statusCode: number, detail: string) {
    super(detail);
    this.name = 'InterviewApiError';
    this.statusCode = statusCode;
    this.detail = detail;

    switch (statusCode) {
      case 404:
        this.code = 'NOT_FOUND';
        break;
      case 409:
        this.code = 'CONFLICT';
        break;
      case 503:
        this.code = 'SERVICE_UNAVAILABLE';
        break;
      case 429:
        this.code = 'RATE_LIMITED';
        break;
      case 401:
        this.code = 'UNAUTHORIZED';
        break;
      default:
        this.code = 'UNKNOWN';
    }
  }

  isConflict(): boolean {
    return this.statusCode === 409;
  }

  isNotFound(): boolean {
    return this.statusCode === 404;
  }

  isUnavailable(): boolean {
    return this.statusCode === 503;
  }

  isRateLimited(): boolean {
    return this.statusCode === 429;
  }
}

function parseError(error: unknown, fallbackMessage: string): InterviewApiError {
  if (axios.isAxiosError(error)) {
    const status = error.response?.status ?? 500;
    const detail =
      (error.response?.data as { detail?: string })?.detail ||
      error.message ||
      fallbackMessage;
    return new InterviewApiError(status, detail);
  }
  return new InterviewApiError(500, error instanceof Error ? error.message : fallbackMessage);
}

/**
 * Fetch the interview session status for a specific task.
 * Returns null if the session does not exist (404 — e.g. task not yet evaluated).
 */
export async function getSession(taskId: string): Promise<InterviewSessionResponse | null> {
  try {
    const response = await apiClient.get<InterviewSessionResponse>(
      `/interview/sessions/${taskId}`
    );
    return response.data;
  } catch (error: unknown) {
    if (axios.isAxiosError(error) && error.response?.status === 404) {
      return null;
    }
    throw parseError(error, 'Failed to fetch interview session.');
  }
}

/**
 * Start an AVAILABLE interview session.
 * Generates and returns the first question turn.
 *
 * @throws InterviewApiError (409 if expired/completed/already in progress, 503 if LLM busy)
 */
export async function startSession(taskId: string): Promise<InterviewStartResponse> {
  try {
    const response = await apiClient.post<InterviewStartResponse>(
      `/interview/sessions/${taskId}/start`
    );
    return response.data;
  } catch (error: unknown) {
    throw parseError(error, 'Failed to start interview session.');
  }
}

/**
 * Resume an in-progress interview session.
 * Returns the session and full turn transcript history.
 *
 * @throws InterviewApiError (409 if session is not IN_PROGRESS, 404 if not found)
 */
export async function resumeSession(taskId: string): Promise<InterviewResumeResponse> {
  try {
    const response = await apiClient.get<InterviewResumeResponse>(
      `/interview/sessions/${taskId}/resume`
    );
    return response.data;
  } catch (error: unknown) {
    throw parseError(error, 'Failed to resume interview session.');
  }
}

/**
 * Submit an answer to the current active turn.
 * Safely persists the answer first, then returns the follow-up question or completion summary.
 *
 * @throws InterviewApiError (409 if session not in progress, 503 if LLM generation failed)
 */
export async function submitAnswer(
  taskId: string,
  answerText: string,
  durationSeconds: number = 0.0
): Promise<AnswerSubmissionResponse> {
  try {
    const payload: SubmitAnswerRequest = {
      answer_text: answerText,
      duration_seconds: durationSeconds,
    };
    const response = await apiClient.post<AnswerSubmissionResponse>(
      `/interview/sessions/${taskId}/answer`,
      payload
    );
    return response.data;
  } catch (error: unknown) {
    throw parseError(error, 'Failed to submit interview answer.');
  }
}

/**
 * Log a client-side proctoring violation event (tab blur, fullscreen exit, etc.).
 * Atomically increments violation count and terminates session if threshold is reached.
 * (Stubbed/ready for Task 7c wiring).
 *
 * @throws InterviewApiError (409 if session not in progress, 429 if rate limit exceeded)
 */
export async function submitProctoringEvent(
  taskId: string,
  eventType: ProctoringEventType,
  turnNumber?: number | null
): Promise<ProctoringEventSubmissionResponse> {
  try {
    const payload: ProctoringEventCreate = {
      event_type: eventType,
      turn_number_at_event: turnNumber ?? null,
    };
    const response = await apiClient.post<ProctoringEventSubmissionResponse>(
      `/interview/sessions/${taskId}/proctoring-event`,
      payload
    );
    return response.data;
  } catch (error: unknown) {
    throw parseError(error, 'Failed to log proctoring event.');
  }
}
