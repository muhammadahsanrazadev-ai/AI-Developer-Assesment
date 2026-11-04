import { Injectable, signal } from '@angular/core';

/** localStorage key. The inline script in index.html reads the same key before bootstrap. */
export const THEME_STORAGE_KEY = 'avi-theme';

export function preferredDark(): boolean {
  const stored = localStorage.getItem(THEME_STORAGE_KEY);
  if (stored === 'dark' || stored === 'light') {
    return stored === 'dark';
  }
  return window.matchMedia('(prefers-color-scheme: dark)').matches;
}

export function applyStoredTheme(): void {
  document.documentElement.classList.toggle('dark', preferredDark());
}

@Injectable({ providedIn: 'root' })
export class ThemeService {
  readonly dark = signal(preferredDark());

  toggle(): void {
    const next = !this.dark();
    this.dark.set(next);
    document.documentElement.classList.toggle('dark', next);
    localStorage.setItem(THEME_STORAGE_KEY, next ? 'dark' : 'light');
  }
}
