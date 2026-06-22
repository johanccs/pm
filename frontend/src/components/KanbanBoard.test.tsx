import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { vi, beforeEach, describe, it, expect } from "vitest";
import { KanbanBoard } from "@/components/KanbanBoard";

// Seed board returned by GET /api/board
const SEED_BOARD = {
  columns: [
    { id: "1", title: "Backlog",     cardIds: [] },
    { id: "2", title: "To Do",       cardIds: [] },
    { id: "3", title: "In Progress", cardIds: [] },
    { id: "4", title: "In Review",   cardIds: [] },
    { id: "5", title: "Done",        cardIds: [] },
  ],
  cards: {},
};

function makeFetch(overrides: Record<string, unknown> = {}) {
  return vi.fn(async (input: RequestInfo | URL) => {
    const url = input.toString();

    if (url.includes("/api/board/cards") && !url.match(/cards\/\d/)) {
      // POST /api/board/cards
      return new Response(
        JSON.stringify(overrides.newCard ?? { id: "42", title: "New card", details: "Notes" }),
        { status: 200 }
      );
    }
    if (url.includes("/api/board/cards/")) {
      // PUT or DELETE /api/board/cards/{id}
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
    if (url.includes("/api/board/columns/")) {
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
    if (url === "/api/board") {
      return new Response(JSON.stringify(overrides.board ?? SEED_BOARD), { status: 200 });
    }
    if (url.includes("/api/auth/logout")) {
      return new Response(JSON.stringify({ ok: true }), { status: 200 });
    }
    if (url.includes("/api/ai/chat")) {
      return new Response(
        JSON.stringify(overrides.aiChat ?? {
          reply: "Done!",
          board: overrides.board ?? SEED_BOARD,
        }),
        { status: 200 }
      );
    }
    return new Response(null, { status: 404 });
  });
}

beforeEach(() => {
  vi.stubGlobal("fetch", makeFetch());
});

describe("KanbanBoard", () => {
  it("renders five columns after loading", async () => {
    render(<KanbanBoard />);
    await waitFor(() =>
      expect(screen.getAllByTestId(/column-/i)).toHaveLength(5)
    );
  });

  it("renames a column (calls API)", async () => {
    render(<KanbanBoard />);
    await waitFor(() => screen.getAllByTestId(/column-/i));
    const column = screen.getAllByTestId(/column-/i)[0];
    const input = within(column).getByLabelText("Column title");
    await userEvent.clear(input);
    await userEvent.type(input, "Sprint 1");
    expect(input).toHaveValue("Sprint 1");
    // API call was made
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/board/columns/"),
      expect.objectContaining({ method: "PUT" })
    );
  });

  it("adds a card by calling POST /api/board/cards", async () => {
    vi.stubGlobal("fetch", makeFetch({ newCard: { id: "99", title: "New card", details: "Notes" } }));
    render(<KanbanBoard />);
    await waitFor(() => screen.getAllByTestId(/column-/i));

    const column = screen.getAllByTestId(/column-/i)[0];
    await userEvent.click(within(column).getByRole("button", { name: /add a card/i }));
    await userEvent.type(within(column).getByPlaceholderText(/card title/i), "New card");
    await userEvent.type(within(column).getByPlaceholderText(/details/i), "Notes");
    await userEvent.click(within(column).getByRole("button", { name: /add card/i }));

    await waitFor(() =>
      expect(within(column).getByText("New card")).toBeInTheDocument()
    );
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      "/api/board/cards",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("opens and closes the AI sidebar", async () => {
    render(<KanbanBoard />);
    await waitFor(() => screen.getAllByTestId(/column-/i));

    // Sidebar should not be visible initially
    expect(screen.queryByRole("heading", { name: /board chat/i })).not.toBeInTheDocument();

    // Open sidebar
    await userEvent.click(screen.getByRole("button", { name: /ai assistant/i }));
    expect(screen.getByRole("heading", { name: /board chat/i })).toBeInTheDocument();

    // Close sidebar
    await userEvent.click(screen.getByRole("button", { name: /close ai sidebar/i }));
    expect(screen.queryByRole("heading", { name: /board chat/i })).not.toBeInTheDocument();
  });

  it("sends a message to the AI and shows reply", async () => {
    vi.stubGlobal(
      "fetch",
      makeFetch({ aiChat: { reply: "I added a card!", board: SEED_BOARD } })
    );
    render(<KanbanBoard />);
    await waitFor(() => screen.getAllByTestId(/column-/i));

    await userEvent.click(screen.getByRole("button", { name: /ai assistant/i }));
    await userEvent.type(screen.getByLabelText(/ai chat input/i), "Add a card");
    await userEvent.click(screen.getByRole("button", { name: /send/i }));

    await waitFor(() =>
      expect(screen.getByText("I added a card!")).toBeInTheDocument()
    );
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      "/api/ai/chat",
      expect.objectContaining({ method: "POST" })
    );
  });

  it("deletes a card by calling DELETE /api/board/cards/{id}", async () => {
    const boardWithCard = {
      columns: [{ id: "1", title: "Backlog", cardIds: ["7"] }, ...SEED_BOARD.columns.slice(1)],
      cards: { "7": { id: "7", title: "To Remove", details: "" } },
    };
    vi.stubGlobal("fetch", makeFetch({ board: boardWithCard }));
    render(<KanbanBoard />);
    await waitFor(() => screen.getByText("To Remove"));

    await userEvent.click(screen.getByRole("button", { name: /delete to remove/i }));

    await waitFor(() =>
      expect(screen.queryByText("To Remove")).not.toBeInTheDocument()
    );
    expect(vi.mocked(fetch)).toHaveBeenCalledWith(
      expect.stringContaining("/api/board/cards/7"),
      expect.objectContaining({ method: "DELETE" })
    );
  });
});
