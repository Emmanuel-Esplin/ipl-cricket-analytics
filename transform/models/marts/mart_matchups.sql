-- Batter against bowler across every season: who dominates whom. Dismissals count only
-- wickets the bowler is credited with (a run out isn't a win for the bowler).
with balls as (
    select
        batter_id, bowler_id,
        count(distinct match_id) as matches,
        sum(case when is_ball_faced then 1 else 0 end) as balls_faced,
        sum(runs_batter) as runs,
        sum(case when is_ball_faced and runs_batter = 0 then 1 else 0 end) as dots,
        sum(case when is_four then 1 else 0 end) as fours,
        sum(case when is_six then 1 else 0 end) as sixes
    from {{ ref('stg_deliveries') }}
    where not is_super_over
    group by batter_id, bowler_id
),

outs as (
    select w.player_out_id as batter_id, w.bowler_id, count(*) as dismissals
    from {{ ref('stg_wickets') }} as w
    inner join {{ ref('stg_innings') }} as i
        on w.match_id = i.match_id and w.innings_no = i.innings_no
    where w.is_bowler_wicket and not i.is_super_over
    group by w.player_out_id, w.bowler_id
)

select
    b.batter_id,
    bat.player_name as batter,
    b.bowler_id,
    bowl.player_name as bowler,
    b.matches,
    b.balls_faced,
    b.runs,
    coalesce(o.dismissals, 0) as dismissals,
    b.dots,
    b.fours,
    b.sixes,
    {{ ratio('b.runs', 'b.balls_faced', 100) }} as strike_rate,
    {{ ratio('b.runs', 'o.dismissals') }} as average
from balls as b
inner join {{ ref('int_players') }} as bat on b.batter_id = bat.player_id
inner join {{ ref('int_players') }} as bowl on b.bowler_id = bowl.player_id
left join outs as o on b.batter_id = o.batter_id and b.bowler_id = o.bowler_id
