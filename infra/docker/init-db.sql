-- Enable PostGIS extensions
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;

-- Create cities table
CREATE TABLE IF NOT EXISTS cities (
    geoname_id      INTEGER PRIMARY KEY,
    city_name       VARCHAR(200) NOT NULL,
    ascii_name      VARCHAR(200),
    country_code    CHAR(2) NOT NULL,
    admin1_code     VARCHAR(20),
    admin2_code     VARCHAR(80),
    population      INTEGER DEFAULT 0,
    timezone        VARCHAR(40),
    geom            GEOMETRY(POINT, 4326) NOT NULL,
    h3_r4           VARCHAR(15),
    h3_r7           VARCHAR(15),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Spatial and standard indexes
CREATE INDEX IF NOT EXISTS cities_geom_gist ON cities USING GIST(geom);
CREATE INDEX IF NOT EXISTS cities_h3_r4_idx ON cities(h3_r4);
CREATE INDEX IF NOT EXISTS cities_h3_r7_idx ON cities(h3_r7);
CREATE INDEX IF NOT EXISTS cities_country_idx ON cities(country_code);

-- Create regions table (GADM boundaries)
CREATE TABLE IF NOT EXISTS regions (
    id           SERIAL PRIMARY KEY,
    region_code  VARCHAR(10) UNIQUE NOT NULL,
    region_name  VARCHAR(200) NOT NULL,
    country_code CHAR(2),
    level        INT,  -- 0=country, 1=state, 2=district
    geom         GEOMETRY(MULTIPOLYGON, 4326) NOT NULL,
    bbox         GEOMETRY(POLYGON, 4326)
);

CREATE INDEX IF NOT EXISTS regions_geom_gist ON regions USING GIST(geom);

-- Create weather_current table in Postgres for the latest readings
CREATE TABLE IF NOT EXISTS weather_current (
    location_id     INTEGER PRIMARY KEY REFERENCES cities(geoname_id),
    temperature     REAL,
    feels_like      REAL,
    humidity        SMALLINT,
    wind_speed      REAL,
    wind_direction  SMALLINT,
    precipitation   REAL,
    weather_code    SMALLINT,
    pressure        REAL,
    visibility      INTEGER,
    uv_index        REAL,
    cloud_cover     SMALLINT,
    updated_at      TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS weather_current_updated_idx ON weather_current(updated_at);
