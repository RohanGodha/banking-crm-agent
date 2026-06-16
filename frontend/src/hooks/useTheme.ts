import { useCallback, useEffect, useState } from 'react';
import { applyTheme, getInitialTheme, getStoredTheme, type Theme } from '@/lib/theme';

/**
 * Theme state with localStorage persistence. Falls back to the OS preference
 * and live-follows it until the user makes an explicit choice.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<Theme>(() => getInitialTheme());

  useEffect(() => {
    applyTheme(theme);
  }, [theme]);

  // Follow the OS preference until the user explicitly picks a theme.
  useEffect(() => {
    if (getStoredTheme()) return;
    const mq = window.matchMedia('(prefers-color-scheme: light)');
    const onChange = (e: MediaQueryListEvent) => {
      if (!getStoredTheme()) setThemeState(e.matches ? 'light' : 'dark');
    };
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  const setTheme = useCallback((t: Theme) => setThemeState(t), []);
  const toggle = useCallback(
    () => setThemeState((t) => (t === 'dark' ? 'light' : 'dark')),
    [],
  );

  return { theme, setTheme, toggle };
}
