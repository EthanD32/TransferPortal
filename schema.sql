-- ============================================================================
-- TransferPortal: Soccer Transfer Market Database (SQLite 3)
-- schema.sql: creates all tables, constraints, views, and indexes.
-- Run this file FIRST, then insert_data.sql (see README.txt).
-- ============================================================================

-- SQLite does not enforce foreign keys unless this is switched on, and the
-- setting applies per connection. Any application must run it on every
-- connection it opens.
PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- Cleanup (children first, so the file can be re-run on an existing database)
-- ----------------------------------------------------------------------------
DROP VIEW  IF EXISTS v_club_transfer_balance;
DROP VIEW  IF EXISTS v_current_managers;
DROP VIEW  IF EXISTS v_transfer_history;

DROP INDEX IF EXISTS idx_tenures_club_end;
DROP INDEX IF EXISTS idx_contracts_end_date;
DROP INDEX IF EXISTS idx_transfers_to_club;
DROP INDEX IF EXISTS idx_transfers_from_club;
DROP INDEX IF EXISTS idx_transfers_player_date;

DROP TABLE IF EXISTS Contracts;
DROP TABLE IF EXISTS Transfers;
DROP TABLE IF EXISTS ManagerTenures;
DROP TABLE IF EXISTS Managers;
DROP TABLE IF EXISTS Players;
DROP TABLE IF EXISTS Clubs;
DROP TABLE IF EXISTS Leagues;

-- ----------------------------------------------------------------------------
-- Conventions
--   * Dates are TEXT in ISO 8601 form (YYYY-MM-DD). Each date column has a
--     CHECK that rejects anything that is not a real calendar date.
--   * is_active is TEXT with the values 'Yes' or 'No'.
--   * fee and market_value are REAL amounts in euros; weekly_wage is a REAL
--     amount in US dollars (the currency the source reports it in).
-- ----------------------------------------------------------------------------

-- ----------------------------------------------------------------------------
-- Leagues
-- ----------------------------------------------------------------------------
CREATE TABLE Leagues (
    league_id INTEGER PRIMARY KEY,
    name      TEXT    NOT NULL UNIQUE,
    country   TEXT    NOT NULL,
    tier      INTEGER NOT NULL CHECK (tier >= 1)      -- 1 = top division
);

-- ----------------------------------------------------------------------------
-- Clubs (each club belongs to exactly one league)
-- ----------------------------------------------------------------------------
CREATE TABLE Clubs (
    club_id      INTEGER PRIMARY KEY,
    name         TEXT    NOT NULL UNIQUE,
    city         TEXT    NOT NULL,
    founded_year INTEGER NOT NULL CHECK (founded_year BETWEEN 1800 AND 2100),
    league_id    INTEGER NOT NULL,
    FOREIGN KEY (league_id) REFERENCES Leagues (league_id)
);

-- ----------------------------------------------------------------------------
-- Players
-- ----------------------------------------------------------------------------
CREATE TABLE Players (
    player_id     INTEGER PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    date_of_birth TEXT NOT NULL CHECK (date(date_of_birth) = date_of_birth),
    nationality   TEXT NOT NULL,
    position      TEXT NOT NULL
                  CHECK (position IN ('Goalkeeper', 'Defender', 'Midfielder', 'Forward')),
    market_value  REAL NOT NULL DEFAULT 0 CHECK (market_value >= 0),
    is_active     TEXT NOT NULL DEFAULT 'Yes' CHECK (is_active IN ('Yes', 'No'))
);

-- ----------------------------------------------------------------------------
-- Managers
-- ----------------------------------------------------------------------------
CREATE TABLE Managers (
    manager_id    INTEGER PRIMARY KEY,
    first_name    TEXT NOT NULL,
    last_name     TEXT NOT NULL,
    date_of_birth TEXT NOT NULL CHECK (date(date_of_birth) = date_of_birth),
    nationality   TEXT NOT NULL,
    is_active     TEXT NOT NULL DEFAULT 'Yes' CHECK (is_active IN ('Yes', 'No'))
);

-- ----------------------------------------------------------------------------
-- ManagerTenures: junction table resolving the Managers <-> Clubs many-to-many.
-- One row per spell. It has its own key (tenure_id) instead of
-- (manager_id, club_id) so a manager can return to the same club later.
-- A NULL end_date means the manager is still in the job.
-- ----------------------------------------------------------------------------
CREATE TABLE ManagerTenures (
    tenure_id  INTEGER PRIMARY KEY,
    manager_id INTEGER NOT NULL,
    club_id    INTEGER NOT NULL,
    start_date TEXT    NOT NULL CHECK (date(start_date) = start_date),
    end_date   TEXT    CHECK (end_date IS NULL OR date(end_date) = end_date),
    role       TEXT    NOT NULL DEFAULT 'Head Coach'
               CHECK (role IN ('Head Coach', 'Assistant', 'Interim')),
    CHECK (end_date IS NULL OR end_date >= start_date),   -- a spell cannot end before it starts
    UNIQUE (manager_id, club_id, start_date),             -- no duplicate spell records
    FOREIGN KEY (manager_id) REFERENCES Managers (manager_id),
    FOREIGN KEY (club_id)    REFERENCES Clubs (club_id)
);

