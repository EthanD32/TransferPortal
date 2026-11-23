-- TransferPortal: transaction.sql (final version)
-- Run with:  sqlite3 -header -column -bail transferportal.db < transaction.sql
--
-- Scenario: recording a new signing in the application takes three related
-- changes: the player is registered, the transfer is recorded, and the new
-- contract is recorded. If any step failed on its own (for example, the
-- contract broke a CHECK rule), the database would be left with a player and a
-- transfer but no contract. A transaction makes all three steps succeed
-- together or not at all.
--
-- The player below ("Sample Signing") is fictional, used only for this demo, so
-- the example ends with ROLLBACK and the real sample data is left unchanged.
-- To keep the changes instead, replace ROLLBACK with COMMIT.
--
-- Lines starting with ".print" are sqlite3 shell commands that label the output.

-- Foreign keys must be switched on before BEGIN (SQLite ignores this setting
-- inside a transaction), and the setting applies per connection.
PRAGMA foreign_keys = ON;

.print
.print ==== Row counts BEFORE the transaction ====
SELECT (SELECT COUNT(*) FROM Players)   AS players,
       (SELECT COUNT(*) FROM Transfers) AS transfers,
       (SELECT COUNT(*) FROM Contracts) AS contracts;

BEGIN TRANSACTION;

-- Step 1: register the new player.
INSERT INTO Players (first_name, last_name, date_of_birth, nationality,
                     position, market_value, is_active)
VALUES ('Sample', 'Signing', '2004-01-15', 'Brazil', 'Midfielder', 30000000, 'Yes');

-- Step 2: record the transfer (Chelsea to Inter Milan, 35 million euros).
-- Club IDs are looked up by name, and the new player's ID by name too.
INSERT INTO Transfers (player_id, from_club_id, to_club_id,
                       transfer_date, fee, transfer_type)
SELECT (SELECT player_id FROM Players WHERE first_name = 'Sample' AND last_name = 'Signing'),
       (SELECT club_id   FROM Clubs   WHERE name = 'Chelsea'),
       (SELECT club_id   FROM Clubs   WHERE name = 'Inter Milan'),
       '2026-11-02', 35000000, 'Permanent';

-- Step 3: record the player's new contract with the buying club.
INSERT INTO Contracts (player_id, club_id, start_date, end_date, weekly_wage)
SELECT (SELECT player_id FROM Players WHERE first_name = 'Sample' AND last_name = 'Signing'),
       (SELECT club_id   FROM Clubs   WHERE name = 'Inter Milan'),
       '2026-11-02', '2031-06-30', 150000;

-- Inside the transaction, all three changes are visible together.
.print
.print ==== Inside the transaction: the new signing as the database sees it ====
SELECT player_name, from_club, to_club, transfer_date, fee AS fee_eur, transfer_type
FROM v_transfer_history
WHERE player_name = 'Sample Signing';

.print
.print ==== Row counts INSIDE the transaction (one more of each) ====
SELECT (SELECT COUNT(*) FROM Players)   AS players,
       (SELECT COUNT(*) FROM Transfers) AS transfers,
       (SELECT COUNT(*) FROM Contracts) AS contracts;

-- Undo all three steps together so the sample data is unchanged.
ROLLBACK;

.print
.print ==== Row counts AFTER ROLLBACK (same as before) ====
SELECT (SELECT COUNT(*) FROM Players)   AS players,
       (SELECT COUNT(*) FROM Transfers) AS transfers,
       (SELECT COUNT(*) FROM Contracts) AS contracts;

.print
.print ==== After ROLLBACK: Sample Signing is gone (0 rows expected) ====
SELECT COUNT(*) AS sample_signing_rows
FROM Players
WHERE first_name = 'Sample' AND last_name = 'Signing';
