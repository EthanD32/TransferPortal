"""db_access.py: all SQL for the TransferPortal application.

Every function takes an open sqlite3 connection. All values that come from the
user are passed as ? placeholders (parameterized SQL), never concatenated into
the SQL text. The only strings built dynamically are WHERE-clause fragments that
are fixed literals chosen by this code (see search_players).
"""

import os
import sqlite3
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# The database location can be changed with the TRANSFERPORTAL_DB environment
# variable. By default it is transferportal.db next to this file.
DB_PATH = Path(os.environ.get("TRANSFERPORTAL_DB", BASE_DIR / "transferportal.db"))


# ----------------------------------------------------------------------------
# Connection and setup
# ----------------------------------------------------------------------------
def connect(path=DB_PATH):
    """Open a connection with foreign keys enforced (SQLite needs this per connection)."""
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def rebuild_database(path=DB_PATH):
    """Delete the database file and recreate it from schema.sql and insert_data.sql."""
    path = Path(path)
    if path.exists():
        path.unlink()
    conn = sqlite3.connect(path)
    try:
        for script in ("schema.sql", "insert_data.sql"):
            conn.executescript((BASE_DIR / script).read_text(encoding="utf-8"))
    finally:
        conn.close()


def database_is_ready(conn):
    """True if the expected tables exist (a quick check that setup was run)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table' AND name IN "
        "('Leagues','Clubs','Players','Managers','ManagerTenures','Transfers','Contracts')"
    ).fetchone()
    return row[0] == 7


# ----------------------------------------------------------------------------
# Operation 1: search / browse players
# ----------------------------------------------------------------------------
def search_players(conn, name=None, position=None, min_value=None):
    """Players matching the optional filters, most valuable first."""
    conditions = []
    params = []
    if name:
        conditions.append("(first_name || ' ' || last_name) LIKE ?")
        params.append(f"%{name}%")
    if position:
        conditions.append("position = ?")
        params.append(position)
    if min_value is not None:
        conditions.append("market_value >= ?")
        params.append(min_value)
    where = "WHERE " + " AND ".join(conditions) if conditions else ""
    sql = (
        "SELECT player_id, first_name || ' ' || last_name AS player, nationality, "
        "       position, market_value, is_active "
        "FROM Players " + where + " ORDER BY market_value DESC, last_name"
    )
    return conn.execute(sql, params).fetchall()


def list_clubs(conn, name=None):
    """Clubs with their league, optionally filtered by part of the name."""
    return conn.execute(
        "SELECT c.club_id, c.name AS club, c.city, l.name AS league "
        "FROM Clubs AS c JOIN Leagues AS l ON l.league_id = c.league_id "
        "WHERE c.name LIKE ? ORDER BY c.name",
        (f"%{name or ''}%",),
    ).fetchall()


# ----------------------------------------------------------------------------
# Operation 2: related data (player profile: Players + Transfers + Clubs + Leagues)
# ----------------------------------------------------------------------------
def get_player(conn, player_id):
    return conn.execute(
        "SELECT player_id, first_name || ' ' || last_name AS player, date_of_birth, "
        "       nationality, position, market_value, is_active "
        "FROM Players WHERE player_id = ?",
        (player_id,),
    ).fetchone()


def player_transfer_history(conn, player_id):
    """A player's transfers in date order, with club names and the buying club's league."""
    return conn.execute(
        "SELECT t.transfer_id, t.transfer_date, "
        "       COALESCE(fc.name, 'Free agent') AS from_club, "
        "       COALESCE(tc.name, 'Free agent') AS to_club, "
        "       COALESCE(l.name, '-') AS league, t.fee, t.transfer_type "
        "FROM Transfers AS t "
        "LEFT JOIN Clubs AS fc ON fc.club_id = t.from_club_id "
        "LEFT JOIN Clubs AS tc ON tc.club_id = t.to_club_id "
        "LEFT JOIN Leagues AS l ON l.league_id = tc.league_id "
        "WHERE t.player_id = ? "
        "ORDER BY t.transfer_date, t.transfer_id",
        (player_id,),
    ).fetchall()


def player_contracts(conn, player_id):
    return conn.execute(
        "SELECT c.name AS club, ct.start_date, ct.end_date, ct.weekly_wage "
        "FROM Contracts AS ct JOIN Clubs AS c ON c.club_id = ct.club_id "
        "WHERE ct.player_id = ? ORDER BY ct.start_date",
        (player_id,),
    ).fetchall()


# ----------------------------------------------------------------------------
# Operation 3: add a player
# ----------------------------------------------------------------------------
def player_exists(conn, first_name, last_name, date_of_birth):
    row = conn.execute(
        "SELECT 1 FROM Players WHERE lower(first_name) = lower(?) "
        "AND lower(last_name) = lower(?) AND date_of_birth = ?",
        (first_name, last_name, date_of_birth),
    ).fetchone()
    return row is not None


def add_player(conn, first_name, last_name, date_of_birth, nationality, position, market_value):
    """Insert a player and return the new player_id."""
    with conn:  # commits on success, rolls back on error
        cur = conn.execute(
            "INSERT INTO Players (first_name, last_name, date_of_birth, nationality, "
            "                     position, market_value, is_active) "
            "VALUES (?, ?, ?, ?, ?, ?, 'Yes')",
            (first_name, last_name, date_of_birth, nationality, position, market_value),
        )
    return cur.lastrowid


# ----------------------------------------------------------------------------
# Operation 4: update (market value) and delete (a mistaken transfer)
# ----------------------------------------------------------------------------
def update_market_value(conn, player_id, new_value):
    """Set a player's market value. Returns the number of rows changed (0 = no such player)."""
    with conn:
        cur = conn.execute(
            "UPDATE Players SET market_value = ? WHERE player_id = ?",
            (new_value, player_id),
        )
    return cur.rowcount


