-- Batting by phase (powerplay 1-6, middle 7-15, death 16-20) per franchise and season.
select
    season,
    batting_team as team,
    phase,
    count(distinct match_id) as matches,
    sum(runs_total) as runs,
    sum(runs_batter) as runs_off_bat,
    sum(case when is_ball_faced then 1 else 0 end) as balls_faced,
    sum(case when is_legal then 1 else 0 end) as legal_balls,
    sum(wickets) as wickets_lost,
    sum(case when is_four or is_six then 1 else 0 end) as boundaries,
    {{ ratio('sum(runs_batter)', 'sum(case when is_ball_faced then 1 else 0 end)', 100) }}
        as strike_rate,
    {{ ratio('sum(runs_total)', 'sum(case when is_legal then 1 else 0 end)', 6) }} as run_rate
from {{ ref('stg_deliveries') }}
where not is_super_over
group by season, batting_team, phase
