-- TransferPortal: queries.sql (final version)
-- Run with:  sqlite3 -header -column transferportal.db < queries.sql
--
-- Lines starting with ".print" are sqlite3 shell commands that label the output.
-- "Today" in the sample data is 2026-11-02, so date comparisons use that literal
-- (instead of date('now')) to keep results the same every time the script runs.
-- Amounts are in euros.

PRAGMA foreign_keys = ON;

.print
.print ==== Requirement 1: Filtering and Sorting ====
-- Requirement 1: Filtering and Sorting
-- Proposal report 1: what is a given player's full transfer history, in order,
-- with the clubs, dates, and fees involved? (Shown here for David De Gea, whose
-- history includes moves to and from "free agent".)
SELECT transfer_date,
       from_club,
       to_club,
       fee            AS fee_eur,
       transfer_type
FROM v_transfer_history
WHERE player_name = 'David De Gea'
ORDER BY transfer_date;

.print
.print ==== Requirement 2: INNER JOIN ====
-- Requirement 2: INNER JOIN
-- Proposal report 5 (contracts expiring within 12 months). Contract-expiry report: which players have a contract ending within the next
-- 12 months (2026-11-02 to 2027-11-02), and what do they earn per week?
-- Players is joined to Contracts; only players with a matching contract appear.
SELECT p.first_name || ' ' || p.last_name AS player_name,
       p.position,
       c.end_date                         AS contract_ends,
       c.weekly_wage                      AS weekly_wage_eur
FROM Players p
INNER JOIN Contracts c ON c.player_id = p.player_id
WHERE c.end_date BETWEEN '2026-11-02' AND '2027-11-02'
ORDER BY c.end_date, player_name;

.print
.print ==== Requirement 3: LEFT JOIN ====
-- Requirement 3: LEFT JOIN
-- League directory: every league with its clubs. Eredivisie has no clubs in the
-- database, so it is kept (LEFT JOIN) and shows "No clubs recorded". An INNER
-- JOIN would silently drop it.
SELECT l.name                              AS league,
       l.country,
       COALESCE(c.name, 'No clubs recorded') AS club
FROM Leagues l
LEFT JOIN Clubs c ON c.league_id = l.league_id
ORDER BY l.name, c.name;

.print
.print ==== Requirement 4: Three-Table Join ====
-- Requirement 4: Three-Table Join (Managers, ManagerTenures, Clubs, plus Leagues)
-- (Managers are part of the revised design.)
-- Manager career history: every club each manager has worked at, with role,
-- league, and dates. A tenure with no end date is shown as "Present". This needs
-- the junction table ManagerTenures to connect Managers to Clubs.
SELECT m.first_name || ' ' || m.last_name AS manager_name,
       c.name                             AS club,
       l.name                             AS league,
       mt.role,
       mt.start_date,
       COALESCE(mt.end_date, 'Present')   AS end_date
FROM Managers m
JOIN ManagerTenures mt ON mt.manager_id = m.manager_id
JOIN Clubs c           ON c.club_id     = mt.club_id
JOIN Leagues l         ON l.league_id   = c.league_id
ORDER BY m.last_name, mt.start_date;

.print
.print ==== Requirement 5: Aggregate Query ====
-- Requirement 5: Aggregate Query
-- Wage-bill summary: across all contracts that have not yet expired, how many are
-- there and what are the average, lowest, and highest weekly wages?
SELECT COUNT(*)                     AS active_contracts,
       ROUND(AVG(weekly_wage), 0)   AS avg_weekly_wage_eur,
       MIN(weekly_wage)             AS min_weekly_wage_eur,
       MAX(weekly_wage)             AS max_weekly_wage_eur
FROM Contracts
WHERE end_date >= '2026-11-02';

.print
.print ==== Requirement 6: GROUP BY and HAVING ====
-- Requirement 6: GROUP BY and HAVING
-- Proposal report 2 (which clubs spent the most on incoming players). Club spending report: which clubs have spent more than 50 million euros in
-- total on incoming permanent transfers? Grouped by buying club; HAVING removes
-- the clubs that spent less.
SELECT c.name                 AS club,
       COUNT(*)               AS players_bought,
       SUM(t.fee)             AS total_spent_eur
FROM Transfers t
JOIN Clubs c ON c.club_id = t.to_club_id
WHERE t.transfer_type = 'Permanent'
GROUP BY c.club_id, c.name
HAVING SUM(t.fee) > 50000000
ORDER BY total_spent_eur DESC;

.print
.print ==== Requirement 7: Subquery ====
-- Requirement 7: Subquery
-- Proposal report 3 (most expensive transfers). Big-deal report: which permanent transfers cost more than the average
-- permanent transfer fee? The subquery calculates that average so the cutoff
-- is not hard-coded and updates as new transfers are added.
SELECT p.first_name || ' ' || p.last_name AS player_name,
       fc.name                            AS from_club,
       tc.name                            AS to_club,
       t.transfer_date,
       t.fee                              AS fee_eur
FROM Transfers t
JOIN Players p      ON p.player_id = t.player_id
JOIN Clubs fc       ON fc.club_id  = t.from_club_id
JOIN Clubs tc       ON tc.club_id  = t.to_club_id
WHERE t.transfer_type = 'Permanent'
  AND t.fee > (SELECT AVG(fee)
               FROM Transfers
               WHERE transfer_type = 'Permanent')
ORDER BY t.fee DESC;

.print
.print ==== Requirement 8: Set Operation (EXCEPT) ====
-- Requirement 8: Set Operation (EXCEPT)
-- Vacancy report: which clubs currently have no head coach? The first set is
-- all clubs; the second is clubs with a Head Coach tenure that has not ended.
-- Both sets are club names, so EXCEPT gives the clubs missing from the second.
SELECT name AS club
FROM Clubs
EXCEPT
SELECT c.name
FROM ManagerTenures mt
JOIN Clubs c ON c.club_id = mt.club_id
WHERE mt.end_date IS NULL
  AND mt.role = 'Head Coach'
ORDER BY club;

.print
.print ==== Requirement 9: View ====
-- Requirement 9: View (v_club_transfer_balance)
-- Proposal report 2 (club spending and earnings from sales).
-- Net spend league table: which clubs have spent the most more than they have
-- earned from sales? The view already combines Clubs, Leagues, and two sets of
-- Transfers totals (bought vs. sold), so the query only needs one line of
-- arithmetic instead of repeating those joins and subqueries.
SELECT club,
       league,
       total_spent                    AS spent_eur,
       ROUND(total_received, 1)       AS received_eur,
       total_spent - total_received   AS net_spend_eur
FROM v_club_transfer_balance
ORDER BY net_spend_eur DESC;
