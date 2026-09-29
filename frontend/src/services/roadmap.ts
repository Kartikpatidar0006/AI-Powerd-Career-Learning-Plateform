/**
 * Roadmap and Tasks API service.
 *
 * Wraps all /roadmap/* and /tasks/* gateway calls.
 */

import apiClient from './api';

// ── Types ─────────────────────────────────────────────────────────

export interface MilestoneProgress {
  order: number;
  title: string;
  description: string;
  target_skills: string[];
  estimated_days: number;
  difficulty_band: number;
  success_criteria: string[];
  tasks_completed: number;
  tasks_planned: number;
  state: 'completed' | 'current' | 'upcoming';
}

export interface Roadmap {
  id: string;
  user_id: string;
  milestones: MilestoneProgress[];
  status: string;
  created_at: string;
  profile_snapshot: Record<string, unknown>;
}

export type TaskStatus = 'ASSIGNED' | 'IN_PROGRESS' | 'SUBMITTED' | 'EVALUATING' | 'EVALUATED';

export interface Task {
  id: string;
  user_id: string;
  roadmap_id: string;
  milestone_order: number;
  sequence_number: number;
  title: string;
  description: string;
  requirements: string[];
  acceptance_criteria: string[];
  skills_targeted: string[];
  difficulty: number;
  estimated_hours: number;
  starter_hint: string | null;
  status: TaskStatus;
  github_repo_url: string | null;
  started_at?: string | null;
  submitted_at: string | null;
  evaluated_at: string | null;
  evaluation_summary: Record<string, unknown> | null;
  created_at: string;
}

export interface NextTaskResponse {
  status: 'task_assigned' | 'roadmap_completed';
  task: Task | null;
}

export interface TaskListResponse {
  tasks: Task[];
  total: number;
  page: number;
  page_size: number;
}

// ── Roadmap API ────────────────────────────────────────────────────

export async function generateRoadmap(): Promise<Roadmap> {
  try {
    const response = await apiClient.post<Roadmap>('/roadmap/generate');
    return response.data;
  } catch (error: any) {
    const status = error.response?.status;
    // On 504 (timeout) or 409 (already generating/exists), re-check /roadmap/me
    if (status === 504 || status === 409) {
      try {
        const existing = await getMyRoadmap();
        if (existing && existing.id) {
          return existing;
        }
      } catch {
        // Fallback failed, throw original error
      }
    }
    throw error;
  }
}

export async function getMyRoadmap(): Promise<Roadmap> {
  const response = await apiClient.get<Roadmap>('/roadmap/me');
  return response.data;
}

// ── Tasks API ──────────────────────────────────────────────────────

export async function getNextTask(): Promise<NextTaskResponse> {
  try {
    const response = await apiClient.post<NextTaskResponse>('/tasks/next');
    return response.data;
  } catch (error: any) {
    const status = error.response?.status;
    // On 504 (timeout) or 409 (active task exists/concurrent create), re-check /tasks/current
    if (status === 504 || status === 409) {
      try {
        const currentTask = await getCurrentTask();
        if (currentTask && currentTask.id) {
          return {
            status: 'task_assigned',
            task: currentTask,
          };
        }
      } catch {
        // Fallback failed, throw original error
      }
    }
    throw error;
  }
}

export async function getCurrentTask(): Promise<Task | null> {
  const response = await apiClient.get<Task | null>('/tasks/current');
  return response.data;
}

export async function getTaskHistory(page = 1, pageSize = 20): Promise<TaskListResponse> {
  const response = await apiClient.get<TaskListResponse>('/tasks', {
    params: { page, page_size: pageSize },
  });
  return response.data;
}

export async function getTaskById(taskId: string): Promise<Task> {
  const response = await apiClient.get<Task>(`/tasks/${taskId}`);
  return response.data;
}

export async function startTask(taskId: string): Promise<Task> {
  const response = await apiClient.post<Task>(`/tasks/${taskId}/start`);
  return response.data;
}

export async function submitTask(taskId: string, githubRepoUrl: string): Promise<Task> {
  const response = await apiClient.post<Task>(`/tasks/${taskId}/submit`, {
    github_repo_url: githubRepoUrl,
  });
  return response.data;
}
