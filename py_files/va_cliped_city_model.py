# save this as analyze_zones.py
import geopandas as gpd
import pandas as pd
from shapely.validation import make_valid


def analyze_zones(zones_total_score, zones, va_path):
    target_models = ['low_rise', 'medium', 'central']
    target_codes = ['ДУ', 'УЦ', 'МЦ']

    # Фильтрация по нужным моделям и кодам
    zones_filtered = zones[
        zones['city_model'].isin(target_models) &
        (zones['is_living_zones'] == False) &
        zones['code_pzz'].isin(target_codes)
    ]

    # Приведение к единой СК
    zones_total_score = zones_total_score.to_crs(epsg=32637)
    zones_filtered = zones_filtered.to_crs(epsg=32637)

    # Объединяем старые и новые зоны
    zones_new = zones_total_score[~zones_total_score['id_zones'].isin(zones_filtered['id_zones'])]
    zones_new = pd.concat([zones_total_score, zones_filtered], ignore_index=True)
    zones_new_high_score = zones_new[zones_new["total_score"] > 0].copy()

    # Загрузка и преобразование валидности VA
    va = gpd.read_file(va_path).to_crs(epsg=32637)

    # Удаляем строки с пустыми геометриями
    va = va[va['geometry'].notnull()].copy()
    zones_new = zones_new[zones_new['geometry'].notnull()].copy()

    # Приведение к валидной геометрии
    va['geometry'] = va['geometry'].apply(lambda geom: make_valid(geom) if geom is not None else None)
    zones_new['geometry'] = zones_new['geometry'].apply(lambda geom: make_valid(geom) if geom is not None else None)


    # Пересечение зон с ВА
    va_clipped = gpd.overlay(va, zones_new, how='intersection')

    # Обработка геометрии + расчёт площади
    va_clipped = va_clipped[va_clipped['geometry'].notnull()].copy()
    va_clipped["geometry"] = va_clipped["geometry"].apply(lambda geom: make_valid(geom) if geom is not None else None)

    va_clipped["area_m2"] = va_clipped.geometry.area
    va_clipped["area_va"] = va_clipped["area_m2"]

    # Сохраняем нужные столбцы
    columns_to_keep = zones_new.columns.tolist()
    for col in ["area_va", "area_m2"]:
        if col not in columns_to_keep:
            columns_to_keep.append(col)
    va_clipped = va_clipped[columns_to_keep]

    # Разделение на пригодные и непридатные зоны
    va_for_house = va_clipped[va_clipped["total_score"] > 0].copy()
    va_dop = va_clipped[va_clipped["total_score"] <= 0].copy()

    # Цвета для визуализации
    color_map = {
        "low_rise": "orange",
        "medium": "pink",
        "central": "lightblue",
    }
    va_for_house["color"] = va_for_house["city_model"].map(color_map)

    # Базовая карта серых зон
    base = zones_new_high_score.explore(
        color="gray",
        alpha=0.4,
        legend=False,
        tooltip=False,
        tiles="CartoDB positron",
        style_kwds={"color": "lightgray", "weight": 0.1, 'fillOpacity': 0.2}
    )

    # Итоговая карта с подходящими ВА
    m = va_for_house.explore(
        column="city_model",
        color=va_for_house["color"],
        categorical=True,
        legend=True,
        alpha=1,
        tooltip=[
            "city_model",
            "total_score",
            "new_population",
            "need_dop_service",
            "new_population_dop",
            "score_category",
            "area_m2",
        ],
        tiles=None,
        m=base,
    )

    return m, va_for_house, va_dop, zones_new
