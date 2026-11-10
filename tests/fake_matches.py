"""Two invented matches in Cricsheet's JSON format, small enough to score by hand.

Match 1 (tie, Chennai win the super over), Mumbai's one over:
  1. A hits 4          5. A dot ball
  2. wide (1)          6. A bowled
  3. A hits 6          7. C runs 4 (all run, not a boundary)
  4. no-ball, A 1      8. C leg bye (1)
  A: 11 off 5 (the no-ball counts as faced, the wide doesn't), out bowled.
  C: 4 off 2, not out. D never faces: 0 off 0, not out.
  Team: 18 runs; 15 off the bat from 7 balls faced. Bowler X: 6 legal balls, 17 conceded
  (15 + wide + no-ball; the leg bye isn't his), 1 wicket.
Chennai's over: E hits three sixes then three dots: 18, a tie. One ball each in the super over.

Match 2: Delhi Daredevils v Kings XI Punjab (old names), no result.
"""

from __future__ import annotations

import io
import json
import zipfile

PEOPLE = {n: f"id_{n.lower()}" for n in ["A", "C", "D", "E", "F", "X", "Y", "P", "Q", "R"]}


def ball(batter, bowler, non_striker, bat=0, extras=None, wicket=None, non_boundary=False):
    extras = extras or {}
    runs = {"batter": bat, "extras": sum(extras.values()), "total": bat + sum(extras.values())}
    if non_boundary:
        runs["non_boundary"] = True
    out = {"batter": batter, "bowler": bowler, "non_striker": non_striker, "runs": runs}
    if extras:
        out["extras"] = extras
    if wicket:
        out["wickets"] = [{"player_out": batter, "kind": wicket}]
    return out


def match(teams, outcome, innings, players, date="2024-04-01"):
    return {
        "meta": {"data_version": "1.3.0"},
        "info": {
            "dates": [date],
            "season": "2023/24",
            "event": {"name": "Indian Premier League", "match_number": 1},
            "city": "Testville",
            "venue": "Test Ground",
            "teams": teams,
            "toss": {"winner": teams[0], "decision": "bat"},
            "outcome": outcome,
            "overs": 20,
            "players": players,
            "registry": {"people": PEOPLE},
        },
        "innings": innings,
    }


MI, CSK = "Mumbai Indians", "Chennai Super Kings"

TIE = match(
    [MI, CSK],
    {"result": "tie", "eliminator": CSK},
    [
        {
            "team": MI,
            "overs": [
                {
                    "over": 0,
                    "deliveries": [
                        ball("A", "X", "D", 4),
                        ball("A", "X", "D", 0, {"wides": 1}),
                        ball("A", "X", "D", 6),
                        ball("A", "X", "D", 1, {"noballs": 1}),
                        ball("A", "X", "D", 0),
                        ball("A", "X", "D", 0, wicket="bowled"),
                        ball("C", "X", "D", 4, non_boundary=True),
                        ball("C", "X", "D", 0, {"legbyes": 1}),
                    ],
                }
            ],
        },
        {
            "team": CSK,
            "target": {"runs": 19, "overs": 20},
            "overs": [
                {
                    "over": 0,
                    "deliveries": [ball("E", "Y", "F", r) for r in (6, 6, 6, 0, 0, 0)],
                }
            ],
        },
        {
            "team": MI,
            "super_over": True,
            "overs": [{"over": 0, "deliveries": [ball("C", "Y", "D", 6)]}],
        },
        {
            "team": CSK,
            "super_over": True,
            "overs": [{"over": 0, "deliveries": [ball("E", "X", "F", 6)]}],
        },
    ],
    {MI: ["A", "C", "D", "X"], CSK: ["E", "F", "Y"]},
)

WASHOUT = match(
    ["Delhi Daredevils", "Kings XI Punjab"],
    {"result": "no result"},
    [
        {
            "team": "Delhi Daredevils",
            "overs": [{"over": 0, "deliveries": [ball("P", "R", "Q", 1)]}],
        }
    ],
    {"Delhi Daredevils": ["P", "Q"], "Kings XI Punjab": ["R"]},
    date="2024-04-02",
)


def archive(matches: dict[str, dict]) -> bytes:
    """A zip laid out like Cricsheet's, README included."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("README.txt", "not a match")
        for match_id, body in matches.items():
            zf.writestr(f"{match_id}.json", json.dumps(body))
    return buf.getvalue()