def get_transfer(conn, transfer_id):
    return conn.execute(
        "SELECT t.transfer_id, p.first_name || ' ' || p.last_name AS player, "
        "       COALESCE(fc.name, 'Free agent') AS from_club, "
        "       COALESCE(tc.name, 'Free agent') AS to_club, "
        "       t.transfer_date, t.fee, t.transfer_type "
        "FROM Transfers AS t "
        "JOIN Players AS p ON p.player_id = t.player_id "
        "LEFT JOIN Clubs AS fc ON fc.club_id = t.from_club_id "
        "LEFT JOIN Clubs AS tc ON tc.club_id = t.to_club_id "
        "WHERE t.transfer_id = ?",
        (transfer_id,),
    ).fetchone()


def delete_transfer(conn, transfer_id):
    """Delete one transfer and the contract that was recorded with it.

    A transfer saved through record_transfer() also creates a contract at the buying club
    starting on the transfer date. Deleting only the transfer would leave that contract
    behind, so both deletes run in one transaction.
    If a later transfer of the same player left the club this one went to, its selling club
    is set back to this transfer's selling club (A->B, B->C becomes A->C), so the history
    stays connected. All of this is one transaction. A NULL club means free agent; the
    relink uses IS / IS NOT so NULLs compare correctly, and it is skipped when it would
    produce a paid transfer to or from a free agent (which the schema does not allow).
    Returns (transfers_deleted, contracts_deleted).
    """
    transfer = conn.execute(
        "SELECT player_id, from_club_id, to_club_id, transfer_date FROM Transfers "
        "WHERE transfer_id = ?",
        (transfer_id,),
    ).fetchone()
    if transfer is None:
        return 0, 0
    with conn:
        conn.execute(
            "UPDATE Transfers SET from_club_id = ? "
            "WHERE transfer_id = (SELECT transfer_id FROM Transfers "
            "                     WHERE player_id = ? AND transfer_id <> ? "
            "                       AND (transfer_date > ? OR (transfer_date = ? AND transfer_id > ?)) "
            "                     ORDER BY transfer_date, transfer_id LIMIT 1) "
            "  AND from_club_id IS ? AND to_club_id IS NOT ? "
            "  AND (? IS NOT NULL OR transfer_type = 'Free')",
            (transfer["from_club_id"], transfer["player_id"], transfer_id,
             transfer["transfer_date"], transfer["transfer_date"], transfer_id,
             transfer["to_club_id"], transfer["from_club_id"], transfer["from_club_id"]),
        )
        contract_cur = conn.execute(
            "DELETE FROM Contracts WHERE player_id = ? AND club_id = ? AND start_date = ?",
            (transfer["player_id"], transfer["to_club_id"], transfer["transfer_date"]),
        )
        transfer_cur = conn.execute(
            "DELETE FROM Transfers WHERE transfer_id = ?", (transfer_id,)
        )
    return transfer_cur.rowcount, contract_cur.rowcount


