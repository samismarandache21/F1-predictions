/**
 * Backend base URL. docker-compose maps the api service to localhost:8000
 * (see docker-compose.yml). A real environment-based config
 * (fileReplacements per Angular build configuration) is a nice-to-have,
 * not needed for the M1 demo — a single constant is simpler to get right
 * without being able to run a build to check it here (Node isn't
 * installed in this environment; see the T9 summary).
 */
export const API_BASE_URL = 'http://localhost:8000';

export function wsUrl(path: string): string {
  return API_BASE_URL.replace(/^http/, 'ws') + path;
}
