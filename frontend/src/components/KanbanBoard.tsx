"use client";

import { useEffect, useMemo, useState } from "react";
import {
  DndContext,
  DragOverlay,
  PointerSensor,
  useSensor,
  useSensors,
  closestCorners,
  type DragEndEvent,
  type DragStartEvent,
} from "@dnd-kit/core";
import { KanbanColumn } from "@/components/KanbanColumn";
import { KanbanCardPreview } from "@/components/KanbanCardPreview";
import { AISidebar } from "@/components/AISidebar";
import { moveCard as computeMove, type BoardData } from "@/lib/kanban";
import * as api from "@/lib/api";

const EMPTY_BOARD: BoardData = { columns: [], cards: {} };

export const KanbanBoard = () => {
  const [board, setBoard] = useState<BoardData>(EMPTY_BOARD);
  const [activeCardId, setActiveCardId] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Load board (redirects to /login/ on 401)
  useEffect(() => {
    api.fetchBoard()
      .then((data) => {
        setBoard(data);
        setReady(true);
      })
      .catch(() => {
        // fetchBoard already redirects on 401; catch any other error silently
      });
  }, []);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } })
  );

  const cardsById = useMemo(() => board.cards, [board.cards]);

  if (!ready) return null;

  // --- Handlers ---

  const handleLogout = async () => {
    await api.logout();
    window.location.href = "/login/";
  };

  const handleDragStart = (event: DragStartEvent) => {
    setActiveCardId(event.active.id as string);
  };

  const handleDragEnd = (event: DragEndEvent) => {
    const { active, over } = event;
    setActiveCardId(null);
    if (!over || active.id === over.id) return;

    const cardId = active.id as string;
    const newColumns = computeMove(board.columns, cardId, over.id as string);
    const targetCol = newColumns.find((c) => c.cardIds.includes(cardId))!;
    const newPosition = targetCol.cardIds.indexOf(cardId);

    const prevBoard = board;
    setBoard({ ...board, columns: newColumns });
    api.moveCard(cardId, targetCol.id, newPosition).catch(() => setBoard(prevBoard));
  };

  const handleRenameColumn = (columnId: string, title: string) => {
    const prevBoard = board;
    setBoard({
      ...board,
      columns: board.columns.map((c) => (c.id === columnId ? { ...c, title } : c)),
    });
    api.renameColumn(columnId, title).catch(() => setBoard(prevBoard));
  };

  const handleAddCard = async (
    columnId: string,
    title: string,
    details: string
  ) => {
    const card = await api.createCard(columnId, title, details);
    setBoard((prev) => ({
      ...prev,
      cards: { ...prev.cards, [card.id]: card },
      columns: prev.columns.map((c) =>
        c.id === columnId ? { ...c, cardIds: [...c.cardIds, card.id] } : c
      ),
    }));
  };

  const handleDeleteCard = (columnId: string, cardId: string) => {
    const prevBoard = board;
    const { [cardId]: _removed, ...remainingCards } = board.cards;
    setBoard({
      ...board,
      cards: remainingCards,
      columns: board.columns.map((c) =>
        c.id === columnId
          ? { ...c, cardIds: c.cardIds.filter((id) => id !== cardId) }
          : c
      ),
    });
    api.deleteCard(cardId).catch(() => setBoard(prevBoard));
  };

  const activeCard = activeCardId ? cardsById[activeCardId] : null;

  return (
    <div className="relative overflow-hidden">
      <div className="pointer-events-none absolute left-0 top-0 h-[420px] w-[420px] -translate-x-1/3 -translate-y-1/3 rounded-full bg-[radial-gradient(circle,_rgba(32,157,215,0.25)_0%,_rgba(32,157,215,0.05)_55%,_transparent_70%)]" />
      <div className="pointer-events-none absolute bottom-0 right-0 h-[520px] w-[520px] translate-x-1/4 translate-y-1/4 rounded-full bg-[radial-gradient(circle,_rgba(117,57,145,0.18)_0%,_rgba(117,57,145,0.05)_55%,_transparent_75%)]" />

      <main className="relative mx-auto flex min-h-screen max-w-[1500px] flex-col gap-10 px-6 pb-16 pt-12">
        <header className="flex flex-col gap-6 rounded-[32px] border border-[var(--stroke)] bg-white/80 p-8 shadow-[var(--shadow)] backdrop-blur">
          <div className="flex flex-wrap items-start justify-between gap-6">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.35em] text-[var(--gray-text)]">
                Single Board Kanban
              </p>
              <h1 className="mt-3 font-display text-4xl font-semibold text-[var(--navy-dark)]">
                Kanban Studio
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-6 text-[var(--gray-text)]">
                Keep momentum visible. Rename columns, drag cards between stages,
                and capture quick notes without getting buried in settings.
              </p>
            </div>
            <div className="flex flex-col items-end gap-3">
              <div className="rounded-2xl border border-[var(--stroke)] bg-[var(--surface)] px-5 py-4">
                <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[var(--gray-text)]">
                  Focus
                </p>
                <p className="mt-2 text-lg font-semibold text-[var(--primary-blue)]">
                  One board. Five columns. Zero clutter.
                </p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setSidebarOpen((o) => !o)}
                  className="rounded-xl border border-[var(--stroke)] bg-[var(--secondary-purple)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-white transition hover:opacity-90"
                >
                  AI Assistant
                </button>
                <button
                  onClick={handleLogout}
                  className="rounded-xl border border-[var(--stroke)] bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--gray-text)] transition hover:border-[var(--secondary-purple)] hover:text-[var(--secondary-purple)]"
                >
                  Sign out
                </button>
              </div>
            </div>
          </div>
          <div className="flex flex-wrap items-center gap-4">
            {board.columns.map((column) => (
              <div
                key={column.id}
                className="flex items-center gap-2 rounded-full border border-[var(--stroke)] px-4 py-2 text-xs font-semibold uppercase tracking-[0.2em] text-[var(--navy-dark)]"
              >
                <span className="h-2 w-2 rounded-full bg-[var(--accent-yellow)]" />
                {column.title}
              </div>
            ))}
          </div>
        </header>

        <DndContext
          sensors={sensors}
          collisionDetection={closestCorners}
          onDragStart={handleDragStart}
          onDragEnd={handleDragEnd}
        >
          <section className="grid gap-6 lg:grid-cols-5">
            {board.columns.map((column) => (
              <KanbanColumn
                key={column.id}
                column={column}
                cards={column.cardIds.map((cardId) => board.cards[cardId])}
                onRename={handleRenameColumn}
                onAddCard={handleAddCard}
                onDeleteCard={handleDeleteCard}
              />
            ))}
          </section>
          <DragOverlay>
            {activeCard ? (
              <div className="w-[260px]">
                <KanbanCardPreview card={activeCard} />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </main>

      <AISidebar
        board={board}
        onBoardUpdate={setBoard}
        isOpen={sidebarOpen}
        onClose={() => setSidebarOpen(false)}
      />
    </div>
  );
};
