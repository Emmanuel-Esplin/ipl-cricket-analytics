-- One row per innings, super overs included (flagged).
select
    i.season,
    i.match_id,
    i.innings_no,
    bat.franchise as batting_team,
    bowl.franchise as bowling_team,
    i.is_super_over,
    i.target_runs,
    i.target_overs
from {{ silver('innings') }} as i
inner join {{ ref('franchises') }} as bat on i.batting_team = bat.team_name
inner join {{ ref('franchises') }} as bowl on i.bowling_team = bowl.team_name
