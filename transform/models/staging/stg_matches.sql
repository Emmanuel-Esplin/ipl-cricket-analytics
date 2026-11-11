-- One row per match, team names rolled up to franchises. 'winner' includes super-over winners.
select
    m.season,
    m.match_id,
    m.season_label,
    cast(m.match_date as date) as match_date,
    m.match_number,
    coalesce(m.stage, 'League') as stage,
    m.city,
    m.venue,
    t1.franchise as team1,
    t2.franchise as team2,
    tw.franchise as toss_winner,
    m.toss_decision,
    w.franchise as winner,
    m.result,
    m.win_by_runs,
    m.win_by_wickets,
    m.method,
    m.super_over_winner is not null as decided_by_super_over,
    m.player_of_match
from {{ silver('matches') }} as m
inner join {{ ref('franchises') }} as t1 on m.team1 = t1.team_name
inner join {{ ref('franchises') }} as t2 on m.team2 = t2.team_name
inner join {{ ref('franchises') }} as tw on m.toss_winner = tw.team_name
left join {{ ref('franchises') }} as w on m.winner = w.team_name
