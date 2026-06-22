# Database Design

SQLite, stored at `/data/pm.db` inside the Docker container (persisted via the `pm_data` named volume).

---

## Tables

### users

| Column        | Type    | Constraints       |
|---------------|---------|-------------------|
| id            | INTEGER | PK, autoincrement |
| username      | TEXT    | NOT NULL, UNIQUE  |
| password_hash | TEXT    | NOT NULL          |

Stores one row per user. For the MVP, only `user` exists and credentials are validated in code. `password_hash` is included for future real authentication.

---

### boards

| Column  | Type    | Constraints              |
|---------|---------|--------------------------|
| id      | INTEGER | PK, autoincrement        |
| user_id | INTEGER | NOT NULL, FK → users.id  |
| title   | TEXT    | NOT NULL                 |

One board per user for the MVP (enforced at the application layer). The board title is not currently exposed in the UI but is stored for future use.

---

### columns

| Column   | Type    | Constraints              |
|----------|---------|--------------------------|
| id       | INTEGER | PK, autoincrement        |
| board_id | INTEGER | NOT NULL, FK → boards.id |
| title    | TEXT    | NOT NULL                 |
| position | INTEGER | NOT NULL                 |

`position` is a 0-based integer used to order columns on the board. Five columns are seeded on first run.

---

### cards

| Column    | Type    | Constraints               |
|-----------|---------|---------------------------|
| id        | INTEGER | PK, autoincrement         |
| column_id | INTEGER | NOT NULL, FK → columns.id |
| title     | TEXT    | NOT NULL                  |
| details   | TEXT    |                           |
| position  | INTEGER | NOT NULL                  |

`position` is 0-based within a column. After any move or delete, positions are compacted to `0, 1, 2 ...` with no gaps.

---

## Relationships

```
users
  └── boards (one per user for MVP)
        └── columns (5 seeded, can be renamed)
              └── cards (zero or more per column)
```

---

## Seed data

On first run (`init_db()`):
1. Insert `user` with a stored password hash
2. Insert one board titled `My Board` for that user
3. Insert 5 columns: `Backlog`, `To Do`, `In Progress`, `In Review`, `Done`
4. No cards seeded — the board starts empty

---

## Design decisions

- **SQLite over Postgres** — runs without a separate service, persists via Docker volume, sufficient for single-user local MVP
- **Integer positions** — simple and fast for the small card counts expected; compacted after mutations to stay clean
- **No soft deletes** — cards and columns are hard-deleted; no need for audit trails in the MVP
- **One board per user** — enforced in application logic, not via a unique constraint, to leave the door open for multi-board future
