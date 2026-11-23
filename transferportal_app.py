"""TransferPortal: interactive command-line application for the soccer transfer database.

Run with:  python3 transferportal_app.py
Options:   --rebuild   recreate transferportal.db from schema.sql and insert_data.sql first

This file handles the menu, input validation, and display. All SQL lives in db_access.py.
"""

import sqlite3
import sys
from datetime import date, datetime

import db_access as db

POSITIONS = ["Goalkeeper", "Defender", "Midfielder", "Forward"]
TRANSFER_TYPES = ["Permanent", "Loan", "Free"]


# A "club" that stands for no club: used when a player is released or signs as a free agent.
# It behaves like a club row (club_id, name) but its club_id is None, which is stored as NULL.
FREE_AGENT = {"club_id": None, "name": "Free agent"}
FREE_AGENT_WORDS = {"free agent", "free", "fa", "none"}


class Cancelled(Exception):
    """Raised when the user leaves a prompt blank to cancel the current operation."""


# ----------------------------------------------------------------------------
# Input helpers (every prompt validates and repeats until the input is acceptable)
# ----------------------------------------------------------------------------
def ask(label, required=True):
    """Read a line. A blank answer cancels the operation if required, else returns ''."""
    while True:
        text = input(f"{label}: ").strip()
        if text:
            return text
        if not required:
            return ""
        print("  (Blank input: operation cancelled.)")
        raise Cancelled


def ask_int(label, low=None, high=None, required=True):
    while True:
        text = ask(label, required)
        if text == "":
            return None
        try:
            value = int(text)
        except ValueError:
            print("  Please enter a whole number.")
            continue
        if (low is not None and value < low) or (high is not None and value > high):
            print(f"  Please enter a number between {low} and {high}.")
            continue
        return value


def ask_amount(label, required=True):
    """A non-negative amount in euros/dollars. Accepts 1000000 or 1,000,000 or 1.5m / 250k."""
    while True:
        text = ask(label, required)
        if text == "":
            return None
        cleaned = text.lower().replace(",", "").replace("$", "").replace("€", "")
        multiplier = 1
        if cleaned.endswith("m"):
            multiplier, cleaned = 1_000_000, cleaned[:-1]
        elif cleaned.endswith("k"):
            multiplier, cleaned = 1_000, cleaned[:-1]
        try:
            value = float(cleaned) * multiplier
        except ValueError:
            print("  Please enter a number such as 25000000, 25,000,000, 25m, or 150k.")
            continue
        if value < 0:
            print("  The amount cannot be negative.")
            continue
        return value


def ask_date(label, earliest=None, latest=None, required=True):
    """A real calendar date in YYYY-MM-DD form, optionally within a range."""
    while True:
        text = ask(label + " (YYYY-MM-DD)", required)
        if text == "":
            return None
        try:
            parsed = datetime.strptime(text, "%Y-%m-%d").date()
        except ValueError:
            print("  That is not a valid date. Use the form YYYY-MM-DD, e.g. 2026-07-01.")
            continue
        if earliest and parsed < earliest:
            print(f"  The date must be on or after {earliest}.")
            continue
        if latest and parsed > latest:
            print(f"  The date must be on or before {latest}.")
            continue
        return parsed.isoformat()


def ask_choice(label, options):
    """Pick one of a list of options by number or by typing its name."""
    for number, option in enumerate(options, start=1):
        print(f"  {number}. {option}")
    while True:
        text = ask(label)
        if text.isdigit() and 1 <= int(text) <= len(options):
            return options[int(text) - 1]
        for option in options:
            if text.lower() == option.lower():
                return option
        print(f"  Please choose 1-{len(options)} or type one of the names.")


def confirm(question):
    return input(f"{question} (y/n): ").strip().lower() in ("y", "yes")


# ----------------------------------------------------------------------------
# Display helpers
# ----------------------------------------------------------------------------
def money(value):
    return "-" if value is None else f"{value:,.0f}"


