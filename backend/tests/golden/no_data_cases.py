"""Map of the no-data shapes of every chat tool, derived from reading the code.

"No data" means the data a request needs does not exist. Each row is one distinct shape the
code actually has and the test that pins it. "Covered" rows live in the original golden
modules and are not repeated. Rows marked FINDING pin only the safe invariant (no crash, or
the observable fields that are clearly intended); the questionable behavior is reported, not
locked in. Entities come from `fixture_empty` (same ID ranges and cleanup as the rest).

get_team_analysis
  unknown / misspelled team ........ covered: test_team_analysis.py::
                                     test_unresolvable_team_returns_not_found_error_without_widget
  team, roster, zero matches ....... test_no_data_team.py::
                                     test_team_that_never_played_reports_a_zero_record_...
                                     (widget IS emitted, all zeros / "Did not qualify")
  zero-match team: lists, discipline test_..._has_empty_match_lists_and_zero_discipline
  zero-match team: no leaders ...... test_..._has_no_squad_leaders_even_with_a_roster
  roster rows with 0 min / NULL .... test_roster_players_without_matches_are_listed_...
  no roster and no matches ......... test_team_without_a_roster_or_matches_has_an_empty_squad
  players but nobody scored ........ test_team_whose_players_never_scored_has_no_top_scorer_...
  scheduled (unplayed) match ....... FINDING F4: counted as a played draw; not pinned

get_team_comparison
  unknown second team / same team .. covered: test_team_comparison.py (unknown B, same team)
  unknown first team / both unknown  test_no_data_team.py::
                                     test_unknown_first_team_is_the_one_named_in_the_error
  both teams without matches ....... test_comparing_two_teams_that_never_played_...
  one team without matches ......... test_comparing_a_team_with_results_against_one_...

get_player_analysis
  unknown player ................... covered: test_player_analysis.py (not found, no widget)
  roster player, no stat/no career . covered: test_player_analysis.py::
                                     test_roster_player_without_stats_or_career_is_reported_...
  roster player, no stat, same-name  covered: ..._falls_back_to_same_named_career
  pending link / no approved link .. covered: test_pending_identity_link_does_not_attach_...
  retired / free-agent career ...... covered: test_career_only_player_with_old_last_season_...
  stat row of 0 minutes ............ test_no_data_player.py::
                                     test_player_with_a_stat_row_of_zero_minutes_...
  approved link, empty career ...... test_approved_link_to_a_career_without_seasons_...
  GK, saves/clean sheets NULL ...... test_goalkeeper_with_unmeasured_saves_shows_dash_chips_...
  no link of any kind .............. test_wc_player_without_any_identity_link_has_no_club_data
  career record, no seasons ........ test_career_record_with_no_seasons_no_transfers_...
  discipline / tier on empty data .. FINDING F3: "Clean record" / peer-dependent tier; not pinned

get_player_comparison
  unknown second / same / no stats B covered: test_player_comparison.py
  unknown first player ............. test_no_data_player.py::
                                     test_unknown_first_player_is_the_one_named_in_the_error
  no stats on first / both ......... test_comparing_a_player_without_stats_in_first_position_...
                                     test_when_both_players_lack_stats_the_first_one_is_reported
  resolve order (name before stats)  test_unknown_player_is_reported_before_a_missing_stat_row
  zero-minute player ............... test_comparison_with_a_zero_minute_player_...
  GK vs GK with unmeasured saves ... test_goalkeeper_comparison_drops_the_rows_...
  GK vs outfield (no shared stats) . covered: test_goalkeeper_only_rows_are_dropped_when_...
  career-only player ............... test_career_only_player_cannot_be_compared_...

get_match_analysis
  unknown team / never met /
  stage or date matches nothing .... covered: test_match_analysis.py::
                                     test_no_matching_fixture_returns_not_found_error_...
  scheduled match, no events/stats/
  lineups .......................... test_no_data_match.py::
                                     test_scheduled_match_with_no_events_stats_or_lineups_...
                                     test_match_without_team_stats_shows_zero_values_...
                                     test_match_without_lineups_returns_both_teams_...
  no Player of the Match ........... not applicable: NOT NULL foreign key in the schema;
                                     test_player_of_the_match_is_always_present_...
  no venue ......................... not applicable: NOT NULL foreign key in the schema
  scheduled match score ............ FINDING F5: reads as 0-0; only status_label is pinned
  teams without matches / same team
  twice / unknown first team ....... test_pairs_that_cannot_have_a_match_return_the_not_found_...
  empty stage / date strings ....... test_empty_string_selectors_are_ignored_...
  malformed date ................... test_malformed_date_raises_value_error_... (FINDING F1)

query_player_stats
  filters match nobody / unknown
  competition / args-model errors .. covered: test_query_player_stats.py
  zero-minute players, total sort .. test_no_data_ranking.py::
                                     test_players_with_zero_minutes_still_rank_by_a_total_stat
  per-90 sort without minutes ...... test_per_90_sort_over_players_with_no_minutes_is_empty
  GK totals never measured ......... test_goalkeeper_total_sort_skips_a_keeper_...
  team without roster / unknown
  nationality / absent position /
  height / age ..................... test_world_cup_filters_that_match_no_roster_row_...
  roster rows without stat row ..... test_roster_players_without_a_stat_row_are_absent_...
  club window: approved link without
  seasons, no approved links, empty
  season window, empty competition,
  unlinked GK, HAVING filter ....... test_club_seasons_window_without_matching_linked_rows_...
  unrecognised season label ........ test_unrecognised_season_label_is_rejected_...
  pending-link players only ........ covered: test_query_player_stats.py::
                                     test_club_seasons_sum_only_approved_linked_players

get_current_utc_time
  not applicable: reads the clock only, so no request can lack its data.

Name inputs (all name-taking tools), test_no_data_input_edges.py
  unresolvable text, longest allowed,
  quotes, SQL text, unicode ........ test_unresolvable_text_is_reported_as_an_error_...
  over 128 characters .............. test_name_longer_than_the_limit_is_rejected_...
  trimmed team names ............... test_team_name_with_surrounding_spaces_is_not_trimmed_...
  %, _, blank, padded .............. test_wildcard_blank_and_padded_names_never_crash_...
                                     (FINDING F2)

Tool loop and chat service, test_no_data_chat_flow.py
  error content handed to the model,
  no widget, no ToolWidgetResult ... test_no_data_result_is_handed_to_the_model_as_an_error_...
  existing-but-empty entity ........ test_team_that_exists_but_never_played_still_emits_a_widget_...
  over-long name via executor ...... test_overlong_name_is_rejected_to_the_model_...
  malformed date via executor ...... test_malformed_match_date_escapes_the_tool_loop_... (F1)
  first message, empty history and
  empty cache ...................... test_first_message_with_empty_history_and_cache_...
  cache write after a not-found turn test_not_found_tool_result_leaves_the_turn_without_widgets_...
  (also covered with fakes: tests/unit/domain/chat/test_chat_service_history_rebuild.py)

Findings (reported, see the task report): F1 malformed `date` raises an uncaught ValueError;
F2 `%` and `_` are unescaped LIKE wildcards and blank or padded player names change which
data source answers; F3 a player with no data is labelled "Clean record" and gets a
peer-dependent tier; F4 a scheduled match counts as a played draw in team records; F5 a
scheduled match is served with a 0-0 score.
"""

# Names that exist nowhere in the shared dev database: clearly fictional and long enough
# that the substring tier of every resolver cannot hit a real row.
UNKNOWN_TEAM = "Zorblaxia Quentarium"
UNKNOWN_PLAYER = "Quillon Zorbathrax Vexmoor"
UNKNOWN_TEAM_ERROR = f"No team found matching '{UNKNOWN_TEAM}'."
UNKNOWN_PLAYER_ERROR = f"No player found matching '{UNKNOWN_PLAYER}'."

NO_PLAYERS_MATCHED_ERROR = "No players matched those filters."
