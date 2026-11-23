# TransferPortal

Ethan Davis, ECE465 Final Project

## Project Overview

TransferPortal is a database system for tracking the professional soccer transfer market. It stores leagues, clubs, players, managers and their coaching tenures, player transfers (including free-agent moves), and player contracts. A command-line application lets a user search, view, add, change, and report on that data from a numbered menu, without writing any SQL.

**Intended users:** soccer analysts, scouts, journalists, and fans who want to look up player histories, compare club spending, and keep transfer records up to date.

**Major functionality:** search players; view a player's transfer history and contracts; view a club's league, manager, and current players; list recent and most expensive transfers; add players, clubs, and leagues; update market values; move a club between leagues; record and delete transfers (with contracts, in a transaction); spending and average-fee reports; contracts expiring soon.

## DBMS

**SQLite 3** (a single-file relational database). No server, account, or password is needed. The sample data uses real, publicly reported clubs, players, managers, and transfers (sources are listed in the header of `insert_data.sql`).

## Files

| File | Purpose |
|---|---|
| `erd.png` | Final ER diagram (matches `schema.sql`) |
| `schema.sql` | Creates 7 tables with constraints, 5 indexes, and 3 views |
| `insert_data.sql` | Loads the sample data (103 rows) |
| `queries.sql` | The 9 required query types (run against the final schema and data) |
| `transaction.sql` | Transaction example (new player, transfer, and contract; ends in ROLLBACK) |
| `transferportal_app.py` | The application: menu, input validation, display |
| `db_access.py` | All SQL (parameterized) and the database connection |
| `.gitignore` | Keeps the generated `transferportal.db` out of the repository |

No credentials or secrets are used anywhere, so no `.env` file or configuration template is needed.

## Database Setup

**Required software:** the `sqlite3` command-line shell (any recent version; tested with 3.45).

From the repository folder, run the files in this order:

```
sqlite3 transferportal.db < schema.sql
sqlite3 transferportal.db < insert_data.sql
```

This creates `transferportal.db`. To start over, delete the file and repeat both commands. `insert_data.sql` must run after `schema.sql`. Foreign keys are enforced by the application and by `queries.sql` / `transaction.sql` (each sets `PRAGMA foreign_keys = ON`).

### Running the SQL files

```
sqlite3 -header -column transferportal.db < queries.sql
sqlite3 -header -column -bail transferportal.db < transaction.sql
```

`queries.sql` prints the nine labeled queries (filtering/sorting, INNER JOIN, LEFT JOIN, multi-table join, aggregate, GROUP BY/HAVING, subquery, EXCEPT, view). `transaction.sql` shows row counts before, inside, and after the transaction. It ends with `ROLLBACK`, so the data is unchanged; replace it with `COMMIT` to keep the changes. Both scripts use the literal date 2026-11-02 as "today" so results are repeatable.

## Application Setup

- **Language:** Python 3.8 or newer (tested with 3.12 and 3.13).
- **Packages:** none. Only the standard library (`sqlite3`) is used, so there is nothing to install.
- **Database connection:** the app opens `transferportal.db` in the same folder as the program. No configuration is needed. To use another file, set the optional environment variable `TRANSFERPORTAL_DB` (macOS/Linux: `TRANSFERPORTAL_DB=/path/file.db python3 transferportal_app.py`; Windows PowerShell: `$env:TRANSFERPORTAL_DB = "C:\path\file.db"`).
- **Start the app:**

```
python3 transferportal_app.py
```

(On Windows use `python` or `py`.) If you have not created the database with the `sqlite3` commands above, you can instead run `python3 transferportal_app.py --rebuild`, which deletes `transferportal.db` if it exists, recreates it from `schema.sql` and `insert_data.sql`, and starts the menu. Use `--rebuild` any time to reset the data.

## Major Application Operations

| Category | Menu option | What it does |
|---|---|---|
| Search / browse | 1 Search players | Filter by name, position, minimum market value (all optional) |
| | 4 Ten most recent transfers | Newest first |
| | 5 Most expensive transfers | Top N, all time or last N years |
| Related data | 2 Player profile | Details, transfer history (joins Transfers, Players, Clubs, Leagues), contracts |
| | 3 Club profile | League, current manager (view), current players |
| Add | 6 Add a new player | Rejects duplicates (same name and birth date) |
| | 7 Add a new club or league | Rejects duplicate names |
| Update / delete | 9 Update a player's market value | With confirmation |
| | 8 Move a club to another league | Promotion / relegation |
| | 10 Delete a transfer record | Deletes the transfer and its contract in one transaction |
| Report | 11 Reports | Club spending and income (view); transfers by league with COUNT, SUM, AVG |
| Additional | 12 Record a transfer | Transfer plus optional contract in one transaction; supports free agents |
| | 13 Contracts expiring soon | Contracts ending within N months |

### Example session

1. Option 1: leave name and position blank, enter `100m` as the minimum value.
2. Option 2: type `de gea` to see a history that includes free-agent moves. Option 3: type `inter miami`.
3. Option 6: add a player (e.g. David / Raya, born 1995-09-15, Spain, Goalkeeper, 30m).
4. Option 12: record a move for the new player (type part of a club name, such as `arsenal`).
5. Option 11: view the spending report. Quit, restart, and run option 2 again to confirm the change was saved, or check with `sqlite3 transferportal.db "SELECT * FROM v_transfer_history WHERE player_name LIKE '%Raya%';"`.
6. Enter bad input (letters for an amount, an impossible date, an unknown ID) to see validation messages.

### Free agents

A NULL club in `Transfers` means "free agent" (there is no Free Agent row in `Clubs`). `from_club_id` NULL means the player signed from being a free agent; `to_club_id` NULL means the player left a club as a free agent. CHECK constraints require at least one real club and require any free-agent move to be type `Free` with fee 0. In option 12, type `free agent` (or `free` / `fa`) at a club prompt.

## SQL Safety, Validation, and Errors

- **Parameterized SQL:** every user-supplied value is passed to `sqlite3` with `?` placeholders. The one assembled query (the optional search filters in `db_access.search_players`) joins only fixed condition strings written in the code; user text is always a parameter.
- **Validation:** menu choices, number ranges, non-negative amounts, real calendar dates, required values, known positions and transfer types, unknown IDs, duplicate players, a transfer to the club the player is already at, contract end after start, and wage above 0.
- **Database errors** (duplicate, foreign key, CHECK, NOT NULL) are caught and shown as one plain sentence, not a stack trace.
- **Transactions:** options 12 and 10 each save or remove a transfer and its contract together, and reconnect the player's neighboring transfer history. If any step fails, nothing is saved. Other changes are single statements that commit immediately.

## Database Notes

Tables: Leagues, Clubs, Players, Managers, ManagerTenures, Transfers, Contracts. Views: `v_transfer_history`, `v_current_managers`, `v_club_transfer_balance`. Fees and market values are in euros; weekly wages are in US dollars. Contract end dates reported only as a year use 30 June. Options 5 (last N years) and 13 use the current date, so their results change over time.

## Known Limitations

- It is a single-user, command-line application with no login or roles. There is no web or graphical interface.
- Only transfers between clubs that are in the `Clubs` table are recorded, so a player's other career moves are not included, and the sample data covers a small selection of clubs and players.
- Market values, fees, and wages are publicly reported estimates and are only an approximate snapshot; they are not official figures.
- Clubs in the sample data have no recorded head coach unless they have an open manager tenure, so `queries.sql` query 8 lists most clubs as having a vacancy.
- Contracts are recorded for only a few players in the sample data.
- Editing a transfer is not supported. To fix one, delete it (option 10) and record it again.
