-- One row per dismissal. Run outs, retirements and obstruction aren't credited to the bowler;
-- 'retired hurt' isn't a dismissal at all (the batter may come back).
select
    season,
    match_id,
    innings_no,
    over_no,
    ball_seq,
    player_out_id,
    player_out,
    kind,
    bowler_id,
    fielders,
    kind not in ('run out', 'retired hurt', 'retired out', 'obstructing the field')
        as is_bowler_wicket,
    kind <> 'retired hurt' as is_dismissal
from {{ silver('wickets') }}