def print_table(rows, columns):
    """columns = [(heading, key, formatter, align)], rows = sqlite3.Row objects."""
    if not rows:
        print("  No records found.")
        return
    cells = [[fmt(row[key]) if fmt else str(row[key]) for _, key, fmt, _ in columns]
             for row in rows]
    widths = [max(len(col[0]), *(len(line[i]) for line in cells))
              for i, col in enumerate(columns)]
    header = "  ".join(col[0].ljust(widths[i]) if col[3] == "l" else col[0].rjust(widths[i])
                       for i, col in enumerate(columns))
    print("  " + header)
    print("  " + "  ".join("-" * w for w in widths))
    for line in cells:
        print("  " + "  ".join(
            line[i].ljust(widths[i]) if columns[i][3] == "l" else line[i].rjust(widths[i])
            for i in range(len(columns))))
    print(f"  ({len(rows)} row{'s' if len(rows) != 1 else ''})")


PLAYER_COLUMNS = [
    ("ID", "player_id", None, "r"),
    ("Player", "player", None, "l"),
    ("Nationality", "nationality", None, "l"),
    ("Position", "position", None, "l"),
    ("Market value (EUR)", "market_value", money, "r"),
    ("Active", "is_active", None, "l"),
]


# ----------------------------------------------------------------------------
# Lookups: let the user pick a player or club by ID or by part of the name
# ----------------------------------------------------------------------------
def show_selected_player(player, typed):
    """Tell the user exactly which player their input resolved to."""
    print(f"  Matched '{typed}' -> {player['player']} (ID {player['player_id']}, "
          f"{player['position']}, born {player['date_of_birth']})")


def show_selected_club(conn, club, typed):
    """Tell the user exactly which club their input resolved to, with its league so that
    similarly named clubs can be told apart."""
    detail = db.get_club_with_league(conn, club["club_id"])
    print(f"  Matched '{typed}' -> {detail['name']} (ID {detail['club_id']}, {detail['league']})")


def show_selected_league(league, typed):
    print(f"  Matched '{typed}' -> {league['name']} (ID {league['league_id']})")


def choose_player(conn):
    """Return a player row, or None if the user gave up. Accepts an ID or part of a name."""
    while True:
        text = ask("Player ID or part of the name")
        if text.isdigit():
            player = db.get_player(conn, int(text))
            if player:
                show_selected_player(player, text)
                return player
            print(f"  No player has ID {text}.")
            continue
        matches = db.search_players(conn, name=text)
        if len(matches) == 1:
            player = db.get_player(conn, matches[0]["player_id"])
            show_selected_player(player, text)
            return player
        if not matches:
            print(f"  No player matches '{text}'. Try again (blank to cancel).")
            continue
        print(f"  {len(matches)} players match. Enter one of these IDs:")
        print_table(matches, PLAYER_COLUMNS)


def choose_club(conn, label="Club ID or part of the name", allow_create=False,
                allow_free_agent=False):
    """Return a club row (club_id, name). With allow_create, a name that matches nothing can
    be added as a new club on the spot (including its league, which can also be new).
    With allow_free_agent, typing "free agent" returns FREE_AGENT (club_id None)."""
    while True:
        text = ask(label)
        if allow_free_agent and text.lower() in FREE_AGENT_WORDS:
            return FREE_AGENT
        if text.isdigit():
            club = db.get_club(conn, int(text))
            if club:
                show_selected_club(conn, club, text)
                return club
            print(f"  No club has ID {text}.")
            continue
        matches = db.list_clubs(conn, text)
        if len(matches) == 1:
            club = db.get_club(conn, matches[0]["club_id"])
            show_selected_club(conn, club, text)
            return club
        if not matches:
            if allow_create:
                club = create_club_interactive(conn, text)
                if club:
                    return club
            else:
                print(f"  No club matches '{text}'. Try again (blank to cancel).")
            continue
        print(f"  {len(matches)} clubs match. Enter one of these IDs:")
        print_table(matches, [("ID", "club_id", None, "r"), ("Club", "club", None, "l"),
                              ("City", "city", None, "l"), ("League", "league", None, "l")])


