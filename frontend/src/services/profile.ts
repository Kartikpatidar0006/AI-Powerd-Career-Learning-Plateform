/**
 * Profile API service.
 *
 * Communicates with the profile agent service via the API Gateway.
 */

import apiClient from './api';
import type { OnboardingFormData, StudentProfile } from '../types/profile';

/**
 * Fetch the authenticated student's profile.
 *
 * @returns StudentProfile object if found.
 * @throws AxiosError with status 404 if profile has not been created.
 */
export async function getMyProfile(): Promise<StudentProfile> {
  const response = await apiClient.get<StudentProfile>('/profile/me');
  return response.data;
}

/**
 * Submit candidate onboarding data to Agent 1 for AI extraction and lock.
 *
 * @param data Onboarding form data.
 * @returns Finalized and locked StudentProfile object.
 */
export async function submitOnboarding(data: OnboardingFormData): Promise<StudentProfile> {
  const response = await apiClient.post<StudentProfile>('/profile/onboarding', data);
  return response.data;
}
