-- Who played for whom in each match.
select
    p.season,
    p.match_id,
    f.franchise as team,
    p.player_id,
    p.player_name
from {{ silver('players') }} as p
inner join {{ ref('franchises') }} as f on p.team = f.team_name