LEAGUE_COLUMNS = [
    ("ID", "league_id", None, "r"), ("League", "league", None, "l"),
    ("Country", "country", None, "l"), ("Tier", "tier", None, "r"),
    ("Clubs", "clubs", None, "r"),
]

TRANSFER_LIST_COLUMNS = [
    ("ID", "transfer_id", None, "r"), ("Date", "transfer_date", None, "l"),
    ("Player", "player_name", None, "l"), ("From", "from_club", None, "l"),
    ("To", "to_club", None, "l"), ("Fee (EUR)", "fee", money, "r"),
    ("Type", "transfer_type", None, "l"),
]


def choose_league(conn, label="League ID or part of the name", allow_create=True):
    """Return a league row (league_id, name). A name that matches nothing can be added as a
    new league on the spot."""
    while True:
        text = ask(label)
        if text.isdigit():
            league = db.get_league(conn, int(text))
            if league:
                show_selected_league(league, text)
                return league
            print(f"  No league has ID {text}.")
            continue
        matches = db.list_leagues(conn, text)
        if len(matches) == 1:
            league = db.get_league(conn, matches[0]["league_id"])
            show_selected_league(league, text)
            return league
        if not matches:
            if allow_create:
                league = create_league_interactive(conn, text)
                if league:
                    return league
            else:
                print(f"  No league matches '{text}'. Try again (blank to cancel).")
            continue
        print(f"  {len(matches)} leagues match. Enter one of these IDs:")
        print_table(matches, LEAGUE_COLUMNS)


def tidy_name(text):
    """Capitalize a name typed entirely in lowercase ("league one" -> "League One").
    Names typed with their own capitalization (such as "AS Monaco") are left alone."""
    return text.title() if text == text.lower() else text


def create_league_interactive(conn, typed):
    """Offer to add a league that was not found. Returns the new league row, or None."""
    if not confirm(f"No league matches '{typed}'. Add it as a new league?"):
        return None
    name = ask(f"Full league name (blank to keep '{tidy_name(typed)}')", required=False) or tidy_name(typed)
    if db.league_name_exists(conn, name):
        print(f"  A league named '{name}' already exists. Pick it from the list instead.")
        return None
    country = ask("Country")
    tier = ask_int("Tier (1 = top division, 2 = second division, ...)", 1, 10)
    new_id = db.add_league(conn, name, country, tier)
    print(f"  Added league '{name}' (league ID {new_id}).")
    return db.get_league(conn, new_id)


def create_club_interactive(conn, typed):
    """Offer to add a club that was not found, choosing or creating its league.
    Returns the new club row, or None."""
    if not confirm(f"No club matches '{typed}'. Add it as a new club?"):
        return None
    name = ask(f"Full club name (blank to keep '{tidy_name(typed)}')", required=False) or tidy_name(typed)
    if db.club_name_exists(conn, name):
        print(f"  A club named '{name}' already exists. Pick it from the list instead.")
        return None
    city = ask("City")
    founded = ask_int(f"Year founded (1800-{date.today().year})", 1800, date.today().year)
    print("\nLeagues (type a name that is not listed to add a new league):")
    print_table(db.list_leagues(conn), LEAGUE_COLUMNS)
    league = choose_league(conn, "League ID or part of the name")
    new_id = db.add_club(conn, name, city, founded, league["league_id"])
    print(f"  Added club '{name}' in {league['name']} (club ID {new_id}).")
    return db.get_club(conn, new_id)


