/**
 * Evaluator Agent Service API (Agent 3).
 *
 * Wraps /evaluations/* gateway calls.
 * Used by DailyTaskPage to poll for evaluation results after submission.
 */

import apiClient from './api';

// ── Types ─────────────────────────────────────────────────────────

export interface CheckResultResponse {
  check_name: string;
  passed: boolean;
  score_contribution: number;
  weight_pct: number;
  detail: string;
}

export type EvaluationStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED' | 'FAILED';

export interface EvaluationResult {
  id: string;
  task_id: string;
  user_id: string;
  github_repo_url: string;
  status: EvaluationStatus;
  final_score: number | null;
  passed: boolean | null;
  deterministic_score: number | null;
  deterministic_checks: CheckResultResponse[] | null;
  feedback_summary: string | null;
  llm_strengths: string[] | null;
  llm_weaknesses: string[] | null;
  llm_suggestions: string[] | null;
  error_detail: string | null;
  created_at: string;
  completed_at: string | null;
}

// ── API ────────────────────────────────────────────────────────────

export async function getEvaluationForTask(taskId: string): Promise<EvaluationResult | null> {
  try {
    const response = await apiClient.get<EvaluationResult>(`/evaluations/${taskId}`);
    return response.data;
  } catch (error: any) {
    if (error.response?.status === 404) {
      return null; // No evaluation yet
    }
    throw error;
  }
}

/**
 * Poll evaluation until completed or failed (max attempts).
 * Returns the final EvaluationResult or null on timeout.
 *
 * @param taskId Task UUID string
 * @param maxAttempts Max poll attempts (default 30 = 30s with 1s interval)
 * @param intervalMs Poll interval in ms (default 2000ms)
 */
export async function pollEvaluation(
  taskId: string,
  maxAttempts = 30,
  intervalMs = 2000,
): Promise<EvaluationResult | null> {
  for (let i = 0; i < maxAttempts; i++) {
    await new Promise((r) => setTimeout(r, intervalMs));
    const result = await getEvaluationForTask(taskId);
    if (result && (result.status === 'COMPLETED' || result.status === 'FAILED')) {
      return result;
    }
  }
  return null;
}
