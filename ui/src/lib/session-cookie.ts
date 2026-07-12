// Persist the active session id in a browser cookie (30 days) so a reopen resumes it.

const COOKIE = "storyteller_session";
const MAX_AGE = 60 * 60 * 24 * 30; // 30 days

export function saveSessionCookie(id: string): void {
  if (typeof document === "undefined") return;
  document.cookie = `${COOKIE}=${encodeURIComponent(id)}; path=/; max-age=${MAX_AGE}; samesite=lax`;
}

export function readSessionCookie(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.match(new RegExp(`(?:^|; )${COOKIE}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

export function clearSessionCookie(): void {
  if (typeof document === "undefined") return;
  document.cookie = `${COOKIE}=; path=/; max-age=0`;
}
