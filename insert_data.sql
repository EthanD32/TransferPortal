-- ============================================================================
-- TransferPortal: sample data (real-world, publicly reported)
-- Run AFTER schema.sql.
--
-- All rows describe real clubs, leagues, players, managers, and transfers,
-- taken from public sources (details below). Only public football facts are
-- used; no private or sensitive information.
--
-- Sources (checked October 2026):
--   * Wikipedia: club, player, and manager articles, "List of most expensive
--     association football transfers", and the club manager lists.
--   * market_value: Transfermarkt valuations as quoted by The Match Journal
--     (top-100 ranking, August 2026 snapshot), Flashscore (Neymar, De Bruyne),
--     and tusbuenasnoticias.com (Messi, Ronaldo, June 2026). Market values are
--     estimates that change often; treat them as an approximate snapshot.
--   * weekly_wage: The National, "The world's 20 highest-paid footballers"
--     (13 August 2026), citing Capology, SalaryLeaks, and media reports.
--     Wages are US dollars per week and are reported estimates, not official.
--
-- Conventions
--   * fee is in euros. It is the reported base fee, excluding bonuses and
--     add-ons where the sources separate them. Free transfers and loans are
--     recorded with fee 0.
--   * transfer_date is the date the move was announced or confirmed.
--   * Contract end dates are often reported as a year only. 30 June of that
--     year is used (most European contracts run to the end of the season);
--     31 December is used for the MLS contract.
--   * Only transfers between clubs that are in the Clubs table are recorded,
--     so a player's earlier or later moves to other clubs are not included.
--   * A NULL club in Transfers means "free agent". to_club_id NULL = the player
--     left a club and became a free agent; from_club_id NULL = the player signed
--     from being a free agent. Such moves are type Free with fee 0. David De Gea
--     shows both: Manchester United to free agent (contract ended, June 2023),
--     then free agent to Fiorentina (signed 9 August 2024). Sources: Fiorentina's
--     announcement and AP coverage of the signing; Wikipedia for his 2011 move.
--   * Mbappe's 2017 move is a loan with an obligation to buy; the permanent
--     deal (reported at 180 million euros) was completed in 2018, but its exact
--     date was not confirmed in the sources, so it is not recorded.
--   * A club's league is its league in the 2026-27 season (West Ham United is
--     in the EFL Championship after relegation). ManagerTenures only covers
--     the managers listed, so most clubs have no current manager recorded.
-- ============================================================================

PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;

-- ----------------------------------------------------------------------------
-- Leagues (9). The Eredivisie has no clubs entered, which is useful for
-- testing LEFT JOINs.
-- ----------------------------------------------------------------------------
INSERT INTO Leagues (league_id, name, country, tier) VALUES
(1, 'Premier League',   'England',       1),
(2, 'EFL Championship', 'England',       2),
(3, 'La Liga',          'Spain',         1),
(4, 'Serie A',          'Italy',         1),
(5, 'Bundesliga',       'Germany',       1),
(6, 'Ligue 1',          'France',        1),
(7, 'Saudi Pro League', 'Saudi Arabia',  1),
(8, 'MLS',              'United States', 1),
(9, 'Eredivisie',       'Netherlands',   1);

