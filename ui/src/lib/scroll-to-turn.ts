// Tiny cross-component bridge: the Memory Inspector (right column) asks the ChatArea
// (center column) to scroll to a turn, without prop-drilling through the Workspace.

const EVENT = "storyteller:scroll-to-turn";

export function scrollChatToTurn(turn: number): void {
  if (typeof window === "undefined") return;
  window.dispatchEvent(new CustomEvent<number>(EVENT, { detail: turn }));
}

export function onScrollToTurn(handler: (turn: number) => void): () => void {
  const listener = (event: Event) => handler((event as CustomEvent<number>).detail);
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}
