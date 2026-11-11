"""IPL cricket dashboard: team results, strike rate per game, batting and bowling, read from
the DuckDB warehouse that `make gold` builds.

Season marts keep raw sums (runs, balls, dismissals), so "All seasons" adds those up and
recomputes averages and rates, rather than averaging averages.
"""

from __future__ import annotations

import os
from pathlib import Path

import altair as alt
import duckdb
import pandas as pd
import streamlit as st

WAREHOUSE = Path(os.environ.get("IPL_DATA_DIR", "data")) / "gold" / "warehouse.duckdb"
ALL = "All"
# Small samples make rates noisy; these keep leaderboards honest.
MIN_BALLS_FACED = 100
MIN_BALLS_BOWLED = 120
MIN_MATCHUP_BALLS = 12
OUTCOME_COLOURS = alt.Scale(domain=["Won", "Lost"], range=["#2a78d6", "#eb6834"])

st.set_page_config(page_title="IPL cricket analytics", page_icon="🏏", layout="wide")

# Recessive axes: no domain line or ticks, light dashed grid, so the marks carry the chart.
QUIET_X = {"domain": False, "ticks": False, "grid": False, "labelPadding": 6}
QUIET_Y = {"domain": False, "ticks": False, "gridDash": [2, 3], "labelPadding": 6}
PAD = {"left": 16, "right": 12, "top": 4, "bottom": 4}


