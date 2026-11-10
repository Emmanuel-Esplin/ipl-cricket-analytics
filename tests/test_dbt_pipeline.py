"""End to end on invented matches: bronze -> silver -> every dbt model and test on DuckDB.

Expected figures are worked out by hand in tests/fake_matches.py.
"""

import os
import subprocess
import sys
from pathlib import Path

import duckdb
import pytest

from ingestion import cricsheet, landing
from processing import silver
from tests.fake_matches import TIE, WASHOUT, archive

DBT = Path(sys.executable).parent / "dbt"
PROJECT = Path(__file__).resolve().parents[1] / "transform"


@pytest.fixture
def warehouse(bronze_dir):
    cricsheet.ingest(archive({"1": TIE, "2": WASHOUT}))
    silver.build_all(landing.store())
    (bronze_dir / "gold").mkdir()
    env = {
        **os.environ,
        "IPL_DATA_DIR": str(bronze_dir),
        "DBT_SEND_ANONYMOUS_USAGE_STATS": "false",
        "DBT_TARGET_PATH": str(bronze_dir / "target"),
        "DBT_LOG_PATH": str(bronze_dir / "logs"),
    }
    run = subprocess.run(
        [str(DBT), "build", "--profiles-dir", ".", "--exclude", "tag:reconcile"],
        cwd=PROJECT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert run.returncode == 0, run.stdout[-3000:]
    con = duckdb.connect(str(bronze_dir / "gold" / "warehouse.duckdb"), read_only=True)
    yield con
    con.close()


def one(con, sql):
    return con.sql(sql).fetchone()


def test_wins_losses_and_renamed_franchises(warehouse):
    results = dict(
        warehouse.sql(
            "select team, (wins, losses, no_results, super_over_wins) from mart_team_season_results"
        ).fetchall()
    )
    assert results == {
        "Chennai Super Kings": (1, 0, 0, 1),
        "Mumbai Indians": (0, 1, 0, 0),
        # Delhi Daredevils and Kings XI Punjab roll up to today's names.
        "Delhi Capitals": (0, 0, 1, 0),
        "Punjab Kings": (0, 0, 1, 0),
    }


def test_team_strike_rate_per_game(warehouse):
    row = one(
        warehouse,
        "select runs, runs_off_bat, balls_faced, legal_balls, wickets_lost, fours, "
        "round(strike_rate, 2), outcome from mart_team_match_batting "
        "where team = 'Mumbai Indians'",
    )
    assert row == (18, 15, 7, 6, 1, 1, 214.29, "Lost")


def test_batter_innings(warehouse):
    rows = warehouse.sql(
        "select batter, runs, balls_faced, fours, sixes, dismissal, strike_rate "
        "from mart_batter_innings where team = 'Mumbai Indians' order by batter"
    ).fetchall()
    assert rows == [
        ("A", 11, 5, 1, 1, "bowled", 220.0),
        ("C", 4, 2, 0, 0, "not out", 200.0),  # the all-run four is not a boundary
        ("D", 0, 0, 0, 0, "not out", None),  # non-striker who never faced
    ]


def test_bowler_figures_leave_out_byes_and_super_overs(warehouse):
    row = one(
        warehouse,
        "select legal_balls, runs_conceded, wickets, economy, best_wickets, best_runs "
        "from mart_bowler_season where bowler = 'X'",
    )
    assert row == (6, 17, 1, 17.0, 1, 17)


def test_phase_and_matchups(warehouse):
    phases = warehouse.sql("select distinct phase from mart_phase_strike_rates").fetchall()
    assert phases == [("Powerplay",)]
    row = one(
        warehouse,
        "select balls_faced, runs, dismissals from mart_matchups "
        "where batter = 'A' and bowler = 'X'",
    )
    assert row == (5, 11, 1)
