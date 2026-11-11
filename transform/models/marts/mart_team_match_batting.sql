-- Each side's batting in each match (super overs excluded), with the result alongside:
-- the strike rate per game. strike_rate counts runs off the bat per 100 balls faced;
-- run_rate counts every run (extras included) per six legal balls.
with batting as (
    select
        season, match_id, innings_no, batting_team as team, bowling_team as opponent,
        sum(runs_total) as runs,
        sum(runs_batter) as runs_off_bat,
        sum(case when is_ball_faced then 1 else 0 end) as balls_faced,
        sum(case when is_legal then 1 else 0 end) as legal_balls,
        sum(wickets) as wickets_lost,
        sum(case when is_four then 1 else 0 end) as fours,
        sum(case when is_six then 1 else 0 end) as sixes,
        sum(case when is_dot then 1 else 0 end) as dots
    from {{ ref('stg_deliveries') }}
    where not is_super_over
    group by season, match_id, innings_no, batting_team, bowling_team
)

select
    b.season,
    b.match_id,
    r.match_date,
    r.stage,
    b.innings_no,
    b.team,
    b.opponent,
    r.outcome,
    b.runs,
    b.wickets_lost,
    b.legal_balls,
    b.balls_faced,
    b.runs_off_bat,
    b.fours,
    b.sixes,
    b.dots,
    {{ ratio('b.runs_off_bat', 'b.balls_faced', 100) }} as strike_rate,
    {{ ratio('b.runs', 'b.legal_balls', 6) }} as run_rate
from batting as b
inner join {{ ref('int_team_results') }} as r on b.match_id = r.match_id and b.team = r.team