-- ----------------------------------------------------------------------------
-- Clubs (22). Founding years are the years the clubs themselves use
-- (for example Manchester City 1880, Newcastle United 1892, Monaco 1924).
-- ----------------------------------------------------------------------------
INSERT INTO Clubs (club_id, name, city, founded_year, league_id) VALUES
(1,  'Arsenal',              'London',              1886, 1),
(2,  'Chelsea',              'London',              1905, 1),
(3,  'Liverpool',            'Liverpool',           1892, 1),
(4,  'Manchester City',      'Manchester',          1880, 1),
(5,  'Manchester United',    'Manchester',          1878, 1),
(6,  'Tottenham Hotspur',    'London',              1882, 1),
(7,  'Newcastle United',     'Newcastle upon Tyne', 1892, 1),
(8,  'West Ham United',      'London',              1895, 2),
(9,  'Real Madrid',          'Madrid',              1902, 3),
(10, 'FC Barcelona',         'Barcelona',           1899, 3),
(11, 'Atletico Madrid',      'Madrid',              1903, 3),
(12, 'Inter Milan',          'Milan',               1908, 4),
(13, 'Napoli',               'Naples',              1926, 4),
(14, 'Bayern Munich',        'Munich',              1900, 5),
(15, 'Borussia Dortmund',    'Dortmund',            1909, 5),
(16, 'Bayer Leverkusen',     'Leverkusen',          1904, 5),
(17, 'Paris Saint-Germain',  'Paris',               1970, 6),
(18, 'AS Monaco',            'Monaco',              1924, 6),
(19, 'Al-Hilal',             'Riyadh',              1957, 7),
(20, 'Al-Nassr',             'Riyadh',              1955, 7),
(21, 'Inter Miami',          'Miami',               2018, 8),
(22, 'Fiorentina',          'Florence',            1926, 4);

-- ----------------------------------------------------------------------------
-- Players (16). Yamal and Saka have never moved between clubs, so they have
-- no rows in Transfers. Positions are simplified to the four allowed values
-- (wingers and strikers are Forward; attacking midfielders are Midfielder).
-- is_active is 'Yes' when the player is still playing professionally.
-- ----------------------------------------------------------------------------
INSERT INTO Players (player_id, first_name, last_name, date_of_birth, nationality, position, market_value, is_active) VALUES
(1,  'Erling',    'Haaland',                '2000-07-21', 'Norway',    'Forward',    220000000, 'Yes'),
(2,  'Kylian',    'Mbappé',                 '1998-12-20', 'France',    'Forward',    200000000, 'Yes'),
(3,  'Jude',      'Bellingham',             '2003-06-29', 'England',   'Midfielder', 160000000, 'Yes'),
(4,  'Declan',    'Rice',                   '1999-01-14', 'England',   'Midfielder', 120000000, 'Yes'),
(5,  'Ousmane',   'Dembélé',                '1997-05-15', 'France',    'Forward',    100000000, 'Yes'),
(6,  'Florian',   'Wirtz',                  '2003-05-03', 'Germany',   'Midfielder', 100000000, 'Yes'),
(7,  'Alexander', 'Isak',                   '1999-09-21', 'Sweden',    'Forward',     85000000, 'Yes'),
(8,  'Harry',     'Kane',                   '1993-07-28', 'England',   'Forward',     60000000, 'Yes'),
(9,  'Khvicha',   'Kvaratskhelia',          '2001-02-12', 'Georgia',   'Forward',    140000000, 'Yes'),
(10, 'Lamine',    'Yamal',                  '2007-07-13', 'Spain',     'Forward',    220000000, 'Yes'),
(11, 'Bukayo',    'Saka',                   '2001-09-05', 'England',   'Forward',    110000000, 'Yes'),
(12, 'Lionel',    'Messi',                  '1987-06-24', 'Argentina', 'Forward',     15000000, 'Yes'),
(13, 'Cristiano', 'Ronaldo',                '1985-02-05', 'Portugal',  'Forward',     12000000, 'Yes'),
(14, 'Neymar',    'da Silva Santos Júnior', '1992-02-05', 'Brazil',    'Forward',      8000000, 'Yes'),
(15, 'Kevin',     'De Bruyne',              '1991-06-28', 'Belgium',   'Midfielder',   8000000, 'Yes'),
(16, 'David',     'De Gea',                 '1990-11-07', 'Spain',     'Goalkeeper',   3500000, 'Yes');

