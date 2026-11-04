import { HttpErrorResponse } from '@angular/common/http';
import { Observable, throwError } from 'rxjs';

import { environment } from '../../../environments/environment';

export interface ApiError {
  status: number;
  code: string;
  message: string;
  details: Record<string, string>;
}

interface ApiErrorBody {
  error?: { code?: string; message?: string; details?: Record<string, string> };
}

const FALLBACK_MESSAGES: Record<number, string> = {
  400: 'The request was invalid. Please check your input.',
  404: 'The requested item could not be found.',
  409: 'This action conflicts with the current state. Please try again shortly.',
  500: 'The server ran into a problem. Please try again.',
  502: 'The AI provider did not respond correctly. Please try again.',
};

export function toApiError(error: unknown): ApiError {
  if (!(error instanceof HttpErrorResponse)) {
    return { status: 0, code: 'unknown_error', message: 'Something went wrong. Please try again.', details: {} };
  }
  if (error.status === 0) {
    return {
      status: 0,
      code: 'network_error',
      message: `Cannot reach the API at ${environment.apiUrl}. Make sure the backend is running.`,
      details: {},
    };
  }
  const body = (error.error ?? {}) as ApiErrorBody;
  return {
    status: error.status,
    code: body.error?.code ?? 'http_error',
    message: body.error?.message ?? FALLBACK_MESSAGES[error.status] ?? `Request failed (${error.status}).`,
    details: body.error?.details ?? {},
  };
}

/** Use inside `catchError` so every service rethrows the same typed error shape. */
export function rethrowApiError(error: unknown): Observable<never> {
  return throwError(() => toApiError(error));
}
