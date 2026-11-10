-- Reconciles against published IPL records; only passes on the real Cricsheet data.
--   2016: Virat Kohli scored 973 runs with 4 hundreds for Royal Challengers.
--   2013: Dwayne Bravo took 32 wickets for Chennai Super Kings.
{{ config(tags=['reconcile']) }}
select 'kohli_2016' as record
where not exists (
    select 1 from {{ ref('mart_batter_season') }}
    where season = 2016 and batter = 'V Kohli' and runs = 973 and hundreds = 4
)
union all
select 'bravo_2013' as record
where not exists (
    select 1 from {{ ref('mart_bowler_season') }}
    where season = 2013 and bowler = 'DJ Bravo' and wickets = 32
)
