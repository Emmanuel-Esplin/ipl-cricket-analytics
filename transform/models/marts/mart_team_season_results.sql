-- Wins and losses per franchise per season. win_pct leaves out no-results.
select
    season,
    team,
    count(*) as matches,
    sum(case when outcome = 'Won' then 1 else 0 end) as wins,
    sum(case when outcome = 'Lost' then 1 else 0 end) as losses,
    sum(case when outcome = 'No result' then 1 else 0 end) as no_results,
    sum(case when outcome = 'Won' and decided_by_super_over then 1 else 0 end)
        as super_over_wins,
    {{ ratio("sum(case when outcome = 'Won' then 1 else 0 end)",
             "sum(case when outcome <> 'No result' then 1 else 0 end)", 100) }} as win_pct
from {{ ref('int_team_results') }}
group by season, team
