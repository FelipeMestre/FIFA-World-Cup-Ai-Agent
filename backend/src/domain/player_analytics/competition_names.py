"""Transfermarkt competition codes used by `real_player_season_stat`.

Names follow Transfermarkt's competition list. Two leagues both titled
"Premier Liga" are qualified by country so a row can be read on its own.
An unknown code is returned unchanged.
"""

_COMPETITION_NAMES: dict[str, str] = {
    "AFCN": "Africa Cup of Nations",
    "BE1": "Jupiler Pro League",
    "BESC": "Belgian Super Cup",
    "BPO4": "Jupiler Pro League Relegation Play-offs",
    "CDR": "Copa del Rey",
    "CGB": "EFL Cup",
    "CIT": "Coppa Italia",
    "CL": "Champions League",
    "CLQ": "Champions League qualifying",
    "DFB": "DFB-Pokal",
    "DFL": "DFL-Supercup",
    "DK1": "Superliga",
    "DKP": "Danish Cup",
    "ECLQ": "Conference League qualifying",
    "EJPL": "Jupiler Pro League Champions' Play-Offs",
    "EL": "Europa League",
    "ELQ": "Europa League qualifying",
    "ES1": "LaLiga",
    "FAC": "FA Cup",
    "FIWC": "World Cup",
    "FR1": "Ligue 1",
    "FRCH": "Trophée des Champions",
    "GB1": "Premier League",
    "GBCS": "Community Shield",
    "GR1": "Super League 1",
    "GRP": "Greek Cup",
    "IT1": "Serie A",
    "KLUB": "Club World Cup",
    "L1": "Bundesliga",
    "NL1": "Eredivisie",
    "NLP": "KNVB Beker",
    "NLSC": "Johan Cruijff Schaal",
    "PO1": "Liga Portugal",
    "POBE": "Jupiler Pro League Europe Play-Offs",
    "POCP": "Taça de Portugal",
    "POSU": "Portuguese Supercup",
    "RU1": "Russian Premier Liga",
    "RUP": "Russian Cup",
    "RUSS": "Russian Super Cup",
    "SC1": "Scottish Premiership",
    "SCI": "Supercoppa Italiana",
    "SFA": "SFA Cup",
    "SUC": "Supercopa",
    "TR1": "Süper Lig",
    "UKR1": "Ukrainian Premier Liga",
    "UKRP": "Ukrainian Cup",
    "USC": "UEFA Super Cup",
}


def competition_name(competition_id: str) -> str:
    return _COMPETITION_NAMES.get(competition_id, competition_id)
