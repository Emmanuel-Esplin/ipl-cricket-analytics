-- Every innings by every batter with the match date and result: strike rate per game.
select
    i.season,
    i.match_id,
    r.match_date,
    i.innings_no,
    i.team,
    i.opponent,
    r.outcome,
    i.batter_id,
    i.batter,
    i.runs,
    i.balls_faced,
    i.fours,
    i.sixes,
    i.dots,
    i.is_out,
    i.dismissal,
    i.strike_rate
from {{ ref('int_batter_innings') }} as i
inner join {{ ref('int_team_results') }} as r on i.match_id = r.match_id and i.team = r.team
