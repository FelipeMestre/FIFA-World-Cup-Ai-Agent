"""Expected facts for the golden fixture, written by hand from the story in `fixture_data`.

These are literals on purpose: deriving them with code would mirror the logic under test.
Story recap (dates 2026): Valdoria beat Karsovia 2-1 (group, 14 Jun), beat Sérvenia 3-0
(group, 20 Jun, Sérvenia at home), then drew the final 1-1 with Karsovia, losing 3-4 on
penalties (19 Jul, Karsovia at home).
"""

# --- Team analysis: Valdoria (3 matches, ordered by date: group KRS, group SRV, final KRS) ---
VALDORIA_SCOPE_LABEL = "WC 2026 · 3 matches"
VALDORIA_RECORD = {"won": 2, "drawn": 0, "lost": 1, "goals_for": 6, "goals_against": 2}
VALDORIA_GOAL_DIFFERENCE = 4
VALDORIA_CONCEDED_PER_GAME = 0.67
VALDORIA_CLEAN_SHEETS = 1
VALDORIA_AVG_POSSESSION = 57.0  # (58 + 53 + 60) / 3
VALDORIA_STANDING_LABEL = "Final · out 1–1 to Karsovia"
VALDORIA_STAGE_CAPTION = "Group Stage to Final"
VALDORIA_MATCH_RESULTS = [
    ("Group Stage", "KRS", "2–1", "W"),
    ("Group Stage", "SRV", "3–0", "W"),
    ("Final", "KRS", "1–1", "L"),  # lost the shootout 3-4
]
VALDORIA_DISCIPLINE = {"yellow_cards": 2, "red_cards": 0, "fouls": 27, "yellow_per_match": 0.67}
VALDORIA_GROUP = {"played": 2, "points": 6, "goal_difference": 4}  # knockout excluded
VALDORIA_ROSTER_SIZE = 5
VALDORIA_TOP_SCORER = "Rafael Ortegon"

KARSOVIA_RECORD = {"won": 1, "drawn": 0, "lost": 1, "goals_for": 2, "goals_against": 3}
KARSOVIA_GROUP = {"played": 1, "points": 0, "goal_difference": -1}
SERVENIA_RECORD = {"won": 0, "drawn": 0, "lost": 1, "goals_for": 0, "goals_against": 3}

# --- Team comparison: Valdoria (a) vs Karsovia (b) ---
VLD_KRS_COMPARISON_ID = "995001-vs-995002"
VLD_KRS_MEETINGS = [
    # (stage, team_a_score, team_b_score, team_a_result, penalty_score from team a's side)
    ("Group Stage", 2, 1, "W", None),
    ("Final", 1, 1, "L", "3–4"),
]
VALDORIA_SQUAD_MARKET_VALUE = 135_000_000  # 60 + 25 + 30 + 12 + 8 million
KARSOVIA_SQUAD_MARKET_VALUE = 35_000_000  # 20 + 15 million
KARSOVIA_ROSTER_SIZE = 2

# --- Player analysis (World Cup path) ---
ORTEGON_SCOPE_LABEL = "WC 2026 · 3 apps"
ORTEGON_FOOTER = "3 apps · 270 min · verified 2026-07-20"
ORTEGON_GOALS_PER_90 = "1.33"  # 4 * 90 / 270
MONTEFUSCO_GOALS_PER_90 = "0.75"  # 2 * 90 / 240
SANTORINI_CHIPS = {"Saves": "11", "Conceded": "2", "Clean sheets": "1"}

# --- Player analysis (Transfermarkt career) ---
ORTEGON_CLUB_PROFILE = {
    "preferred_foot": "left",
    "sub_position": "Centre-Forward",
    "height_cm": 184,
    "citizenship": "Valdoria",
    "current_club": "Valdoria City FC",
    "market_value_eur": 55_000_000,
    "highest_market_value_eur": 70_000_000,
    "international_caps": 41,
    "international_goals": 19,
    "is_retired": False,
}
ORTEGON_TRANSFER_DATES = ["2018-07-01", "2022-07-01"]  # oldest first
ORTEGON_CAREER_SEASONS = {
    # (season, competition) -> (team that year, appearances, goals)
    ("2025", "Premier League"): ("Valdoria City FC", 30, 18),
    ("2025", "Champions League"): ("Valdoria City FC", 8, 5),
    ("2024", "Premier League"): ("Valdoria City FC", 28, 12),
}
HALDORSEN_CAREER_TOTALS = {"appearances": 36, "minutes": 2600, "goals": "9", "assists": "3"}
HALDORSEN_TEAM_CODE = "Harbor United"
VERIDIAN_TEAM_CODE = "Karsovia Dynamo"
RETIRED_TEAM_CODE = "RETIRED"
FREE_AGENT_TEAM_CODE = "FREE"

# --- Match analysis ---
GROUP_VLD_KRS_ID = "995001"
FINAL_KRS_VLD_ID = "995002"
GROUP_SRV_VLD_ID = "995003"
GROUP_VLD_KRS_SCORERS = ("Rafael Ortegon 23' · Rafael Ortegon 78'", "Mateo Ravelli 55'")
FINAL_SCORERS = ("Mateo Ravelli 12'", "Dario Montefusco 88'")
SERVENIA_VLD_AWAY_SCORERS = "Rafael Ortegon 10' · Rafael Ortegon 60' · Dario Montefusco 80'"
AMBIGUOUS_CANDIDATES = [
    # (match id, stage, date label, home code, away code, score)
    ("995001", "Group Stage", "Jun 14, 2026", "VLD", "KRS", "2–1"),
    ("995002", "Final", "Jul 19, 2026", "KRS", "VLD", "1–1"),
]

# --- query_player_stats: World Cup, restricted to one team via the nationality filter ---
# Valdoria players by goals desc; ties at 0 goals break on minutes desc then player id.
VALDORIA_BY_GOALS = [
    "Rafael Ortegon",
    "Dario Montefusco",
    "Tomás Peñaranda",
    "Emilio Santorini",
    "Mateo Ravelli",
]
VALDORIA_FORWARDS_BY_GOALS = ["Rafael Ortegon", "Dario Montefusco"]
VALDORIA_ZERO_GOAL_PLAYERS = {"Tomás Peñaranda", "Emilio Santorini", "Mateo Ravelli"}
# Club seasons (approved links only): Ortegon is the one linked Valdoria player.
ORTEGON_CLUB_GOALS = {
    "2025 all competitions": "23",  # 18 league + 5 Champions League
    "2025 Premier League": "18",
    "2024 + 2025 all competitions": "35",  # 12 + 18 + 5
}
