import os
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment

def main():
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1)
    t_env = StreamTableEnvironment.create(env)

    # Load Jars for Kafka, Avro, and Schema Registry
    kafka_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.19/flink-sql-connector-kafka-3.1.0-1.19.jar"
    avro_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-avro/1.19.0/flink-avro-1.19.0.jar"
    confluent_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-avro-confluent-registry/1.19.0/flink-avro-confluent-registry-1.19.0.jar"

    t_env.get_config().set("pipeline.jars", f"{kafka_jar};{avro_jar};{confluent_jar}")

    # Enriched Source DDL
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
            'properties.group.id' = 'flink-anomaly-group',
            'scan.startup.mode' = 'latest-offset',
            'format' = 'avro-confluent',
            'avro-confluent.url' = 'http://schema-registry:8081'
        )
    """)

    # Kafka Alert Sink DDL (JSON format)
    t_env.execute_sql("""
        CREATE TABLE weather_alerts (
            alert_id STRING,
            location_id INT,
            city_name STRING,
            temperature FLOAT,
            expected_mean FLOAT,
            expected_std FLOAT,
            zscore FLOAT,
            observed_at BIGINT
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'weather.alerts',
            'properties.bootstrap.servers' = 'kafka:9092',
            'format' = 'json'
        )
    """)

    # Note: For demo purposes, we will use a rolling window of 1 day instead of 7 days
    # since we want anomalies to trigger faster with less historical data,
    # but the SQL syntax remains the same.
    # We compute rolling mean & std dev using an OVER window.
    t_env.execute_sql("""
        INSERT INTO weather_alerts
        SELECT * FROM (
            SELECT
                observation_id AS alert_id,
                location_id,
                city_name,
                temperature,
                AVG(temperature) OVER (
                    PARTITION BY location_id
                    ORDER BY row_time
                    RANGE BETWEEN INTERVAL '1' DAY PRECEDING AND CURRENT ROW
                ) AS expected_mean,
                STDDEV_SAMP(temperature) OVER (
                    PARTITION BY location_id
                    ORDER BY row_time
                    RANGE BETWEEN INTERVAL '1' DAY PRECEDING AND CURRENT ROW
                ) AS expected_std,
                (ABS(temperature - AVG(temperature) OVER (
                    PARTITION BY location_id
                    ORDER BY row_time
                    RANGE BETWEEN INTERVAL '1' DAY PRECEDING AND CURRENT ROW
                )) / COALESCE(NULLIF(STDDEV_SAMP(temperature) OVER (
                    PARTITION BY location_id
                    ORDER BY row_time
                    RANGE BETWEEN INTERVAL '1' DAY PRECEDING AND CURRENT ROW
                ), 0), 1.0)) AS zscore,
                observed_at
            FROM weather_enriched
        )
        WHERE zscore > 3.0 AND expected_std > 0.1
    """)

if __name__ == "__main__":
    main()
