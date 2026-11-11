import pyarrow.parquet as pq

from ingestion import cricsheet, landing
from processing import silver
from tests.fake_matches import TIE, WASHOUT, archive


def rows(builder, match, match_id="1"):
    return list(builder({**match, "_match_id": match_id}))


def test_tie_names_the_super_over_winner():
    (row,) = rows(silver.match_rows, TIE)
    assert row["result"] == "tie"
    assert row["winner"] == row["super_over_winner"] == "Chennai Super Kings"


def test_no_result_has_no_winner():
    (row,) = rows(silver.match_rows, WASHOUT)
    assert (row["result"], row["winner"]) == ("no result", None)


def test_deliveries_split_extras_and_flag_run_fours():
    balls = rows(silver.delivery_rows, TIE)[:8]
    assert [b["ball_seq"] for b in balls] == list(range(1, 9))
    assert balls[1]["wides"] == 1 and balls[3]["noballs"] == 1 and balls[7]["legbyes"] == 1
    assert balls[6]["runs_batter"] == 4 and balls[6]["non_boundary"]
    assert balls[0]["batter_id"] == "id_a"


def test_super_overs_are_flagged():
    flags = [i["is_super_over"] for i in rows(silver.innings_rows, TIE)]
    assert flags == [False, False, True, True]


def test_bowling_side_is_the_other_team():
    first = rows(silver.innings_rows, TIE)[0]
    assert (first["batting_team"], first["bowling_team"]) == (
        "Mumbai Indians",
        "Chennai Super Kings",
    )


def test_build_all_writes_one_file_per_table_and_season(bronze_dir):
    cricsheet.ingest(archive({"1": TIE, "2": WASHOUT}))
    counts = silver.build_all(landing.store())

    assert counts["matches"] == 2
    assert counts["wickets"] == 1
    table = pq.read_table(bronze_dir / "silver/deliveries/season=2024/part-0.parquet")
    assert table.schema.equals(silver.SCHEMAS["deliveries"])


def test_terraform_schemas_match_silver():
    from processing import schemas_export

    assert schemas_export.TARGET.read_text() == schemas_export.render(), "run `make schemas`"