# ----------------------------------------------------------------------------
# Operation 5: reports (view, aggregate, GROUP BY / HAVING)
# ----------------------------------------------------------------------------
def club_balance_report(conn):
    """Spending, income, and net spend per club that has any transfer activity."""
    return conn.execute(
        "SELECT club, league, players_bought, total_spent, players_sold, total_received, "
        "       total_spent - total_received AS net_spend "
        "FROM v_club_transfer_balance "
        "WHERE players_bought > 0 OR players_sold > 0 "
        "ORDER BY net_spend DESC, club"
    ).fetchall()


def league_fee_report(conn):
    """Permanent-transfer count, total, and average fee by the buying club's league."""
    return conn.execute(
        "SELECT l.name AS league, COUNT(*) AS transfers, SUM(t.fee) AS total_fees, "
        "       ROUND(AVG(t.fee), 0) AS average_fee "
        "FROM Transfers AS t "
        "JOIN Clubs AS c ON c.club_id = t.to_club_id "
        "JOIN Leagues AS l ON l.league_id = c.league_id "
        "WHERE t.transfer_type = 'Permanent' "
        "GROUP BY l.league_id, l.name "
        "ORDER BY average_fee DESC"
    ).fetchall()


# ----------------------------------------------------------------------------
# Operation 6: record a transfer (multi-step transaction)
# ----------------------------------------------------------------------------
def current_club_id(conn, player_id, as_of=None):
    """The club a player was at on a date: where their latest transfer on or before `as_of`
    went (None if there is none). With no date, the club of their most recent transfer.
    Using the date lets a career be entered out of order (for example, back-filling a
    player's earlier moves) and still get the right selling club."""
    row = conn.execute(
        "SELECT to_club_id FROM Transfers "
        "WHERE player_id = ? AND (? IS NULL OR transfer_date <= ?) "
        "ORDER BY transfer_date DESC, transfer_id DESC LIMIT 1",
        (player_id, as_of, as_of),
    ).fetchone()
    return row["to_club_id"] if row else None


def club_on_date(conn, player_id, as_of=None):
    """(known, club_id) for where a player was on a date.
    known is False when the player has no recorded transfer on or before the date.
    When known, club_id is the club of their latest transfer by then, or None if that
    transfer made them a free agent."""
    row = conn.execute(
        "SELECT to_club_id FROM Transfers "
        "WHERE player_id = ? AND (? IS NULL OR transfer_date <= ?) "
        "ORDER BY transfer_date DESC, transfer_id DESC LIMIT 1",
        (player_id, as_of, as_of),
    ).fetchone()
    return (True, row["to_club_id"]) if row else (False, None)


def get_club(conn, club_id):
    return conn.execute(
        "SELECT club_id, name FROM Clubs WHERE club_id = ?", (club_id,)
    ).fetchone()


_AUTO = object()


