-- One row per bowler per innings (super overs excluded): the bowler's figures for the match.
with balls as (
    select
        season, match_id, innings_no, bowling_team, batting_team, bowler_id,
        sum(case when is_legal then 1 else 0 end) as legal_balls,
        sum(bowler_runs) as runs_conceded,
        sum(case when is_dot then 1 else 0 end) as dots,
        sum(case when is_four then 1 else 0 end) as fours_conceded,
        sum(case when is_six then 1 else 0 end) as sixes_conceded,
        sum(case when wides > 0 then 1 else 0 end) as wides,
        sum(case when noballs > 0 then 1 else 0 end) as noballs
    from {{ ref('stg_deliveries') }}
    where not is_super_over
    group by season, match_id, innings_no, bowling_team, batting_team, bowler_id
),

wkts as (
    select match_id, innings_no, bowler_id, count(*) as wickets
    from {{ ref('stg_wickets') }}
    where is_bowler_wicket
    group by match_id, innings_no, bowler_id
)

select
    b.season,
    b.match_id,
    b.innings_no,
    b.bowling_team as team,
    b.batting_team as opponent,
    b.bowler_id,
    p.player_name as bowler,
    b.legal_balls,
    b.runs_conceded,
    coalesce(w.wickets, 0) as wickets,
    b.dots,
    b.fours_conceded,
    b.sixes_conceded,
    b.wides,
    b.noballs,
    {{ ratio('b.runs_conceded', 'b.legal_balls', 6) }} as economy
from balls as b
inner join {{ ref('int_players') }} as p on b.bowler_id = p.player_id
left join wkts as w
    on b.match_id = w.match_id and b.innings_no = w.innings_no and b.bowler_id = w.bowler_id
