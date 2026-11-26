import { apiRequest } from './client';

export interface LoginResponse {
  token: string;
}

/** `POST /login`: credentials in, JWT out (openapi.yaml, LoginResponse). */
export function loginRequest(email: string, password: string): Promise<LoginResponse> {
  return apiRequest<LoginResponse>('/login', {
    method: 'POST',
    body: { email, password },
  });
}
