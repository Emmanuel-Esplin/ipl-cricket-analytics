"""Bronze match JSON to typed silver Parquet, one file per table and season.

Flattening happens here rather than in dbt so the same SQL runs on DuckDB and Athena:
Athena reads nested JSON poorly, and both engines read flat Parquet the same way.

Players are keyed by Cricsheet's registry id, not by name: names are only unique within a
match, and the registry is what links one player across seasons.
"""

from __future__ import annotations

import argparse
import logging
from collections.abc import Callable, Iterator
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq

from ingestion import landing
from ingestion.cricsheet import ENDPOINT, SOURCE

Row = dict[str, Any]
Match = dict[str, Any]

log = logging.getLogger(__name__)

INT, STRING, BOOL = pa.int64(), pa.string(), pa.bool_()

SCHEMAS: dict[str, pa.Schema] = {
    "matches": pa.schema(
        [
            ("season", INT),
            ("match_id", STRING),
            ("season_label", STRING),
            ("match_date", STRING),
            ("match_number", INT),
            ("stage", STRING),
            ("city", STRING),
            ("venue", STRING),
            ("team1", STRING),
            ("team2", STRING),
            ("toss_winner", STRING),
            ("toss_decision", STRING),
            ("winner", STRING),
            ("result", STRING),
            ("win_by_runs", INT),
            ("win_by_wickets", INT),
            ("method", STRING),
            ("super_over_winner", STRING),
            ("player_of_match", STRING),
            ("scheduled_overs", INT),
        ]
    ),
    "innings": pa.schema(
        [
            ("season", INT),
            ("match_id", STRING),
            ("innings_no", INT),
            ("batting_team", STRING),
            ("bowling_team", STRING),
            ("is_super_over", BOOL),
            ("target_runs", INT),
            ("target_overs", INT),
        ]
    ),
    "deliveries": pa.schema(
        [
            ("season", INT),
            ("match_id", STRING),
            ("innings_no", INT),
            ("batting_team", STRING),
            ("bowling_team", STRING),
            ("is_super_over", BOOL),
            ("over_no", INT),
            ("ball_seq", INT),
            ("batter_id", STRING),
            ("batter", STRING),
            ("non_striker_id", STRING),
            ("bowler_id", STRING),
            ("bowler", STRING),
            ("runs_batter", INT),
            ("runs_extras", INT),
            ("runs_total", INT),
            ("non_boundary", BOOL),
            ("wides", INT),
            ("noballs", INT),
            ("byes", INT),
            ("legbyes", INT),
            ("penalty", INT),
            ("wickets", INT),
        ]
    ),
    "wickets": pa.schema(
        [
            ("season", INT),
            ("match_id", STRING),
            ("innings_no", INT),
            ("over_no", INT),
            ("ball_seq", INT),
            ("player_out_id", STRING),
            ("player_out", STRING),
            ("kind", STRING),
            ("bowler_id", STRING),
            ("fielders", STRING),
        ]
    ),
    "players": pa.schema(
        [
            ("season", INT),
            ("match_id", STRING),
            ("team", STRING),
            ("player_id", STRING),
            ("player_name", STRING),
        ]
    ),
}


def _match_id(match: Match) -> str:
    return match["_match_id"]


def _registry(match: Match) -> dict[str, str]:
    return match["info"].get("registry", {}).get("people", {})


def match_rows(match: Match) -> Iterator[Row]:
    """One row per match, with the result spelled out."""
    info, outcome = match["info"], match["info"]["outcome"]
    by = outcome.get("by", {})
    pom = info.get("player_of_match") or [None]
    result = outcome.get("result", "normal")
    # A tie settled by a super over names the side that won it as the 'eliminator'.
    super_over_winner = outcome.get("eliminator")
    yield {
        "match_id": _match_id(match),
        "season_label": str(info["season"]),
        "match_date": info["dates"][0],
        "match_number": info.get("event", {}).get("match_number"),
        "stage": info.get("event", {}).get("stage"),
        "city": info.get("city"),
        "venue": info.get("venue"),
        "team1": info["teams"][0],
        "team2": info["teams"][1],
        "toss_winner": info["toss"]["winner"],
        "toss_decision": info["toss"]["decision"],
        "winner": outcome.get("winner") or super_over_winner,
        "result": result,
        "win_by_runs": by.get("runs"),
        "win_by_wickets": by.get("wickets"),
        "method": outcome.get("method"),
        "super_over_winner": super_over_winner,
        "player_of_match": pom[0],
        "scheduled_overs": info.get("overs"),
    }


def _innings(match: Match) -> Iterator[tuple[int, Row, Row]]:
    """(innings_no, raw innings, shared columns) for every innings, super overs included."""
    teams = match["info"]["teams"]
    for number, innings in enumerate(match["innings"], start=1):
        batting = innings["team"]
        yield (
            number,
            innings,
            {
                "match_id": _match_id(match),
                "innings_no": number,
                "batting_team": batting,
                "bowling_team": teams[1] if batting == teams[0] else teams[0],
                "is_super_over": bool(innings.get("super_over")),
            },
        )


