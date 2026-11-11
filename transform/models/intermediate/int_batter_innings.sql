-- One row per batter per innings (super overs excluded). A batter who only ever stood at the
-- non-striker's end still batted, so both ends count towards appearing in the innings.
with balls as (
    select
        match_id, innings_no, batter_id,
        sum(runs_batter) as runs,
        sum(case when is_ball_faced then 1 else 0 end) as balls_faced,
        sum(case when is_four then 1 else 0 end) as fours,
        sum(case when is_six then 1 else 0 end) as sixes,
        sum(case when is_ball_faced and runs_batter = 0 then 1 else 0 end) as dots
    from {{ ref('stg_deliveries') }}
    where not is_super_over
    group by match_id, innings_no, batter_id
),

appeared as (
    select distinct season, match_id, innings_no, batting_team, bowling_team, batter_id
    from {{ ref('stg_deliveries') }}
    where not is_super_over
    union
    select distinct season, match_id, innings_no, batting_team, bowling_team,
           non_striker_id as batter_id
    from {{ ref('stg_deliveries') }}
    where not is_super_over
),

outs as (
    select match_id, innings_no, player_out_id, max(kind) as dismissal
    from {{ ref('stg_wickets') }}
    where is_dismissal
    group by match_id, innings_no, player_out_id
)

select
    a.season,
    a.match_id,
    a.innings_no,
    a.batting_team as team,
    a.bowling_team as opponent,
    a.batter_id,
    p.player_name as batter,
    coalesce(b.runs, 0) as runs,
    coalesce(b.balls_faced, 0) as balls_faced,
    coalesce(b.fours, 0) as fours,
    coalesce(b.sixes, 0) as sixes,
    coalesce(b.dots, 0) as dots,
    o.dismissal is not null as is_out,
    coalesce(o.dismissal, 'not out') as dismissal,
    {{ ratio('coalesce(b.runs, 0)', 'b.balls_faced', 100) }} as strike_rate
from appeared as a
inner join {{ ref('int_players') }} as p on a.batter_id = p.player_id
left join balls as b
    on a.match_id = b.match_id and a.innings_no = b.innings_no and a.batter_id = b.batter_id
left join outs as o
    on a.match_id = o.match_id and a.innings_no = o.innings_no and a.batter_id = o.player_out_id
