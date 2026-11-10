-- Two rows per match, one from each side's point of view.
-- A super-over tie counts as a win for the side that won the super over; no result is neither.
with sides as (
    select season, match_id, match_date, stage, team1 as team, team2 as opponent,
           winner, result, decided_by_super_over, method
    from {{ ref('stg_matches') }}
    union all
    select season, match_id, match_date, stage, team2 as team, team1 as opponent,
           winner, result, decided_by_super_over, method
    from {{ ref('stg_matches') }}
)

select
    season,
    match_id,
    match_date,
    stage,
    team,
    opponent,
    case
        when result = 'no result' then 'No result'
        when winner = team then 'Won'
        else 'Lost'
    end as outcome,
    decided_by_super_over,
    method is not null as rain_affected
from sides