def innings_rows(match: Match) -> Iterator[Row]:
    """One row per innings, with the chase target where there is one."""
    for _, innings, base in _innings(match):
        target = innings.get("target", {})
        yield {**base, "target_runs": target.get("runs"), "target_overs": target.get("overs")}


def _balls(match: Match) -> Iterator[tuple[Row, int, int, Row]]:
    """(innings columns, over_no, ball_seq, raw delivery). ball_seq counts every delivery in
    the over from 1, extras included, so it orders balls that Cricsheet labels alike."""
    for _, innings, base in _innings(match):
        for over in innings["overs"]:
            for seq, ball in enumerate(over["deliveries"], start=1):
                yield base, over["over"], seq, ball


def delivery_rows(match: Match) -> Iterator[Row]:
    """One row per delivery bowled."""
    people = _registry(match)
    for base, over_no, seq, ball in _balls(match):
        runs, extras = ball["runs"], ball.get("extras", {})
        yield {
            **base,
            "over_no": over_no,
            "ball_seq": seq,
            "batter_id": people.get(ball["batter"]),
            "batter": ball["batter"],
            "non_striker_id": people.get(ball["non_striker"]),
            "bowler_id": people.get(ball["bowler"]),
            "bowler": ball["bowler"],
            "runs_batter": runs["batter"],
            "runs_extras": runs["extras"],
            "runs_total": runs["total"],
            # A four or six that was run, not hit to the rope (rare, but it isn't a boundary).
            "non_boundary": bool(runs.get("non_boundary")),
            "wides": extras.get("wides", 0),
            "noballs": extras.get("noballs", 0),
            "byes": extras.get("byes", 0),
            "legbyes": extras.get("legbyes", 0),
            "penalty": extras.get("penalty", 0),
            "wickets": len(ball.get("wickets", [])),
        }


def wicket_rows(match: Match) -> Iterator[Row]:
    """One row per dismissal. Run outs can dismiss the non-striker, so player_out is explicit."""
    people = _registry(match)
    for base, over_no, seq, ball in _balls(match):
        for wicket in ball.get("wickets", []):
            fielders = [f.get("name") for f in wicket.get("fielders", []) if f.get("name")]
            yield {
                "match_id": base["match_id"],
                "innings_no": base["innings_no"],
                "over_no": over_no,
                "ball_seq": seq,
                "player_out_id": people.get(wicket["player_out"]),
                "player_out": wicket["player_out"],
                "kind": wicket["kind"],
                "bowler_id": people.get(ball["bowler"]),
                "fielders": ", ".join(fielders) or None,
            }


def player_rows(match: Match) -> Iterator[Row]:
    """One row per player named in each team's XI (plus substitutes Cricsheet lists)."""
    people = _registry(match)
    for team, names in match["info"].get("players", {}).items():
        for name in names:
            yield {
                "match_id": _match_id(match),
                "team": team,
                "player_id": people.get(name),
                "player_name": name,
            }


TABLES: dict[str, Callable[[Match], Iterator[Row]]] = {
    "matches": match_rows,
    "innings": innings_rows,
    "deliveries": delivery_rows,
    "wickets": wicket_rows,
    "players": player_rows,
}


def _bronze_matches(store: landing.Storage) -> Iterator[tuple[int, Match]]:
    # Files sit at bronze/cricsheet/matches/season=YYYY/match_id=NNN.json.
    for path in store.list_files(store.path("bronze", SOURCE, ENDPOINT), ".json"):
        parts = dict(p.removesuffix(".json").split("=", 1) for p in path.split("/") if "=" in p)
        match = landing.read_bronze(path)
        match["_match_id"] = parts["match_id"]
        yield int(parts["season"]), match


def build_all(store: landing.Storage) -> dict[str, int]:
    """Rebuild every silver table from all of bronze in one pass. Returns row counts."""
    rows: dict[str, dict[int, list[Row]]] = {table: {} for table in TABLES}
    for season, match in _bronze_matches(store):
        for table, build in TABLES.items():
            bucket = rows[table].setdefault(season, [])
            bucket.extend({"season": season, **row} for row in build(match))

    counts = {}
    for table, by_season in rows.items():
        # Rebuilt from scratch, so a season removed from bronze can't linger in silver.
        store.delete_dir(store.path("silver", table))
        for season, season_rows in sorted(by_season.items()):
            target = store.path("silver", table, f"season={season}", "part-0.parquet")
            store.make_parent(target)
            data = pa.Table.from_pylist(season_rows, schema=SCHEMAS[table])
            pq.write_table(data, target, filesystem=store.fs)
        counts[table] = sum(len(r) for r in by_season.values())
        log.info("silver %s: %d rows", table, counts[table])
    return counts


def main() -> None:
    argparse.ArgumentParser(description="Rebuild silver from bronze.").parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    print(build_all(landing.store()))


if __name__ == "__main__":
    main()
