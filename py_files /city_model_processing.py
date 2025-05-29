import pandas as pd
import geopandas as gpd
import numpy as np
import json
from objectnat import get_balanced_buildings
import logging
from shapely.geometry import Polygon
from shapely.errors import TopologicalError

# Настройка логирования
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# Системы координат
AREA_CRS = "EPSG:3857"  # Web Mercator (метры, используется в онлайн-картах)
GEO_CRS = "EPSG:4326"   # Географическая система (градусы)

living_codes = None  # Глобально

def load_living_codes(file_path="living_codes.json"):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("living_codes", []))

def add_zone_attributes(zones, living_codes):
    zones = zones.to_crs(GEO_CRS)
    zones["is_living_zones"] = zones["code_pzz"].isin(living_codes)
    zones["id_zones"] = ["1." + str(i + 1) for i in range(len(zones))]

    # Внедряем код city_model_service_from_gdf
    TARGET_CODES = {"МЦ", "ДУ", "ДС", "ЖР", "Р.1", "Р.2", "Р.3", "СЦ", "УЦ", "П.5", "П.6", "П.7"}
    CITY_FIELD = "city_model"
    CODE_FIELD = "code_pzz"

    zones = zones.copy()
    zones[CODE_FIELD] = zones[CODE_FIELD].astype(str).str.strip().str.upper()

    def find_model(row, neighbor_zone):
        buffer_geom = row.geometry.buffer(20)
        buffer_matches = neighbor_zone[neighbor_zone.geometry.intersects(buffer_geom)]

        if not buffer_matches.empty:
            return buffer_matches.iloc[0][CITY_FIELD]

        dists = neighbor_zone.geometry.centroid.distance(row.geometry.centroid)
        return neighbor_zone.loc[dists.idxmin(), CITY_FIELD]

    targets = zones[(zones[CODE_FIELD].isin(TARGET_CODES)) & 
                    (zones[CITY_FIELD].isnull() | (zones[CITY_FIELD].str.strip() == ""))]

    logging.info(f"Найдено зон для обработки: {len(targets)}")

    neighbor_zone = zones[zones[CITY_FIELD].notnull() & (zones[CITY_FIELD] != "")]
    neighbor_zone = neighbor_zone[neighbor_zone[CITY_FIELD].isin({"medium", "low_rise", "central"})]
    neighbor_zone = neighbor_zone.sort_values("geometry", ascending=False).reset_index(drop=True)

    for idx, row in targets.iterrows():
        zones.loc[row.name, CITY_FIELD] = find_model(row, neighbor_zone)

    filled_count = zones.loc[targets.index, CITY_FIELD].notnull().sum()
    logging.info(f"Заполнено city_model для {filled_count} из {len(targets)} зон")

    zones = zones[["id_zones", "code_pzz", "city_model", "is_living_zones", "geometry"]]
    return zones

def prepare_building_data(buildings):
    buildings = buildings.to_crs(AREA_CRS)
    buildings['is_living'] = buildings['is_living'].replace({1: True, 0: False}).fillna(False).astype(bool)
    buildings['number_of_floors'] = buildings['number_of_floors'].fillna(1)
    buildings['footprint_area'] = buildings.geometry.area
    buildings['build_floor_area'] = buildings['footprint_area'] * buildings['number_of_floors']
    buildings['living_area'] = buildings.apply(
        lambda row: row['build_floor_area'] * 0.8 if row['is_living'] else 0, axis=1)
    buildings['non_living_area'] = buildings['build_floor_area'] - buildings['living_area']
    return buildings.to_crs(GEO_CRS)

def assign_population_to_buildings(buildings, living_population):
    buildings = buildings.to_crs(AREA_CRS)
    living_buildings = buildings[buildings['is_living']]
    living_buildings = get_balanced_buildings(living_buildings=living_buildings, population=living_population)

    non_living_buildings = buildings[~buildings['is_living']]
    non_living_buildings['number_of_floors'] = non_living_buildings['number_of_floors'].fillna(1)

    all_buildings = pd.concat([non_living_buildings, living_buildings], ignore_index=True)
    all_buildings['population'] = all_buildings['population'].fillna(0)
    all_buildings['id_build'] = ["2." + str(i + 1) for i in range(len(all_buildings))]

    return all_buildings.to_crs(GEO_CRS)

def join_zones_to_buildings(buildings, zones):
    buildings = buildings.to_crs(AREA_CRS)
    zones = zones.to_crs(AREA_CRS)

    centroids = buildings.copy()
    centroids['geometry'] = centroids.geometry.centroid
    joined = gpd.sjoin(centroids, zones[['id_zones', 'city_model', 'geometry']], how='left', predicate='within')
    
    buildings['id_zones'], buildings['city_model'] = joined[['id_zones', 'city_model']].T.values
    return buildings.to_crs(GEO_CRS)

def aggregate_zone_data(buildings, zones):
    buildings = buildings.to_crs(AREA_CRS)
    zones = zones.to_crs(AREA_CRS)

    sum_cols = ["footprint_area", "build_floor_area", "living_area", "non_living_area", "population"]
    mean_cols = ["number_of_floors"]
    
    aggregated = (
        buildings.groupby("id_zones")[sum_cols + mean_cols]
        .agg({**{col: "sum" for col in sum_cols}, **{col: "mean" for col in mean_cols}})  
        .round(2)
        .rename(columns=lambda c: f"sum_{c}" if c in sum_cols else f"avg_{c}")
        .reset_index()
    )
    aggregated["avg_number_of_floors"] = aggregated["avg_number_of_floors"].round().astype(int)

    zones = zones.merge(aggregated, on="id_zones", how="left").fillna(0)
    return zones.to_crs(GEO_CRS)

def distribute_population_across_zones(zones):
    zones = zones.to_crs(AREA_CRS)

    living = zones[zones["is_living_zones"]]
    non_living = zones[~zones["is_living_zones"]]

    if "area_zone" not in living.columns:
        living["area_zone"] = living.geometry.area

    def find_nearest(row):
        distances = living.geometry.distance(row.geometry)
        nearest_idx = distances.idxmin()
        return living.loc[nearest_idx, "id_zones"], distances.min()

    for idx, row in non_living.iterrows():
        nearest_id, _ = find_nearest(row)
        nearest = living[living["id_zones"] == nearest_id].iloc[0]
        pop = row["sum_population"]
        area = nearest["area_zone"]
        pop_density = pop / area
        living.loc[living["id_zones"] == nearest_id, "sum_population"] += pop_density * area

    zones = zones.merge(living[["id_zones", "sum_population"]], on="id_zones", how="left")
    zones = zones.drop(columns=["sum_population_x"]).rename(columns={"sum_population_y": "sum_population"})
    return zones.to_crs(GEO_CRS)

def process_city_model(zones, buildings, living_population, living_codes_path="living_codes.json"):
    global living_codes
    if living_codes is None:
        living_codes = load_living_codes(living_codes_path)

    print(f"🔹 Загруженные коды жилых зон: {living_codes}")

    zones = add_zone_attributes(zones, living_codes)
    buildings = prepare_building_data(buildings)
    balanced_buildings = assign_population_to_buildings(buildings, living_population)
    balanced_buildings = join_zones_to_buildings(balanced_buildings, zones)
    zones = aggregate_zone_data(balanced_buildings, zones)
    zones = distribute_population_across_zones(zones)

    return zones, balanced_buildings