# ----------------------------------------------------------------------------
# Error handling: turn database errors into short, readable messages
# ----------------------------------------------------------------------------
def explain_db_error(error):
    message = str(error)
    if isinstance(error, sqlite3.IntegrityError):
        if "UNIQUE" in message:
            return "That record already exists (duplicate value)."
        if "FOREIGN KEY" in message:
            return "That record is linked to other records, or refers to one that does not exist."
        if "CHECK" in message:
            return "The values break a database rule (for example, an invalid date range or amount)."
        if "NOT NULL" in message:
            return "A required value is missing."
        return "The database rejected the change (constraint violation)."
    return "The database operation failed. Nothing was changed."


# ----------------------------------------------------------------------------
# The menu operations
# ----------------------------------------------------------------------------
def op_search_players(conn):
    """1. Search or browse: filter players by name, position, and minimum market value."""
    print("\nSearch players (leave a filter blank to skip it).")
    name = ask("Part of the name", required=False)
    position = None
    pos_text = ask("Position (Goalkeeper/Defender/Midfielder/Forward)", required=False)
    if pos_text:
        matches = [p for p in POSITIONS if p.lower() == pos_text.lower()]
        if not matches:
            print("  Unknown position. Position filter ignored.")
        else:
            position = matches[0]
    min_value = ask_amount("Minimum market value in EUR (e.g. 50m)", required=False)
    rows = db.search_players(conn, name or None, position, min_value)
    print()
    print_table(rows, PLAYER_COLUMNS)


def op_player_profile(conn):
    """2. Related data: a player's details, transfer history, and contracts (several joins)."""
    print("\nPlayer profile")
    player = choose_player(conn)
    print(f"\n{player['player']}  |  {player['position']}  |  {player['nationality']}  |  "
          f"born {player['date_of_birth']}  |  market value EUR {money(player['market_value'])}")
    print("\nTransfer history:")
    print_table(db.player_transfer_history(conn, player["player_id"]), [
        ("Transfer ID", "transfer_id", None, "r"),
        ("Date", "transfer_date", None, "l"),
        ("From", "from_club", None, "l"),
        ("To", "to_club", None, "l"),
        ("League", "league", None, "l"),
        ("Fee (EUR)", "fee", money, "r"),
        ("Type", "transfer_type", None, "l"),
    ])
    print("\nContracts:")
    print_table(db.player_contracts(conn, player["player_id"]), [
        ("Club", "club", None, "l"),
        ("Start", "start_date", None, "l"),
        ("End", "end_date", None, "l"),
        ("Weekly wage (USD)", "weekly_wage", money, "r"),
    ])


def op_add_player(conn):
    """3. Add data: insert a new player."""
    print("\nAdd a player (leave any required field blank to cancel).")
    first = ask("First name")
    last = ask("Last name")
    dob = ask_date("Date of birth", earliest=date(1950, 1, 1), latest=date.today())
    nationality = ask("Nationality")
    position = ask_choice("Position", POSITIONS)
    value = ask_amount("Market value in EUR (e.g. 40m)")
    if db.player_exists(conn, first, last, dob):
        print(f"  {first} {last} (born {dob}) is already in the database. Nothing added.")
        return
    new_id = db.add_player(conn, first, last, dob, nationality, position, value)
    print(f"  Added {first} {last} with player ID {new_id}.")


def op_update_market_value(conn):
    """4a. Update data: change a player's market value."""
    print("\nUpdate a player's market value")
    player = choose_player(conn)
    print(f"  {player['player']} is currently valued at EUR {money(player['market_value'])}.")
    new_value = ask_amount("New market value in EUR (e.g. 90m)")
    if not confirm(f"Change value to EUR {money(new_value)}?"):
        print("  No changes made.")
        return
    changed = db.update_market_value(conn, player["player_id"], new_value)
    print("  Market value updated." if changed else "  Player not found. Nothing changed.")


