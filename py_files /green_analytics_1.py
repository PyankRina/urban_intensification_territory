import geopandas as gpd
import pandas as pd
import numpy as np
from IPython.display import display  # Для вывода в Jupyter

# Нормативы по типам городской среды (м²/чел.)
normatives = {
    "low_rise": 30,
    "medium": 10,
    "central": 6,
}

def calculate_green_analytics(green, park, living_zones, crs_epsg: int = 3395):
    """
    Расчет обеспеченности зелеными насаждениями для каждого квартала.

    Параметры:
        green (GeoDataFrame): Зелёные насаждения общего пользования.
        park (GeoDataFrame): Парки.
        living_zones (GeoDataFrame): Жилые зоны с населением и моделью городской среды.
        crs_epsg (int): EPSG-код проекционной системы координат (по умолчанию EPSG:3395).
    """

    # Добавим ID зелёных зон
    green['id_green_zone'] = ["9." + str(i + 1) for i in range(len(green))]
    green.insert(0, 'id_green_zone', green.pop('id_green_zone'))

    park['id_green_zone'] = ["6." + str(i + 1) for i in range(len(park))]
    park.insert(0, 'id_green_zone', park.pop('id_green_zone'))

    # Объединяем зелёные зоны
    green_combined = gpd.GeoDataFrame(pd.concat([green, park], ignore_index=True), crs=green.crs)
    green_combined = green_combined.to_crs(epsg=crs_epsg)

    # Площадь зелёных зон (в м²)
    green_combined["area"] = green_combined.geometry.area
    green_space_total = green_combined["area"].sum()
    display(f"Общая площадь зелёных насаждений в городе (м²): {green_space_total:,.0f}")

    # Численность населения
    living_zones["sum_population"] = living_zones["sum_population"].astype(float)
    total_population = living_zones["sum_population"].sum()

    # Население по типам городской среды
    population_by_type = living_zones.groupby("city_model")["sum_population"].sum().to_dict()

    # Зелень по типам среды
    green_by_type = {
        t: (population_by_type[t] / total_population) * green_space_total
        for t in population_by_type
    }

    def calculate_zone_green_simple(row):
        city_type = row["city_model"]
        pop = row["sum_population"]
        type_population = population_by_type.get(city_type, 0)
        type_green = green_by_type.get(city_type, 0)

        if pop == 0:
            pop = 1
        if type_population == 0:
            return pd.Series([0, 0, 0])

        share = pop / type_population
        allocated_green = type_green * share
        per_capita = allocated_green / pop
        normative = normatives.get(city_type, 0)
        difference = per_capita - normative

        return pd.Series([allocated_green, per_capita, difference])

    living_zones[[
        "green_allocated",
        "green_per_capita",
        "difference_from_normative"
    ]] = living_zones.apply(calculate_zone_green_simple, axis=1)

    # Вывод по каждому типу городской среды
    city_stats = []
    for city_type in living_zones['city_model'].unique():
        total_green = living_zones[living_zones['city_model'] == city_type]['green_allocated'].sum()
        total_pop = living_zones[living_zones['city_model'] == city_type]['sum_population'].sum()
        avg_green_per_capita = total_green / total_pop if total_pop > 0 else 0
        city_stats.append({
            'city_type': city_type,
            'total_green': round(total_green, 2),
            'avg_green_per_capita': round(avg_green_per_capita, 2)
        })

    display(pd.DataFrame(city_stats))

    avg_city_green_per_capita = green_space_total / total_population if total_population > 0 else 0
    display(f"Средняя обеспеченность зелёными насаждениями на человека по городу: {avg_city_green_per_capita:.2f} м²/чел.\n")

    return living_zones
