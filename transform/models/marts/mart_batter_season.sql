-- Batting per player per season and franchise. Sums are kept so the dashboard can add up
-- seasons and recompute averages and strike rates correctly.
select
    season,
    team,
    batter_id,
    batter,
    count(*) as innings,
    sum(case when is_out then 0 else 1 end) as not_outs,
    sum(runs) as runs,
    sum(balls_faced) as balls_faced,
    sum(case when is_out then 1 else 0 end) as dismissals,
    max(runs) as highest_score,
    sum(case when runs >= 50 and runs < 100 then 1 else 0 end) as fifties,
    sum(case when runs >= 100 then 1 else 0 end) as hundreds,
    sum(fours) as fours,
    sum(sixes) as sixes,
    sum(dots) as dots,
    {{ ratio('sum(runs)', 'sum(case when is_out then 1 else 0 end)') }} as average,
    {{ ratio('sum(runs)', 'sum(balls_faced)', 100) }} as strike_rate
from {{ ref('int_batter_innings') }}
group by season, team, batter_id, batter
