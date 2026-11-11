-- Bowling per player per season and franchise. Best figures are the most wickets in one
-- match, fewest runs breaking ties.
with ranked as (
    select
        *,
        row_number() over (
            partition by season, team, bowler_id
            order by wickets desc, runs_conceded asc, match_id
        ) as figures_rank
    from {{ ref('int_bowler_innings') }}
),

best as (
    select season, team, bowler_id, wickets as best_wickets, runs_conceded as best_runs
    from ranked
    where figures_rank = 1
)

select
    i.season,
    i.team,
    i.bowler_id,
    i.bowler,
    count(*) as innings,
    sum(i.legal_balls) as legal_balls,
    sum(i.runs_conceded) as runs_conceded,
    sum(i.wickets) as wickets,
    sum(i.dots) as dots,
    sum(i.fours_conceded) as fours_conceded,
    sum(i.sixes_conceded) as sixes_conceded,
    sum(case when i.wickets >= 4 then 1 else 0 end) as four_wicket_hauls,
    max(b.best_wickets) as best_wickets,
    max(b.best_runs) as best_runs,
    {{ ratio('sum(i.runs_conceded)', 'sum(i.legal_balls)', 6) }} as economy,
    {{ ratio('sum(i.runs_conceded)', 'sum(i.wickets)') }} as average,
    {{ ratio('sum(i.legal_balls)', 'sum(i.wickets)') }} as bowling_strike_rate,
    {{ ratio('sum(i.dots)', 'sum(i.legal_balls)', 100) }} as dot_ball_pct
from {{ ref('int_bowler_innings') }} as i
inner join best as b
    on i.season = b.season and i.team = b.team and i.bowler_id = b.bowler_id
group by i.season, i.team, i.bowler_id, i.bowler
