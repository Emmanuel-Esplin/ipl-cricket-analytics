-- One display name per Cricsheet player id (names are stable per id; max() just picks one).
select player_id, max(player_name) as player_name
from {{ ref('stg_players') }}
where player_id is not null
group by player_id