-- ----------------------------------------------------------------------------
-- Managers (10). is_active is 'Yes' for managers who have not retired.
-- ----------------------------------------------------------------------------
INSERT INTO Managers (manager_id, first_name, last_name, date_of_birth, nationality, is_active) VALUES
(1,  'Carlo',      'Ancelotti', '1959-06-10', 'Italy',       'Yes'),
(2,  'José',       'Mourinho',  '1963-01-26', 'Portugal',    'Yes'),
(3,  'Thomas',     'Tuchel',    '1973-08-29', 'Germany',     'Yes'),
(4,  'Zinedine',   'Zidane',    '1972-06-23', 'France',      'Yes'),
(5,  'Pep',        'Guardiola', '1971-01-18', 'Spain',       'Yes'),
(6,  'Jürgen',     'Klopp',     '1967-06-16', 'Germany',     'Yes'),
(7,  'Arne',       'Slot',      '1978-09-17', 'Netherlands', 'Yes'),
(8,  'Ole Gunnar', 'Solskjær',  '1973-02-26', 'Norway',      'Yes'),
(9,  'Mikel',      'Arteta',    '1982-03-26', 'Spain',       'Yes'),
(10, 'Diego',      'Simeone',   '1970-04-28', 'Argentina',   'Yes');

-- ----------------------------------------------------------------------------
-- ManagerTenures (21). end_date NULL = still in the job (Arteta, Simeone).
-- Several managers return to a club: Ancelotti and Zidane at Real Madrid,
-- Mourinho at Chelsea. Solskjaer has an Interim spell followed by a Head Coach
-- spell at Manchester United. Only spells at clubs in the Clubs table are
-- recorded.
-- ----------------------------------------------------------------------------
INSERT INTO ManagerTenures (tenure_id, manager_id, club_id, start_date, end_date, role) VALUES
(1,  1,  2,  '2009-07-01', '2011-05-22', 'Head Coach'),
(2,  1,  17, '2011-12-30', '2013-05-19', 'Head Coach'),
(3,  1,  9,  '2013-06-25', '2015-05-25', 'Head Coach'),
(4,  1,  14, '2016-07-01', '2017-09-28', 'Head Coach'),
(5,  1,  13, '2018-05-23', '2019-12-10', 'Head Coach'),
(6,  1,  9,  '2021-06-01', '2025-05-25', 'Head Coach'),
(7,  2,  2,  '2004-06-02', '2007-09-20', 'Head Coach'),
(8,  2,  12, '2008-06-02', '2010-05-28', 'Head Coach'),
(9,  2,  2,  '2013-06-03', '2015-12-17', 'Head Coach'),
(10, 2,  5,  '2016-05-27', '2018-12-18', 'Head Coach'),
(11, 3,  15, '2015-07-01', '2017-05-30', 'Head Coach'),
(12, 3,  2,  '2021-01-26', '2022-09-07', 'Head Coach'),
(13, 4,  9,  '2016-01-04', '2018-05-31', 'Head Coach'),
(14, 4,  9,  '2019-03-11', '2021-05-27', 'Head Coach'),
(15, 5,  4,  '2016-07-01', '2026-05-24', 'Head Coach'),
(16, 6,  3,  '2015-10-08', '2024-05-31', 'Head Coach'),
(17, 7,  3,  '2024-06-01', '2026-05-30', 'Head Coach'),
(18, 8,  5,  '2018-12-19', '2019-03-28', 'Interim'),
(19, 8,  5,  '2019-03-28', '2021-11-21', 'Head Coach'),
(20, 9,  1,  '2019-12-22', NULL,         'Head Coach'),
(21, 10, 11, '2011-12-23', NULL,         'Head Coach');

