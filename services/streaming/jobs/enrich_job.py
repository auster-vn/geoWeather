import os
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.table import StreamTableEnvironment, DataTypes
from pyflink.table.udf import udf
import h3

def main():
    # Setup environments
    env = StreamExecutionEnvironment.get_execution_environment()
    env.set_parallelism(1) # Local development
    t_env = StreamTableEnvironment.create(env)

    # Configure pipeline dependencies for Kafka, Avro, and Confluent Registry
    # This automatically downloads the required connectors on startup
    kafka_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.1.0-1.19/flink-sql-connector-kafka-3.1.0-1.19.jar"
    avro_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-avro/1.19.0/flink-avro-1.19.0.jar"
    confluent_jar = "https://repo1.maven.org/maven2/org/apache/flink/flink-avro-confluent-registry/1.19.0/flink-avro-confluent-registry-1.19.0.jar"
    
    t_env.get_config().set("pipeline.jars", f"{kafka_jar};{avro_jar};{confluent_jar}")

    # Register H3 UDFs
    @udf(result_type=DataTypes.STRING())
    def get_h3_r4(lat: float, lon: float) -> str:
        if lat is None or lon is None:
            return None
        return h3.latlng_to_cell(lat, lon, 4)

    @udf(result_type=DataTypes.STRING())
    def get_h3_r7(lat: float, lon: float) -> str:
        if lat is None or lon is None:
            return None
        return h3.latlng_to_cell(lat, lon, 7)

    t_env.create_temporary_system_function("h3_r4", get_h3_r4)
    t_env.create_temporary_system_function("h3_r7", get_h3_r7)

    # Source DDL: Raw observations topic
    t_env.execute_sql("""
        CREATE TABLE weather_raw (
            observation_id STRING,
            location_id INT,
            city_name STRING,
            country_code STRING,
            latitude DOUBLE,
            longitude DOUBLE,
            h3_index_r4 STRING,
            h3_index_r7 STRING,
            observed_at BIGINT, -- Avro timestamp is represented as bigint millis
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
            schema_version INT
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'weather.observations.raw',
            'properties.bootstrap.servers' = 'kafka:9092',
            'properties.group.id' = 'flink-enrich-raw',
            'scan.startup.mode' = 'latest-offset',
            'format' = 'avro-confluent',
            'avro-confluent.url' = 'http://schema-registry:8081'
        )
    """)

    # Sink DDL: Enriched observations topic
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
            schema_version INT
        ) WITH (
            'connector' = 'kafka',
            'topic' = 'weather.observations.enriched',
            'properties.bootstrap.servers' = 'kafka:9092',
            'format' = 'avro-confluent',
            'avro-confluent.url' = 'http://schema-registry:8081'
        )
    """)

    # Run Enrichment Query
    t_env.execute_sql("""
        INSERT INTO weather_enriched
        SELECT 
            observation_id,
            location_id,
            city_name,
            country_code,
            latitude,
            longitude,
            h3_r4(latitude, longitude) AS h3_index_r4,
            h3_r7(latitude, longitude) AS h3_index_r7,
            observed_at,
            temperature,
            feels_like,
            humidity,
            wind_speed,
            wind_direction,
            precipitation,
            weather_code,
            pressure,
            visibility,
            uv_index,
            cloud_cover,
            schema_version
        FROM weather_raw
    """)

if __name__ == "__main__":
    main()