def op_delete_transfer(conn):
    """4b. Delete data: remove a transfer entered by mistake."""
    print("\nDelete a transfer record (for entries made by mistake)")
    player = choose_player(conn)
    history = db.player_transfer_history(conn, player["player_id"])
    if not history:
        print(f"  {player['player']} has no transfers recorded.")
        return
    print_table(history, [
        ("Transfer ID", "transfer_id", None, "r"), ("Date", "transfer_date", None, "l"),
        ("From", "from_club", None, "l"), ("To", "to_club", None, "l"),
        ("Fee (EUR)", "fee", money, "r"), ("Type", "transfer_type", None, "l"),
    ])
    transfer_id = ask_int("ID of the transfer to delete")
    transfer = db.get_transfer(conn, transfer_id)
    if transfer is None:
        print(f"  Transfer {transfer_id} does not exist.")
        return
    if transfer["player"] != player["player"]:
        print("  That transfer belongs to a different player. Nothing deleted.")
        return
    print("  Any contract at the buying club that started on the transfer date is removed too.")
    if not confirm(f"Delete {transfer['player']}: {transfer['from_club']} -> "
                   f"{transfer['to_club']} on {transfer['transfer_date']}?"):
        print("  No changes made.")
        return
    transfers_deleted, contracts_deleted = db.delete_transfer(conn, transfer_id)
    if transfers_deleted:
        print(f"  Transfer deleted ({contracts_deleted} linked contract(s) removed).")
    else:
        print("  Transfer not found. Nothing deleted.")


def op_reports(conn):
    """5. Summary or report: club spending (view) and average fee per league (aggregate)."""
    print("\nReports")
    choice = ask_choice("Choose a report", [
        "Club spending and income (v_club_transfer_balance view)",
        "Permanent transfers by league (count, total, average fee)",
    ])
    print()
    if choice.startswith("Club"):
        print_table(db.club_balance_report(conn), [
            ("Club", "club", None, "l"), ("League", "league", None, "l"),
            ("Bought", "players_bought", None, "r"), ("Spent (EUR)", "total_spent", money, "r"),
            ("Sold", "players_sold", None, "r"), ("Received (EUR)", "total_received", money, "r"),
            ("Net spend (EUR)", "net_spend", money, "r"),
        ])
    else:
        print_table(db.league_fee_report(conn), [
            ("League", "league", None, "l"), ("Transfers", "transfers", None, "r"),
            ("Total fees (EUR)", "total_fees", money, "r"),
            ("Average fee (EUR)", "average_fee", money, "r"),
        ])


def op_record_transfer(conn):
    """6. Additional operation: record a signing (transfer + contract in one transaction)."""
    print("\nRecord a transfer (leave a required field blank to cancel).")
    player = choose_player(conn)
    # The date comes first because the selling club is the club the player was at on that
    # date. This also lets a career be entered out of order (back-filling earlier moves).
    transfer_date = ask_date("Transfer date", earliest=date(1950, 1, 1))
    known, from_id = db.club_on_date(conn, player["player_id"], transfer_date)
    if known:
        from_club = FREE_AGENT if from_id is None else db.get_club(conn, from_id)
        print(f"  On {transfer_date}, {player['player']} was at: {from_club['name']}.")
    else:
        print(f"  No earlier transfer is recorded for {player['player']} before {transfer_date}.")
        from_club = choose_club(conn, "Selling club: ID, part of the name, or 'free agent'",
                                allow_create=True, allow_free_agent=True)
        from_id = from_club["club_id"]
    to_club = choose_club(conn, "Buying club: ID, part of the name, or 'free agent'",
                          allow_create=True, allow_free_agent=True)
    if to_club["club_id"] == from_id:
        if from_id is None:
            print("  The selling and buying side cannot both be free agent. Nothing recorded.")
        else:
            print("  The player is already at that club. Nothing recorded.")
        return
    if from_id is None or to_club["club_id"] is None:
        transfer_type, fee = "Free", 0.0
        print("  A move to or from a free agent is recorded as a Free transfer with fee 0.")
    else:
        transfer_type = ask_choice("Transfer type", TRANSFER_TYPES)
        if transfer_type == "Free":
            fee = 0.0
            print("  Free transfers have a fee of 0.")
        else:
            fee = ask_amount("Fee in EUR (0 for an undisclosed loan fee)")
    contract_end = weekly_wage = None
    if to_club["club_id"] is not None and confirm("Also record the new contract at the buying club?"):
        contract_end = ask_date("Contract end date", earliest=date.fromisoformat(transfer_date))
        if contract_end <= transfer_date:
            print("  The contract must end after the transfer date. Nothing recorded.")
            return
        weekly_wage = ask_amount("Weekly wage in USD")
        if weekly_wage <= 0:
            print("  The weekly wage must be greater than 0. Nothing recorded.")
            return
    new_id, relinked = db.record_transfer(conn, player["player_id"], to_club["club_id"],
                                          transfer_date, fee, transfer_type,
                                          contract_end, weekly_wage, from_club_id=from_id)
    saved = "transfer and contract" if contract_end else "transfer"
    print(f"  Saved {saved} (transfer ID {new_id}): {player['player']}, "
          f"{from_club['name']} to {to_club['name']}.")
    if relinked:
        print("  The player's next recorded transfer now shows this club as its selling club.")