@st.cache_data
def query(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Run one read-only query. Cached, because the marts only change when `make gold` runs."""
    with duckdb.connect(str(WAREHOUSE), read_only=True) as con:
        return con.execute(sql, list(params)).df()


def where(season: int | None, team: str | None, team_col: str = "team") -> tuple[str, tuple]:
    """SQL filter and parameters for the season and team pickers."""
    clauses, params = ["1 = 1"], []
    if season is not None:
        clauses.append("season = ?")
        params.append(season)
    if team is not None:
        clauses.append(f"{team_col} = ?")
        params.append(team)
    return " and ".join(clauses), tuple(params)


def safe_ratio(num: pd.Series, den: pd.Series, scale: float = 1) -> pd.Series:
    return (scale * num / den.where(den > 0)).round(2)


def overs(balls: pd.Series) -> pd.Series:
    """Legal balls as cricket overs, e.g. 27 -> '4.3'."""
    return (balls // 6).astype(int).astype(str) + "." + (balls % 6).astype(int).astype(str)


def card(title: str, subtitle: str | None = None):
    box = st.container(border=True)
    box.markdown(f"**{title}**")
    if subtitle:
        box.caption(subtitle)
    return box


if not WAREHOUSE.exists():
    st.error(f"No warehouse at {WAREHOUSE}. Run `make gold` first.")
    st.stop()

# --- Header and filters ---------------------------------------------------------------------

seasons = query("select distinct season from mart_team_season_results order by season desc")
season_options = [ALL, *seasons["season"].tolist()]
head, pick_season, pick_team = st.columns([3, 1, 1.4], vertical_alignment="bottom")
with pick_season:
    season_pick = st.selectbox("Season", season_options, index=1)
season = None if season_pick == ALL else int(season_pick)
team_sql, team_params = where(season, None)
teams = query(
    f"select distinct team from mart_team_season_results where {team_sql} order by team",
    team_params,
)["team"].tolist()
with pick_team:
    team_pick = st.selectbox("Team", [ALL, *teams])
team = None if team_pick == ALL else team_pick
with head:
    st.title("IPL cricket analytics")
    st.caption(
        "Ball-by-ball data from [Cricsheet](https://cricsheet.org) (ODC-By). "
        "Renamed franchises roll up to today's names; super overs are left out of player stats."
    )

flt, params = where(season, team)

# --- Headline tiles -------------------------------------------------------------------------

totals = query(
    f"""select count(distinct match_id) as matches, sum(runs_off_bat) as runs,
               sum(balls_faced) as balls, sum(sixes) as sixes
        from mart_team_match_batting where {flt}""",
    params,
).iloc[0]
top_bat = query(
    f"""select batter, sum(runs) as runs from mart_batter_season where {flt}
        group by batter order by runs desc limit 1""",
    params,
)
top_bowl = query(
    f"""select bowler, sum(wickets) as wickets from mart_bowler_season where {flt}
        group by bowler order by wickets desc, sum(runs_conceded) limit 1""",
    params,
)
tiles = st.columns(5)
tiles[0].metric("Matches", f"{int(totals.matches):,}", border=True)
tiles[1].metric(
    "Strike rate",
    f"{100 * totals.runs / max(totals.balls, 1):.1f}",
    border=True,
    help="Runs off the bat per 100 balls faced.",
)
tiles[2].metric("Sixes", f"{int(totals.sixes):,}", border=True)
if not top_bat.empty:
    tiles[3].metric(
        "Most runs",
        f"{int(top_bat.runs[0]):,}",
        top_bat.batter[0],
        delta_color="off",
        delta_arrow="off",
        border=True,
    )
if not top_bowl.empty:
    tiles[4].metric(
        "Most wickets",
        f"{int(top_bowl.wickets[0])}",
        top_bowl.bowler[0],
        delta_color="off",
        delta_arrow="off",
        border=True,
    )

teams_tab, batting_tab, bowling_tab, matchups_tab = st.tabs(
    ["Teams", "Batting", "Bowling", "Matchups"]
)

# --- Teams ----------------------------------------------------------------------------------

with teams_tab:
    results = query(
        f"""select team, sum(matches) as matches, sum(wins) as wins, sum(losses) as losses,
                   sum(no_results) as no_results, sum(super_over_wins) as super_over_wins
            from mart_team_season_results where {flt} group by team""",
        params,
    )
    results["win_pct"] = safe_ratio(results.wins, results.wins + results.losses, 100)
    long = results.melt(["team", "win_pct"], ["wins", "losses"], "outcome", "count")
    long["outcome"] = long.outcome.map({"wins": "Won", "losses": "Lost"})

    left, right = st.columns([1.2, 1])
    with left, card("Wins and losses", "Super-over wins count as wins; no-results are left out."):
        chart = (
            alt.Chart(long)
            .mark_bar(cornerRadiusEnd=4, stroke="transparent", strokeWidth=2)
            .encode(
                y=alt.Y(
                    "team:N",
                    sort=alt.EncodingSortField("win_pct", order="descending"),
                    title=None,
                    axis=alt.Axis(**QUIET_X, labelLimit=200),
                ),
                x=alt.X("count:Q", title="Matches", stack="zero", axis=alt.Axis(**QUIET_Y)),
                color=alt.Color(
                    "outcome:N", scale=OUTCOME_COLOURS, title=None, legend=alt.Legend(orient="top")
                ),
                order=alt.Order("outcome:N", sort="descending"),
                tooltip=["team", "outcome", "count", alt.Tooltip("win_pct", title="Win %")],
            )
            .properties(height=alt.Step(26), padding=PAD)
        )
        st.altair_chart(chart, width="stretch")
    with right, card("Win record"):
        st.dataframe(
            results.sort_values("win_pct", ascending=False),
            hide_index=True,
            width="stretch",
            column_config={
                "team": "Team",
                "matches": "M",
                "wins": "W",
                "losses": "L",
                "no_results": "NR",
                "super_over_wins": "Super-over W",
                "win_pct": st.column_config.ProgressColumn(
                    "Win %", format="%.1f", min_value=0, max_value=100
                ),
            },
        )

    games = query(
        f"""select match_id, match_date, team, opponent, outcome, runs, wickets_lost,
                   overs_text, strike_rate, run_rate
            from (select *, cast(legal_balls // 6 as varchar) || '.'
                         || cast(legal_balls % 6 as varchar) as overs_text
                  from mart_team_match_batting) where {flt} and outcome <> 'No result'
            order by match_date""",
        params,
    )
    with card(
        "Strike rate per game",
        "Each dot is one innings: runs off the bat per 100 balls faced. "
        + ("Pick a team to follow one side." if team is None else f"{team}, game by game."),
    ):
        base = alt.Chart(games).encode(
            tooltip=[
                alt.Tooltip("match_date:T", title="Date"),
                "team",
                "opponent",
                "outcome",
                alt.Tooltip("runs", title="Runs"),
                alt.Tooltip("wickets_lost", title="Wkts"),
                alt.Tooltip("overs_text", title="Overs"),
                alt.Tooltip("strike_rate", format=".1f", title="Strike rate"),
            ]
        )
        if team is None:
            dots = (
                base.mark_circle(size=64, opacity=0.75, stroke="white", strokeWidth=1)
                .encode(
                    y=alt.Y("team:N", title=None, axis=alt.Axis(**QUIET_X, labelLimit=200)),
                    x=alt.X(
                        "strike_rate:Q",
                        title="Strike rate",
                        scale=alt.Scale(zero=False),
                        axis=alt.Axis(**QUIET_Y),
                    ),
                    color=alt.Color(
                        "outcome:N",
                        scale=OUTCOME_COLOURS,
                        title=None,
                        legend=alt.Legend(orient="top"),
                    ),
                    yOffset=alt.YOffset("jitter:Q"),
                )
                .transform_calculate(jitter="random()")
            )
            chart = dots.properties(height=alt.Step(30), padding=PAD)
        else:
            chart = (
                base.mark_bar(cornerRadiusEnd=4)
                .encode(
                    x=alt.X("match_date:T", title=None, axis=alt.Axis(**QUIET_X)),
                    y=alt.Y("strike_rate:Q", title="Strike rate", axis=alt.Axis(**QUIET_Y)),
                    color=alt.Color(
                        "outcome:N",
                        scale=OUTCOME_COLOURS,
                        title=None,
                        legend=alt.Legend(orient="top"),
                    ),
                )
                .properties(height=260, padding=PAD)
            )
        st.altair_chart(chart, width="stretch")

    phases = query(
        f"""select team, phase, sum(runs_off_bat) as runs, sum(balls_faced) as balls,
                   sum(wickets_lost) as wickets
            from mart_phase_strike_rates where {flt} group by team, phase""",
        params,
    )
    phases["strike_rate"] = safe_ratio(phases.runs, phases.balls, 100)
    with card("Strike rate by phase", "Powerplay overs 1-6, middle 7-15, death 16-20."):
        order = ["Powerplay", "Middle", "Death"]
        if team is None:
            by_phase = phases.groupby("phase", as_index=False)[["runs", "balls", "wickets"]].sum()
            by_phase["strike_rate"] = safe_ratio(by_phase.runs, by_phase.balls, 100)
            chart = (
                alt.Chart(by_phase)
                .mark_bar(cornerRadiusEnd=4, size=48)
                .encode(
                    x=alt.X(
                        "phase:N", sort=order, title=None, axis=alt.Axis(**QUIET_X, labelAngle=0)
                    ),
                    y=alt.Y("strike_rate:Q", title="Strike rate", axis=alt.Axis(**QUIET_Y)),
                    tooltip=[
                        "phase",
                        "runs",
                        "balls",
                        "wickets",
                        alt.Tooltip("strike_rate", format=".1f"),
                    ],
                )
            )
        else:
            chart = (
                alt.Chart(phases)
                .mark_bar(cornerRadiusEnd=4, size=48)
                .encode(
                    x=alt.X(
                        "phase:N", sort=order, title=None, axis=alt.Axis(**QUIET_X, labelAngle=0)
                    ),
                    y=alt.Y("strike_rate:Q", title="Strike rate", axis=alt.Axis(**QUIET_Y)),
                    tooltip=[
                        "phase",
                        "runs",
                        "balls",
                        "wickets",
                        alt.Tooltip("strike_rate", format=".1f"),
                    ],
                )
            )
        st.altair_chart(chart.properties(height=240, padding=PAD), width="stretch")

# --- Batting --------------------------------------------------------------------------------

with batting_tab:
    batters = query(
        f"""select batter_id, batter, string_agg(distinct team, ', ') as teams,
                   sum(innings) as innings, sum(not_outs) as not_outs, sum(runs) as runs,
                   sum(balls_faced) as balls, sum(dismissals) as outs,
                   max(highest_score) as highest, sum(fifties) as fifties,
                   sum(hundreds) as hundreds, sum(fours) as fours, sum(sixes) as sixes
            from mart_batter_season where {flt} group by batter_id, batter""",
        params,
    )
    batters["average"] = safe_ratio(batters.runs, batters.outs)
    batters["strike_rate"] = safe_ratio(batters.runs, batters.balls, 100)
    qualified = batters[batters.balls >= MIN_BALLS_FACED]

    with card("Batting leaderboard"):
        st.dataframe(
            batters.sort_values("runs", ascending=False).drop(columns=["batter_id", "outs"]),
            hide_index=True,
            width="stretch",
            height=420,
            column_config={
                "batter": "Batter",
                "teams": "Team",
                "innings": "Inns",
                "not_outs": "NO",
                "runs": "Runs",
                "balls": "Balls",
                "highest": "HS",
                "fifties": "50s",
                "hundreds": "100s",
                "fours": "4s",
                "sixes": "6s",
                "average": st.column_config.NumberColumn("Avg", format="%.2f"),
                "strike_rate": st.column_config.NumberColumn("SR", format="%.2f"),
            },
        )

    left, right = st.columns(2)
    with left, card("Runs against strike rate", f"Batters with {MIN_BALLS_FACED}+ balls faced."):
        chart = (
            alt.Chart(qualified)
            .mark_circle(size=70, opacity=0.7, stroke="white", strokeWidth=1)
            .encode(
                x=alt.X(
                    "strike_rate:Q",
                    title="Strike rate",
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(**QUIET_Y),
                ),
                y=alt.Y("runs:Q", title="Runs", axis=alt.Axis(**QUIET_Y)),
                tooltip=[
                    "batter",
                    "teams",
                    "runs",
                    "balls",
                    alt.Tooltip("strike_rate", format=".1f"),
                    alt.Tooltip("average", format=".1f"),
                ],
            )
            .properties(height=320, padding=PAD)
        )
        st.altair_chart(chart, width="stretch")

    with right, card("One batter, game by game"):
        names = batters.sort_values("runs", ascending=False)
        if names.empty:
            st.info("No batting for this filter.")
        else:
            chosen = st.selectbox(
                "Batter",
                names.batter_id,
                format_func=dict(zip(names.batter_id, names.batter, strict=True)).get,
                key="batter",
            )
            inns_sql, inns_params = where(season, team)
            innings = query(
                f"""select match_date, opponent, outcome, runs, balls_faced, strike_rate,
                           dismissal
                    from mart_batter_innings where {inns_sql} and batter_id = ?
                    order by match_date""",
                (*inns_params, chosen),
            )
            chart = (
                alt.Chart(innings)
                .mark_bar(cornerRadiusEnd=4)
                .encode(
                    x=alt.X("match_date:T", title=None, axis=alt.Axis(**QUIET_X)),
                    y=alt.Y("runs:Q", title="Runs", axis=alt.Axis(**QUIET_Y)),
                    tooltip=[
                        alt.Tooltip("match_date:T", title="Date"),
                        "opponent",
                        "outcome",
                        "runs",
                        alt.Tooltip("balls_faced", title="Balls"),
                        alt.Tooltip("strike_rate", format=".1f", title="SR"),
                        "dismissal",
                    ],
                )
                .properties(height=250, padding=PAD)
            )
            st.altair_chart(chart, width="stretch")

# --- Bowling --------------------------------------------------------------------------------

with bowling_tab:
    bowlers = query(
        f"""select bowler_id, bowler, string_agg(distinct team, ', ') as teams,
                   sum(innings) as innings, sum(legal_balls) as balls,
                   sum(runs_conceded) as runs, sum(wickets) as wickets, sum(dots) as dots,
                   sum(four_wicket_hauls) as four_fors
            from mart_bowler_season where {flt} group by bowler_id, bowler""",
        params,
    )
    best = query(
        f"""select bowler_id, best_wickets, best_runs from (
                select bowler_id, best_wickets, best_runs, row_number() over (
                    partition by bowler_id order by best_wickets desc, best_runs) as rk
                from mart_bowler_season where {flt}) where rk = 1""",
        params,
    )
    bowlers = bowlers.merge(best, on="bowler_id")
    bowlers["overs"] = overs(bowlers.balls)
    bowlers["best"] = (
        bowlers.best_wickets.astype(int).astype(str)
        + "/"
        + bowlers.best_runs.astype(int).astype(str)
    )
    bowlers["economy"] = safe_ratio(bowlers.runs, bowlers.balls, 6)
    bowlers["average"] = safe_ratio(bowlers.runs, bowlers.wickets)
    bowlers["strike_rate"] = safe_ratio(bowlers.balls, bowlers.wickets)
    bowlers["dot_pct"] = safe_ratio(bowlers.dots, bowlers.balls, 100)

    with card("Bowling leaderboard", "Strike rate here is balls per wicket."):
        st.dataframe(
            bowlers.sort_values(["wickets", "runs"], ascending=[False, True])[
                [
                    "bowler",
                    "teams",
                    "innings",
                    "overs",
                    "runs",
                    "wickets",
                    "best",
                    "economy",
                    "average",
                    "strike_rate",
                    "dot_pct",
                    "four_fors",
                ]
            ],
            hide_index=True,
            width="stretch",
            height=420,
            column_config={
                "bowler": "Bowler",
                "teams": "Team",
                "innings": "Inns",
                "overs": "Overs",
                "runs": "Runs",
                "wickets": "Wkts",
                "best": "Best",
                "four_fors": "4w",
                "economy": st.column_config.NumberColumn("Econ", format="%.2f"),
                "average": st.column_config.NumberColumn("Avg", format="%.2f"),
                "strike_rate": st.column_config.NumberColumn("SR", format="%.1f"),
                "dot_pct": st.column_config.NumberColumn("Dot %", format="%.1f"),
            },
        )
    with card(
        "Economy against strike rate",
        f"Bowlers with {MIN_BALLS_BOWLED}+ legal balls. Bottom-left is best.",
    ):
        chart = (
            alt.Chart(bowlers[(bowlers.balls >= MIN_BALLS_BOWLED) & (bowlers.wickets > 0)])
            .mark_circle(size=70, opacity=0.7, stroke="white", strokeWidth=1)
            .encode(
                x=alt.X(
                    "economy:Q",
                    title="Economy",
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(**QUIET_Y),
                ),
                y=alt.Y(
                    "strike_rate:Q",
                    title="Balls per wicket",
                    scale=alt.Scale(zero=False),
                    axis=alt.Axis(**QUIET_Y),
                ),
                size=alt.Size("wickets:Q", title="Wickets", legend=alt.Legend(orient="top")),
                tooltip=[
                    "bowler",
                    "teams",
                    "wickets",
                    "overs",
                    alt.Tooltip("economy", format=".2f"),
                    alt.Tooltip("strike_rate", format=".1f", title="Balls/wkt"),
                    "best",
                ],
            )
            .properties(height=340, padding=PAD)
        )
        st.altair_chart(chart, width="stretch")

# --- Matchups -------------------------------------------------------------------------------

with matchups_tab:
    st.caption(
        f"Batter against bowler across every season (filters don't apply). "
        f"Pairs with {MIN_MATCHUP_BALLS}+ balls. Dismissals count only the bowler's wickets."
    )
    stars = query(
        """select batter_id, batter, sum(runs) as runs from mart_matchups
           group by batter_id, batter order by runs desc"""
    )
    side, pick = st.columns([1, 3])
    with side:
        mode = st.radio("Look up", ["Batter", "Bowler"], horizontal=True)
    with pick:
        if mode == "Batter":
            pid = st.selectbox(
                "Batter",
                stars.batter_id,
                format_func=dict(zip(stars.batter_id, stars.batter, strict=True)).get,
                key="mu_batter",
            )
            col, other = "batter_id", "bowler"
        else:
            spinners = query(
                """select bowler_id, bowler, sum(dismissals) as w from mart_matchups
                   group by bowler_id, bowler order by w desc"""
            )
            pid = st.selectbox(
                "Bowler",
                spinners.bowler_id,
                format_func=dict(zip(spinners.bowler_id, spinners.bowler, strict=True)).get,
                key="mu_bowler",
            )
            col, other = "bowler_id", "batter"
    pairs = query(
        f"""select {other} as opponent, matches, balls_faced, runs, dismissals, dots, fours,
                   sixes, strike_rate, average
            from mart_matchups where {col} = ? and balls_faced >= ?
            order by balls_faced desc""",
        (pid, MIN_MATCHUP_BALLS),
    )
    with card(f"Head to head ({len(pairs)} opponents)"):
        st.dataframe(
            pairs,
            hide_index=True,
            width="stretch",
            column_config={
                "opponent": "Bowler" if mode == "Batter" else "Batter",
                "matches": "Matches",
                "balls_faced": "Balls",
                "runs": "Runs",
                "dismissals": "Outs",
                "dots": "Dots",
                "fours": "4s",
                "sixes": "6s",
                "strike_rate": st.column_config.NumberColumn("SR", format="%.1f"),
                "average": st.column_config.NumberColumn("Avg", format="%.1f"),
            },
        )