def record_transfer(conn, player_id, to_club_id, transfer_date, fee, transfer_type,
                    contract_end=None, weekly_wage=None, from_club_id=_AUTO):
    """Record a transfer and, optionally, the player's new contract at the buying club.

    The two inserts belong together: a signing that is saved without its contract (or a
    contract without its transfer) would leave the data inconsistent. Both run inside one
    transaction, so either both are saved or neither is.
    If the new transfer falls in the middle of the player's recorded history (a career being
    back-filled out of order), the next transfer's selling club is updated to the new buying
    club, so the chain A->C becomes A->B, B->C. That is a third step in the same transaction.
    A club id of None means "free agent" on either side (release / contract ended, or a
    free-agent signing). from_club_id defaults to the club the player was at on that date;
    pass it explicitly (a club id or None) when the player has no recorded history.
    A free-agent move has no contract recorded (there is no club to sign with).
    Returns (new transfer_id, True if a later transfer was relinked).
    """
    if from_club_id is _AUTO:
        from_club_id = current_club_id(conn, player_id, transfer_date)
    with conn:  # BEGIN ... COMMIT, or ROLLBACK if anything below raises
        cur = conn.execute(
            "INSERT INTO Transfers (player_id, from_club_id, to_club_id, "
            "                       transfer_date, fee, transfer_type) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (player_id, from_club_id, to_club_id, transfer_date, fee, transfer_type),
        )
        new_id = cur.lastrowid
        # Only a later transfer that left the same club this one left is relinked
        # (IS compares NULLs too), and never into a transfer from a club to itself.
        relinked = conn.execute(
            "UPDATE Transfers SET from_club_id = ? "
            "WHERE transfer_id = (SELECT transfer_id FROM Transfers "
            "                     WHERE player_id = ? AND transfer_id <> ? "
            "                       AND (transfer_date > ? OR (transfer_date = ? AND transfer_id > ?)) "
            "                     ORDER BY transfer_date, transfer_id LIMIT 1) "
            "  AND from_club_id IS ? AND to_club_id IS NOT ? "
            "  AND (? IS NOT NULL OR transfer_type = 'Free')",
            (to_club_id, player_id, new_id, transfer_date, transfer_date, new_id,
             from_club_id, to_club_id, to_club_id),
        ).rowcount
        if contract_end is not None and to_club_id is not None:
            conn.execute(
                "INSERT INTO Contracts (player_id, club_id, start_date, end_date, weekly_wage) "
                "VALUES (?, ?, ?, ?, ?)",
                (player_id, to_club_id, transfer_date, contract_end, weekly_wage),
            )
    return new_id, relinked > 0


# ----------------------------------------------------------------------------
# Recent and most expensive transfers
# ----------------------------------------------------------------------------
def recent_transfers(conn, limit=10):
    """The most recently dated transfers, newest first (ties: most recently entered first)."""
    return conn.execute(
        "SELECT transfer_id, transfer_date, player_name, from_club, to_club, fee, transfer_type "
        "FROM v_transfer_history "
        "ORDER BY transfer_date DESC, transfer_id DESC LIMIT ?",
        (limit,),
    ).fetchall()


def top_transfers(conn, years=None, limit=10):
    """The most expensive transfers, optionally only those in the last `years` years."""
    return conn.execute(
        "SELECT transfer_id, transfer_date, player_name, from_club, to_club, fee, transfer_type "
        "FROM v_transfer_history "
        "WHERE (? IS NULL OR transfer_date >= date('now', '-' || ? || ' years')) "
        "ORDER BY fee DESC, transfer_date DESC LIMIT ?",
        (years, years, limit),
    ).fetchall()


# ----------------------------------------------------------------------------
# Clubs and leagues: add a league, add a club, move a club between leagues
# ----------------------------------------------------------------------------
def list_leagues(conn, name=None):
    """Leagues with how many clubs each has (leagues with no clubs are kept by the LEFT JOIN)."""
    return conn.execute(
        "SELECT l.league_id, l.name AS league, l.country, l.tier, COUNT(c.club_id) AS clubs "
        "FROM Leagues AS l LEFT JOIN Clubs AS c ON c.league_id = l.league_id "
        "WHERE l.name LIKE ? "
        "GROUP BY l.league_id, l.name, l.country, l.tier "
        "ORDER BY l.country, l.tier, l.name",
        (f"%{name or ''}%",),
    ).fetchall()


