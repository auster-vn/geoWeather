import os
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment

def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    t_env = StreamTableEnvironment.create(env)

    # Load Jars for Kafka, Avro, Schema Registry, JDBC, and PostgreSQL Driver
    kafka_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.19/flink-sql-connector-kafka-3.1.0-1.19.jar"
    avro_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-avro/1.19.0/flink-avro-1.19.0.jar"
    confluent_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-avro-confluent-registry/1.19.0/flink-avro-confluent-registry-1.19.0.jar"
    jdbc_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-connector-jdbc/3.1.2-1.19/flink-connector-jdbc-3.1.2-1.19.jar"
    postgres_jar = "https://jdbc.postgresql.org/download/postgresql-42.7.3.jar"

    t_env.get_config().set("pipeline.jars", f"{kafka_jar};{avro_jar};{confluent_jar};{jdbc_jar};{postgres_jar}")

    # Enriched Source DDL
    # Note: we need event time attributes and watermarks for windowing
    # TO_TIMESTAMP(FROM_UNIXTIME(observed_at / 1000)) converts bigint millis to Timestamp(3)
    t_env.execute_sql("""
        CREATE TABLE weather_enriched (
            observation_id STRING,
            location_id INT,
            city_name STRING,
            country_code STRING,
            latitude DOUBLE,
            longitude DOUBLE,
            h3_index_r4 STRING,
            h3_index_r7 STRING,
            observed_at BIGINT,
            temperature FLOAT,
            feels_like FLOAT,
            humidity INT,
            wind_speed FLOAT,
            wind_direction INT,
            precipitation FLOAT,
            weather_code INT,
            pressure FLOAT,
            visibility INT,
            uv_index FLOAT,
            cloud_cover INT,
            schema_version INT,
            row_time AS TO_TIMESTAMP(FROM_UNIXTIME(observed_at / 1000)),
            WATERMARK FOR row_time AS row_time - INTERVAL '10' SECOND
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'weather.observations.enriched',
            'properties.bootstrap.servers' = 'kafka:9092',
            'properties.group.id' = 'flink-aggregate-group',
            'scan.startup.mode' = 'latest-offset',
            'format' = 'avro-confluent',
            'avro-confluent.url' = 'http://schema-registry:8081'
        )
    """)

    # TimescaleDB Sink DDL (JDBC)
    t_env.execute_sql("""
        CREATE TABLE timescale_hourly_agg (
            h3_index_r4 STRING,
            window_start TIMESTAMP(3),
            window_end TIMESTAMP(3),
            avg_temperature FLOAT,
            max_wind_speed FLOAT,
            total_precip FLOAT,
            avg_humidity FLOAT,
            observation_count BIGINT,
            PRIMARY KEY (h3_index_r4, window_start) NOT ENFORCED
        ) WITH (
            'connector' = 'jdbc',
            'url' = 'jdbc:postgresql://timescaledb:5432/geoweather_ts',
            'table-name' = 'weather_hourly_agg',
            'username' = 'postgres',
            'password' = 'geoweather_local'
        )
    """)

    # Kafka Aggregate Sink DDL (JSON format)
    t_env.execute_sql("""
        CREATE TABLE kafka_hourly_agg (
            h3_index_r4 STRING,
            window_start TIMESTAMP(3),
            window_end TIMESTAMP(3),
            avg_temperature FLOAT,
            max_wind_speed FLOAT,
            total_precip FLOAT,
            avg_humidity FLOAT,
            observation_count BIGINT
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'weather.aggregates.hourly',
            'properties.bootstrap.servers' = 'kafka:9092',
            'format' = 'json'
        )
    """)

    # We use a statement set to execute multiple queries in the same execution graph
    statement_set = t_env.create_statement_set()

    # Aggregated query view
    agg_sql = """
        SELECT
            h3_index_r4,
            TUMBLE_START(row_time, INTERVAL '1' HOUR) AS window_start,
            TUMBLE_END(row_time, INTERVAL '1' HOUR) AS window_end,
            AVG(temperature) AS avg_temperature,
            MAX(wind_speed) AS max_wind_speed,
            SUM(precipitation) AS total_precip,
            AVG(CAST(humidity AS FLOAT)) AS avg_humidity,
            COUNT(*) AS observation_count
        FROM weather_enriched
        WHERE h3_index_r4 IS NOT NULL
        GROUP BY h3_index_r4, TUMBLE(row_time, INTERVAL '1' HOUR)
    """

    statement_set.add_insert_sql(f"INSERT INTO timescale_hourly_agg {agg_sql}")
    statement_set.add_insert_sql(f"INSERT INTO kafka_hourly_agg {agg_sql}")

    # Execute both insertions
    statement_set.execute()

if __name__ == "__main__":
    main()
