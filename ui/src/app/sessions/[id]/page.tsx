import { SessionClient } from "./session-client";

// Next 16: params is a Promise in dynamic routes — await it in the async server component.
export default async function SessionPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <SessionClient id={id} />;
}
