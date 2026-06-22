import type { BoardData, Card } from "./kanban";

async function request(path: string, init?: RequestInit): Promise<Response> {
  const resp = await fetch(path, init);
  if (resp.status === 401) {
    window.location.href = "/login/";
    throw new Error("unauthenticated");
  }
  if (!resp.ok) throw new Error(`API error ${resp.status}`);
  return resp;
}

// Strip frontend prefixes before sending numeric IDs to the backend.
const colNum = (id: string) => id.replace(/^col-/, "");
const cardNum = (id: string) => id.replace(/^card-/, "");

// Add col-/card- prefixes to raw backend board response.
function prefixBoard(raw: {
  columns: { id: string; title: string; cardIds: string[] }[];
  cards: Record<string, { title: string; details: string }>;
}): BoardData {
  const columns = raw.columns.map((col) => ({
    id: `col-${col.id}`,
    title: col.title,
    cardIds: col.cardIds.map((id) => `card-${id}`),
  }));
  const cards: Record<string, Card> = {};
  for (const [id, card] of Object.entries(raw.cards)) {
    const prefixedId = `card-${id}`;
    cards[prefixedId] = { id: prefixedId, title: card.title, details: card.details };
  }
  return { columns, cards };
}

export async function fetchBoard(): Promise<BoardData> {
  const resp = await request("/api/board");
  return prefixBoard(await resp.json());
}

export async function renameColumn(id: string, title: string): Promise<void> {
  await request(`/api/board/columns/${colNum(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ title }),
  });
}

export async function createCard(
  columnId: string,
  title: string,
  details: string
): Promise<Card> {
  const resp = await request("/api/board/cards", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ column_id: parseInt(colNum(columnId)), title, details }),
  });
  const data = await resp.json();
  return { id: `card-${data.id}`, title: data.title, details: data.details };
}

export async function moveCard(
  cardId: string,
  columnId: string,
  position: number
): Promise<void> {
  await request(`/api/board/cards/${cardNum(cardId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ column_id: parseInt(colNum(columnId)), position }),
  });
}

export async function deleteCard(cardId: string): Promise<void> {
  await request(`/api/board/cards/${cardNum(cardId)}`, { method: "DELETE" });
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", { method: "POST" });
}

export type ChatMessage = { role: "user" | "assistant"; content: string };

export async function aiChat(
  message: string,
  history: ChatMessage[]
): Promise<{ reply: string; board: BoardData }> {
  const resp = await request("/api/ai/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message, history }),
  });
  const raw = await resp.json();
  return { reply: raw.reply, board: prefixBoard(raw.board) };
}