-- ----------------------------------------------------------------------------
-- Transfers (20). Fees in euros (base fee, excluding add-ons).
-- Types: 12 Permanent, 1 Loan (Mbappe to PSG, 2017), 7 Free.
-- Clubs with no recorded transfer (Chelsea, Inter Milan) and players with none
-- (Yamal, Saka) support LEFT JOIN and NOT IN queries.
-- A NULL from_club_id or to_club_id means free agent (see the conventions above);
-- De Gea's transfers 19 and 20 use it.
-- ----------------------------------------------------------------------------
INSERT INTO Transfers (transfer_id, player_id, from_club_id, to_club_id, transfer_date, fee, transfer_type) VALUES
(1,  14, 10, 17, '2017-08-03', 222000000, 'Permanent'),  -- Neymar, Barcelona to PSG (release clause)
(2,  5,  15, 10, '2017-08-25', 105000000, 'Permanent'),  -- Dembele, Dortmund to Barcelona (plus 40m add-ons)
(3,  2,  18, 17, '2017-08-31', 0,         'Loan'),       -- Mbappe, Monaco to PSG (loan, obligation to buy)
(4,  12, 10, 17, '2021-08-10', 0,         'Free'),       -- Messi, Barcelona to PSG (contract expired)
(5,  1,  15, 4,  '2022-05-10', 60000000,  'Permanent'),  -- Haaland, Dortmund to Manchester City (release clause)
(6,  13, 5,  20, '2022-12-30', 0,         'Free'),       -- Ronaldo, Manchester United to Al-Nassr (contract ended)
(7,  3,  15, 9,  '2023-06-14', 103000000, 'Permanent'),  -- Bellingham, Dortmund to Real Madrid
(8,  12, 17, 21, '2023-07-15', 0,         'Free'),       -- Messi, PSG to Inter Miami
(9,  4,  8,  1,  '2023-07-15', 116500000, 'Permanent'),  -- Rice, West Ham to Arsenal
(10, 5,  10, 17, '2023-08-12', 50400000,  'Permanent'),  -- Dembele, Barcelona to PSG
(11, 8,  6,  14, '2023-08-12', 100000000, 'Permanent'),  -- Kane, Tottenham to Bayern (plus 10m bonuses)
(12, 14, 17, 19, '2023-08-15', 90000000,  'Permanent'),  -- Neymar, PSG to Al-Hilal
(13, 2,  17, 9,  '2024-06-03', 0,         'Free'),       -- Mbappe, PSG to Real Madrid (contract expired)
(14, 9,  13, 17, '2025-01-17', 70000000,  'Permanent'),  -- Kvaratskhelia, Napoli to PSG (plus 10m bonuses)
(15, 15, 4,  13, '2025-06-12', 0,         'Free'),       -- De Bruyne, Manchester City to Napoli (contract expired)
(16, 6,  16, 3,  '2025-06-20', 117500000, 'Permanent'),  -- Wirtz, Leverkusen to Liverpool
(17, 7,  7,  3,  '2025-09-01', 144500000, 'Permanent'),  -- Isak, Newcastle to Liverpool
(18, 16, 11, 5,  '2011-07-01', 25000000,  'Permanent'),  -- De Gea, Atletico Madrid to Manchester United (reported fee varies, about 22.5-25m)
(19, 16, 5,  NULL, '2023-06-30', 0,       'Free'),       -- De Gea, Manchester United to free agent (contract expired)
(20, 16, NULL, 22, '2024-08-09', 0,       'Free');       -- De Gea, free agent to Fiorentina

-- ----------------------------------------------------------------------------
-- Contracts (5). Only contracts with a start date, an end year, and a reported
-- weekly wage in the sources are recorded. weekly_wage is in US dollars.
-- Messi's row is his October 2025 extension.
-- ----------------------------------------------------------------------------
INSERT INTO Contracts (contract_id, player_id, club_id, start_date, end_date, weekly_wage) VALUES
(1, 1,  4,  '2025-01-17', '2034-06-30', 700000),  -- Haaland, Manchester City (extension to 2034)
(2, 3,  9,  '2023-06-14', '2029-06-30', 460000),  -- Bellingham, Real Madrid (six-year contract)
(3, 8,  14, '2023-08-12', '2027-06-30', 550000),  -- Kane, Bayern Munich (four-year contract)
(4, 2,  9,  '2024-06-03', '2029-06-30', 690000),  -- Mbappe, Real Madrid (five-year contract)
(5, 12, 21, '2025-10-23', '2028-12-31', 545000);  -- Messi, Inter Miami (extension through 2028)

COMMIT;
