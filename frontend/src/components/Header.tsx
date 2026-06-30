/**
 * Header bar component — removed per #193.
 *
 * Theme toggle + settings moved to ActionBar;
 * app title moved to bottom footer.
 */

interface HeaderProps {
  onSettingsClick?: () => void;
  onThemeToggle?: () => void;
  isDark?: boolean;
  t: (key: string) => string;
}

/** Header has been removed per #193. Component kept as no-op for API compatibility. */
export function Header(_props: HeaderProps) {
  return null;
}
