-- One row per delivery, with the scoring rules applied once so every mart agrees:
--   ball faced    = anything but a wide (a no-ball counts against the batter's balls)
--   legal ball    = neither a wide nor a no-ball (what counts towards the over)
--   bowler's runs = runs off the bat + wides + no-balls (byes, leg byes and penalties aren't his)
--   phase         = powerplay overs 1-6, middle 7-15, death 16-20
--   wickets       = dismissals on this ball; 'retired hurt' is not one
with dismissals as (
    select match_id, innings_no, over_no, ball_seq, count(*) as wickets
    from {{ ref('stg_wickets') }}
    where is_dismissal
    group by match_id, innings_no, over_no, ball_seq
)

select
    d.season,
    d.match_id,
    d.innings_no,
    bat.franchise as batting_team,
    bowl.franchise as bowling_team,
    d.is_super_over,
    d.over_no,
    d.ball_seq,
    case
        when d.over_no < 6 then 'Powerplay'
        when d.over_no < 15 then 'Middle'
        else 'Death'
    end as phase,
    d.batter_id,
    d.batter,
    d.non_striker_id,
    d.bowler_id,
    d.bowler,
    d.runs_batter,
    d.runs_extras,
    d.runs_total,
    d.wides,
    d.noballs,
    d.byes,
    d.legbyes,
    coalesce(w.wickets, 0) as wickets,
    d.wides = 0 as is_ball_faced,
    d.wides = 0 and d.noballs = 0 as is_legal,
    d.runs_batter + d.wides + d.noballs as bowler_runs,
    d.runs_total = 0 and d.wides = 0 and d.noballs = 0 as is_dot,
    d.runs_batter = 4 and not d.non_boundary as is_four,
    d.runs_batter = 6 and not d.non_boundary as is_six
from {{ silver('deliveries') }} as d
inner join {{ ref('franchises') }} as bat on d.batting_team = bat.team_name
inner join {{ ref('franchises') }} as bowl on d.bowling_team = bowl.team_name
left join dismissals as w
    on d.match_id = w.match_id and d.innings_no = w.innings_no
    and d.over_no = w.over_no and d.ball_seq = w.ball_seq
