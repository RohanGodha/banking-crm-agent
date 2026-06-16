/** Light/dark theme persistence + DOM application. */

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'rmcopilot-theme';

export function getStoredTheme(): Theme | null {
  try {
    const v = localStorage.getItem(STORAGE_KEY);
    return v === 'light' || v === 'dark' ? v : null;
  } catch {
    return null;
  }
}

export function getSystemTheme(): Theme {
  try {
    return window.matchMedia('(prefers-color-scheme: light)').matches ? 'light' : 'dark';
  } catch {
    return 'dark';
  }
}

export function getInitialTheme(): Theme {
  return getStoredTheme() ?? getSystemTheme();
}

/** Apply a theme to <html>, persist it, and sync the mobile browser chrome colour. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  root.classList.toggle('dark', theme === 'dark');
  root.classList.toggle('light', theme === 'light');
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    /* storage unavailable */
  }
  const meta = document.querySelector('meta[name="theme-color"]');
  if (meta) meta.setAttribute('content', theme === 'dark' ? '#0a0d12' : '#f7f8fa');
}

/**
 * Read a theme colour token (e.g. 'accent', 'bg-card') as a usable CSS color,
 * resolved from the current theme's CSS variables. For SVG/Canvas (D3) where
 * Tailwind classes don't apply.
 */
export function themeColor(token: string, fallback = '#3b82f6'): string {
  try {
    const v = getComputedStyle(document.documentElement)
      .getPropertyValue(`--c-${token}`)
      .trim();
    return v ? `rgb(${v})` : fallback;
  } catch {
    return fallback;
  }
}
