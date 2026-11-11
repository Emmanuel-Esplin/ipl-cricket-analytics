# Metric definitions

Every rule lives once, in `transform/models/staging/stg_deliveries.sql` and `stg_wickets.sql`,
so all marts agree.

| Term | Definition |
| --- | --- |
| Ball faced | Any delivery except a wide. A no-ball counts as faced. |
| Legal ball | Neither a wide nor a no-ball; six make an over. |
| Strike rate (batting) | Runs off the bat per 100 balls faced. Team strike rate uses the same rule. |
| Run rate | All runs, extras included, per six legal balls. |
| Bowler's runs | Runs off the bat + wides + no-balls. Byes, leg byes and penalty runs aren't the bowler's. |
| Economy | Bowler's runs per six legal balls. |
| Bowling average / strike rate | Bowler's runs per wicket / legal balls per wicket. |
| Bowler's wicket | Any dismissal except run out, retired hurt, retired out, obstructing the field. |
| Dismissal | Any wicket except retired hurt (the batter can return). |
| Boundary | A 4 or 6 off the bat, unless Cricsheet flags it `non_boundary` (all run). |
| Phase | Powerplay overs 1-6, middle 7-15, death 16-20. |
| Win / loss | From the result. A tie decided by a super over is a win for the super-over winner (`super_over_wins` counts them). No-results are neither and are left out of win %. |
| Season | Calendar year of the match. Cricsheet labels some seasons "2007/08", "2009/10", "2020/21". |
| Franchise | Renamed sides roll up to today's name (`transform/seeds/franchises.csv`): Delhi Daredevils -> Delhi Capitals, Kings XI Punjab -> Punjab Kings, Royal Challengers Bangalore -> Bengaluru, Rising Pune Supergiants -> Supergiant. Deccan Chargers and Sunrisers Hyderabad are different franchises. |

Super-over balls are left out of all batting, bowling, phase and matchup stats, as in
official records.

## Caveats

- Matches abandoned without a ball bowled aren't in Cricsheet, so they don't appear as
  no-results (KKR had two such washouts in 2024).
- A batter who only stood at the non-striker's end still counts as an innings (0 off 0, not out).
- Players are keyed by Cricsheet's registry id, not by name.

## Reconciliation

`transform/tests/assert_known_season_records.sql` (tag `reconcile`) checks two published
records against the real data: Virat Kohli's 973 runs with 4 hundreds in 2016, and Dwayne
Bravo's 32 wickets in 2013. Every final winner 2008-2026 was also checked by hand.
