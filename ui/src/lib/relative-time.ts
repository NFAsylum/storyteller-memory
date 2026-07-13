// Relative timestamp in pt-BR ("agora", "5 min atrás", "ontem", "3 dias atrás").
// `now` is injectable so it can be tested deterministically.

export function relativeTime(iso: string, now: number = Date.now()): string {
  const seconds = Math.round((now - new Date(iso).getTime()) / 1000);
  if (seconds < 45) return "agora";
  const minutes = Math.round(seconds / 60);
  if (minutes < 60) return `${minutes} min atrás`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `${hours} h atrás`;
  const days = Math.round(hours / 24);
  return days === 1 ? "ontem" : `${days} dias atrás`;
}