def op_contracts_expiring(conn):
    """7. Additional operation: contracts ending within the next N months."""
    print("\nContracts expiring soon")
    months = ask_int("Look ahead how many months (1-120)", 1, 120)
    print()
    print_table(db.contracts_expiring(conn, months), [
        ("Player", "player", None, "l"), ("Club", "club", None, "l"),
        ("Contract ends", "end_date", None, "l"), ("Weekly wage (USD)", "weekly_wage", money, "r"),
    ])


def op_club_profile(conn):
    """Related data: a club's details, current manager, and the players currently there."""
    print("\nClub profile")
    club = db.get_club_details(conn, choose_club(conn)["club_id"])
    print(f"\n{club['name']}  |  {club['city']}  |  founded {club['founded_year']}  |  "
          f"{club['league']} ({club['country']})")
    print("\nCurrent manager:")
    print_table(db.club_current_managers(conn, club["club_id"]), [
        ("Manager", "manager_name", None, "l"), ("Role", "role", None, "l"),
        ("In charge since", "start_date", None, "l"),
    ])
    print("\nPlayers currently at the club (their latest recorded transfer was here):")
    print_table(db.club_current_players(conn, club["club_id"]), [
        ("ID", "player_id", None, "r"), ("Player", "player", None, "l"),
        ("Position", "position", None, "l"), ("Joined", "transfer_date", None, "l"),
        ("Type", "transfer_type", None, "l"),
    ])


def op_recent_transfers(conn):
    """The ten most recent transfers, newest first."""
    print("\nTen most recent transfers")
    print()
    print_table(db.recent_transfers(conn, 10), TRANSFER_LIST_COLUMNS)


def op_top_transfers(conn):
    """The most expensive transfers, optionally within the last N years."""
    print("\nMost expensive transfers (leave a prompt blank to use its default)")
    years = ask_int("Look back how many years (blank = all time)", 1, 100, required=False)
    limit = ask_int("How many to show (blank = 10)", 1, 100, required=False) or 10
    span = f"the last {years} year(s)" if years else "all time"
    print(f"\nTop {limit} most expensive transfers, {span}:")
    print_table(db.top_transfers(conn, years, limit), TRANSFER_LIST_COLUMNS)


