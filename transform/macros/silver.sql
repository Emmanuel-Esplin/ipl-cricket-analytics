{# A silver table: Parquet partitioned by season locally, the Glue table on Athena. #}
{% macro silver(table) %}
  {%- if target.type == 'duckdb' -%}
    read_parquet('{{ var("silver_dir") }}/{{ table }}/*/*.parquet', hive_partitioning = false)
  {%- else -%}
    {{ source('silver', table) }}
  {%- endif -%}
{% endmacro %}

{# a / b as a double, null when b is zero (a bowler with no wickets has no average). #}
{% macro ratio(numerator, denominator, scale=1) %}
  case when {{ denominator }} > 0
       then {{ scale }} * cast({{ numerator }} as double) / {{ denominator }} end
{% endmacro %}