def get_league(conn, league_id):
    return conn.execute(
        "SELECT league_id, name FROM Leagues WHERE league_id = ?", (league_id,)
    ).fetchone()


def league_name_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM Leagues WHERE lower(name) = lower(?)", (name,)
    ).fetchone() is not None


def club_name_exists(conn, name):
    return conn.execute(
        "SELECT 1 FROM Clubs WHERE lower(name) = lower(?)", (name,)
    ).fetchone() is not None


def add_league(conn, name, country, tier):
    """Insert a league and return its league_id."""
    with conn:
        cur = conn.execute(
            "INSERT INTO Leagues (name, country, tier) VALUES (?, ?, ?)",
            (name, country, tier),
        )
    return cur.lastrowid


def add_club(conn, name, city, founded_year, league_id):
    """Insert a club and return its club_id."""
    with conn:
        cur = conn.execute(
            "INSERT INTO Clubs (name, city, founded_year, league_id) VALUES (?, ?, ?, ?)",
            (name, city, founded_year, league_id),
        )
    return cur.lastrowid


def get_club_with_league(conn, club_id):
    return conn.execute(
        "SELECT c.club_id, c.name, c.league_id, l.name AS league "
        "FROM Clubs AS c JOIN Leagues AS l ON l.league_id = c.league_id "
        "WHERE c.club_id = ?",
        (club_id,),
    ).fetchone()


def get_club_details(conn, club_id):
    return conn.execute(
        "SELECT c.club_id, c.name, c.city, c.founded_year, l.name AS league, l.country "
        "FROM Clubs AS c JOIN Leagues AS l ON l.league_id = c.league_id "
        "WHERE c.club_id = ?",
        (club_id,),
    ).fetchone()


def club_current_managers(conn, club_id):
    """Managers whose tenure at the club has no end date (from the v_current_managers view)."""
    return conn.execute(
        "SELECT manager_name, role, start_date FROM v_current_managers "
        "WHERE club_id = ? ORDER BY start_date",
        (club_id,),
    ).fetchall()


def club_current_players(conn, club_id):
    """Players whose latest recorded transfer was to this club (most recent arrivals first).
    The transfer history, not contracts, decides who is considered to be at the club."""
    return conn.execute(
        "SELECT p.player_id, p.first_name || ' ' || p.last_name AS player, p.position, "
        "       t.transfer_date, t.transfer_type "
        "FROM Transfers AS t JOIN Players AS p ON p.player_id = t.player_id "
        "WHERE t.to_club_id = ? "
        "  AND t.transfer_id = (SELECT t2.transfer_id FROM Transfers AS t2 "
        "                       WHERE t2.player_id = t.player_id "
        "                       ORDER BY t2.transfer_date DESC, t2.transfer_id DESC LIMIT 1) "
        "ORDER BY t.transfer_date DESC, p.last_name",
        (club_id,),
    ).fetchall()


def move_club_to_league(conn, club_id, league_id):
    """Promotion / relegation: put a club in a different league. Returns rows changed."""
    with conn:
        cur = conn.execute(
            "UPDATE Clubs SET league_id = ? WHERE club_id = ?", (league_id, club_id)
        )
    return cur.rowcount


# ----------------------------------------------------------------------------
# Contracts expiring soon (proposal question 5)
# ----------------------------------------------------------------------------
def contracts_expiring(conn, months):
    """Contracts that end between today and `months` months from now, soonest first."""
    return conn.execute(
        "SELECT p.first_name || ' ' || p.last_name AS player, c.name AS club, "
        "       ct.end_date, ct.weekly_wage "
        "FROM Contracts AS ct "
        "JOIN Players AS p ON p.player_id = ct.player_id "
        "JOIN Clubs AS c ON c.club_id = ct.club_id "
        "WHERE ct.end_date BETWEEN date('now') AND date('now', '+' || ? || ' months') "
        "ORDER BY ct.end_date",
        (months,),
    ).fetchall()