def op_add_club_or_league(conn):
    """Add data: a new league, or a new club in an existing league."""
    print("\nAdd a club or a league (leave a required field blank to cancel).")
    what = ask_choice("What do you want to add?", ["A club", "A league"])
    if what == "A league":
        name = ask("League name")
        if db.league_name_exists(conn, name):
            print(f"  A league named '{name}' already exists. Nothing added.")
            return
        country = ask("Country")
        tier = ask_int("Tier (1 = top division, 2 = second division, ...)", 1, 10)
        new_id = db.add_league(conn, name, country, tier)
        print(f"  Added league '{name}' with league ID {new_id}.")
        return
    name = ask("Club name")
    if db.club_name_exists(conn, name):
        print(f"  A club named '{name}' already exists. Nothing added.")
        return
    city = ask("City")
    founded = ask_int(f"Year founded (1800-{date.today().year})", 1800, date.today().year)
    print("\nLeagues (type a name that is not listed to add a new league):")
    print_table(db.list_leagues(conn), LEAGUE_COLUMNS)
    league = choose_league(conn, "League ID or part of the name")
    new_id = db.add_club(conn, name, city, founded, league["league_id"])
    print(f"  Added club '{name}' in {league['name']} with club ID {new_id}.")


def op_move_club(conn):
    """Update data: change a club's league (promotion or relegation). Can repeat quickly."""
    print("\nMove clubs between leagues (promotion / relegation)")
    while True:
        club = db.get_club_with_league(conn, choose_club(conn)["club_id"])
        print(f"  {club['name']} is currently in {club['league']}.")
        print_table(db.list_leagues(conn), LEAGUE_COLUMNS)
        league = choose_league(conn, "New league: ID or part of the name")
        if league["league_id"] == club["league_id"]:
            print("  The club is already in that league. No change.")
        elif confirm(f"Move {club['name']} from {club['league']} to {league['name']}?"):
            changed = db.move_club_to_league(conn, club["club_id"], league["league_id"])
            print("  League updated." if changed else "  Club not found. Nothing changed.")
        else:
            print("  No changes made.")
        if not confirm("Move another club?"):
            break


MENU = [
    ("Search players (by name, position, minimum value)", op_search_players),
    ("Player profile: transfer history and contracts", op_player_profile),
    ("Club profile: manager and current players", op_club_profile),
    ("Ten most recent transfers", op_recent_transfers),
    ("Most expensive transfers (all time or last N years)", op_top_transfers),
    ("Add a new player", op_add_player),
    ("Add a new club or league", op_add_club_or_league),
    ("Move a club to a different league (promotion/relegation)", op_move_club),
    ("Update a player's market value", op_update_market_value),
    ("Delete a transfer record", op_delete_transfer),
    ("Reports: club spending, average fee by league", op_reports),
    ("Record a transfer (with optional new contract)", op_record_transfer),
    ("Contracts expiring soon", op_contracts_expiring),
]


# ----------------------------------------------------------------------------
# Main loop
# ----------------------------------------------------------------------------
def show_menu():
    print("\n=== TransferPortal ===")
    for number, (title, _) in enumerate(MENU, start=1):
        print(f"  {number}. {title}")
    print("  0. Quit")


def main():
    if "--rebuild" in sys.argv:
        db.rebuild_database()
        print("Database rebuilt from schema.sql and insert_data.sql.")

    if not db.DB_PATH.exists():
        print(f"Database file not found: {db.DB_PATH}")
        print("Create it first with:  python3 transferportal_app.py --rebuild")
        return 1

    conn = None
    try:
        conn = db.connect()
        if not db.database_is_ready(conn):
            print("The database is missing tables. Run:  python3 transferportal_app.py --rebuild")
            return 1
        while True:
            show_menu()
            try:
                choice = input("Choose an option: ").strip()
            except EOFError:
                break
            if choice == "0":
                break
            if not choice.isdigit() or not 1 <= int(choice) <= len(MENU):
                print(f"  Please enter a number from 0 to {len(MENU)}.")
                continue
            try:
                MENU[int(choice) - 1][1](conn)
            except Cancelled:
                pass
            except EOFError:
                break
            except sqlite3.Error as error:
                print(f"  Could not complete the operation: {explain_db_error(error)}")
    except sqlite3.Error:
        print("Could not open the database. Check the file path and try --rebuild.")
        return 1
    except KeyboardInterrupt:
        print()
    finally:
        if conn is not None:
            conn.close()
    print("Goodbye.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