-- ----------------------------------------------------------------------------
-- Transfers: one row per move of a player between clubs.
-- A NULL club means "free agent": from_club_id NULL = the player had no club
-- (signed as a free agent, or a first signing); to_club_id NULL = the player
-- left a club and became a free agent (released, or contract ended). At least
-- one side must be a real club, and any move that involves a free agent is
-- recorded as type 'Free' with fee 0.
-- ----------------------------------------------------------------------------
CREATE TABLE Transfers (
    transfer_id   INTEGER PRIMARY KEY,
    player_id     INTEGER NOT NULL,
    from_club_id  INTEGER,                                       -- NULL = free agent
    to_club_id    INTEGER,                                       -- NULL = free agent
    transfer_date TEXT    NOT NULL CHECK (date(transfer_date) = transfer_date),
    fee           REAL    NOT NULL DEFAULT 0 CHECK (fee >= 0),
    transfer_type TEXT    NOT NULL CHECK (transfer_type IN ('Permanent', 'Loan', 'Free')),
    CHECK (from_club_id IS NOT NULL OR to_club_id IS NOT NULL),  -- free agent to free agent is not a move
    CHECK (from_club_id IS NULL OR to_club_id IS NULL OR from_club_id <> to_club_id),  -- a club cannot sell to itself
    CHECK (transfer_type <> 'Free' OR fee = 0),                  -- free transfers carry no fee
    CHECK ((from_club_id IS NOT NULL AND to_club_id IS NOT NULL) OR transfer_type = 'Free'),  -- free agent moves are 'Free'
    FOREIGN KEY (player_id)    REFERENCES Players (player_id),
    FOREIGN KEY (from_club_id) REFERENCES Clubs (club_id),
    FOREIGN KEY (to_club_id)   REFERENCES Clubs (club_id)
);

-- ----------------------------------------------------------------------------
-- Contracts: a player's deal with a club. Own key so a player can sign with
-- the same club more than once (for example, a contract extension).
-- ----------------------------------------------------------------------------
CREATE TABLE Contracts (
    contract_id INTEGER PRIMARY KEY,
    player_id   INTEGER NOT NULL,
    club_id     INTEGER NOT NULL,
    start_date  TEXT    NOT NULL CHECK (date(start_date) = start_date),
    end_date    TEXT    NOT NULL CHECK (date(end_date) = end_date),
    weekly_wage REAL    NOT NULL CHECK (weekly_wage > 0),
    CHECK (end_date > start_date),
    UNIQUE (player_id, club_id, start_date),
    FOREIGN KEY (player_id) REFERENCES Players (player_id),
    FOREIGN KEY (club_id)   REFERENCES Clubs (club_id)
);

-- ----------------------------------------------------------------------------
-- Indexes (created intentionally for common lookups; PK/UNIQUE indexes are
-- created automatically by SQLite and are not counted here)
-- ----------------------------------------------------------------------------

-- A player's career history, in date order (report: full transfer history).
CREATE INDEX idx_transfers_player_date ON Transfers (player_id, transfer_date);

-- Club spending and sales reports, and joins from Clubs to Transfers.
CREATE INDEX idx_transfers_to_club   ON Transfers (to_club_id);
CREATE INDEX idx_transfers_from_club ON Transfers (from_club_id);

-- "Which contracts expire soon?" range searches on end_date.
CREATE INDEX idx_contracts_end_date ON Contracts (end_date);

-- "Who manages this club now?" (club_id, then end_date IS NULL).
CREATE INDEX idx_tenures_club_end ON ManagerTenures (club_id, end_date);

-- ----------------------------------------------------------------------------
-- Views
-- ----------------------------------------------------------------------------

-- Readable transfer history: player, selling club, buying club and its league.
-- LEFT JOINs on both clubs keep moves to or from a free agent (NULL club).
CREATE VIEW v_transfer_history AS
SELECT t.transfer_id,
       p.first_name || ' ' || p.last_name         AS player_name,
       p.position                                 AS position,
       COALESCE(fc.name, 'Free agent')            AS from_club,
       COALESCE(tc.name, 'Free agent')            AS to_club,
       l.name                                     AS to_league,
       t.transfer_date,
       t.fee,
       t.transfer_type
FROM Transfers t
JOIN Players p       ON p.player_id  = t.player_id
LEFT JOIN Clubs fc   ON fc.club_id   = t.from_club_id
LEFT JOIN Clubs tc   ON tc.club_id   = t.to_club_id
LEFT JOIN Leagues l  ON l.league_id  = tc.league_id;

-- Current manager (or managers, if a head coach and assistants are recorded)
-- for each club: tenures that have not ended.
CREATE VIEW v_current_managers AS
SELECT c.club_id,
       c.name                                     AS club,
       l.name                                     AS league,
       m.first_name || ' ' || m.last_name         AS manager_name,
       m.nationality                              AS manager_nationality,
       mt.role,
       mt.start_date
FROM ManagerTenures mt
JOIN Managers m ON m.manager_id = mt.manager_id
JOIN Clubs c    ON c.club_id    = mt.club_id
JOIN Leagues l  ON l.league_id  = c.league_id
WHERE mt.end_date IS NULL;

-- Money spent on incoming transfers and received for outgoing ones, per club.
-- Clubs with no activity show 0 rather than disappearing.
CREATE VIEW v_club_transfer_balance AS
SELECT c.club_id,
       c.name AS club,
       l.name AS league,
       (SELECT COUNT(*) FROM Transfers t WHERE t.to_club_id = c.club_id)                 AS players_bought,
       COALESCE((SELECT SUM(t.fee) FROM Transfers t WHERE t.to_club_id = c.club_id), 0)   AS total_spent,
       (SELECT COUNT(*) FROM Transfers t WHERE t.from_club_id = c.club_id)               AS players_sold,
       COALESCE((SELECT SUM(t.fee) FROM Transfers t WHERE t.from_club_id = c.club_id), 0) AS total_received
FROM Clubs c
JOIN Leagues l ON l.league_id = c.league_id;
