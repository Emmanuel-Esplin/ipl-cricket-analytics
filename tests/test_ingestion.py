import copy

import httpx
import pytest

from ingestion import cricsheet, landing
from tests.fake_matches import TIE, WASHOUT, archive


def test_writes_each_match_under_its_season(bronze_dir):
    result = cricsheet.ingest(archive({"1": TIE, "2": WASHOUT}))

    assert result == {"written": 2, "unchanged": 0}
    path = bronze_dir / "bronze/cricsheet/matches/season=2024/match_id=1.json"
    assert landing.read_bronze(str(path))["info"]["teams"][0] == "Mumbai Indians"


def test_rerun_writes_only_new_or_revised_matches():
    cricsheet.ingest(archive({"1": TIE}))
    revised = copy.deepcopy(TIE)
    revised["info"]["venue"] = "Renamed Ground"

    assert cricsheet.ingest(archive({"1": TIE, "2": WASHOUT})) == {"written": 1, "unchanged": 1}
    assert cricsheet.ingest(archive({"1": revised})) == {"written": 1, "unchanged": 0}


def test_refresh_rewrites_everything():
    cricsheet.ingest(archive({"1": TIE}))
    assert cricsheet.ingest(archive({"1": TIE}), refresh=True)["written"] == 1


@pytest.mark.parametrize(("label", "date", "season"), [("2007/08", "2008-04-18", 2008)])
def test_season_comes_from_the_match_date(label, date, season):
    assert cricsheet.season_of({"info": {"season": label, "dates": [date]}}) == season


def test_download_uses_the_archive_url():
    seen = []

    def handler(request):
        seen.append(str(request.url))
        return httpx.Response(200, content=b"zip")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert cricsheet.download_archive(client) == b"zip"
    assert seen == [cricsheet.ARCHIVE_URL]
