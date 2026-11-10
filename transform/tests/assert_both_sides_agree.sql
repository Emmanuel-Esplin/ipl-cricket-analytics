-- Every decided match has exactly one winner and one loser.
select match_id
from {{ ref('int_team_results') }}
group by match_id
having sum(case when outcome = 'Won' then 1 else 0 end)
       <> sum(case when outcome = 'Lost' then 1 else 0 end)
    or count(*) <> 2
