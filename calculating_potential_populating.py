import geopandas as gpd
import pandas as pd
import numpy as np

def calculate_population(row):
    """
    Расчёт возможного нового населения и потребности в дополнительной социальной инфраструктуре.
    """
    school = row["school_free_places"]
    kindergarten = row["kindergarten_free_places"]
    polyclinic = row["polyclinic_free_places"]

    new_population = np.nan
    new_population_dop = np.nan
    need_dop_service = None

    # Убедимся, что все сервисы имеют больше нуля, прежде чем их использовать
    if school > 0 and kindergarten > 0 and polyclinic > 0:
        school_vs_kindergarten = min(school, kindergarten) * 2.8
        new_population = min(school_vs_kindergarten, polyclinic)

    # Учитываем поликлинику, если она отсутствует
    elif polyclinic == 0 and school > 0 and kindergarten > 0:
        new_population_dop = min(school, kindergarten) * 2.8
        need_dop_service = "polyclinic"

    # Учитываем школу, если она отсутствует
    elif school == 0 and kindergarten > 0 and polyclinic > 0:
        new_population_dop = min(kindergarten * 2.8, polyclinic)
        need_dop_service = "school"

    # Учитываем детский сад, если его нет
    elif kindergarten == 0 and school > 0 and polyclinic > 0:
        new_population_dop = min(school * 2.8, polyclinic)
        need_dop_service = "kindergarten"

    # Фильтрация для значений new_population_dop < 49
    if pd.notnull(new_population_dop) and new_population_dop < 1:
        need_dop_service = "no feasible service placement"
        new_population_dop = None  # Убираем значение, если оно меньше 49

    return pd.Series([new_population, new_population_dop, need_dop_service])


def calculate_and_update(living_zones):
    """
    Расчёт и перезапись значений в столбцах на основе определённых условий.
    """
    if not isinstance(living_zones, gpd.GeoDataFrame):
        raise ValueError("Input must be a GeoDataFrame")

    # Применяем функцию для расчёта
    living_zones[["new_population", "new_population_dop", "need_dop_service"]] = (
        living_zones.apply(calculate_population, axis=1)
    )

    # Приводим к числовому типу
    living_zones["new_population"] = pd.to_numeric(
        living_zones["new_population"], downcast="integer", errors="coerce"
    )

    living_zones["new_population_dop"] = pd.to_numeric(
        living_zones["new_population_dop"], downcast="integer", errors="coerce"
    )

    # Округляем и фильтруем малые значения (менее 49)
    living_zones["new_population"] = living_zones["new_population"].apply(
        lambda x: int(round(x)) if pd.notnull(x) and x > 1 else None
    )

    living_zones["new_population_dop"] = living_zones["new_population_dop"].apply(
        lambda x: int(round(x)) if pd.notnull(x) and x > 19 else None
    )

    # Перезаписываем на "no feasible service placement", если new_population_dop == 0
    living_zones.loc[living_zones["new_population_dop"] == 0, "need_dop_service"] = "no feasible service placement"

    return living_zones


def visualize_by_need_service(living_zones):
    """
    Визуализация GeoDataFrame по нуждаемым дополнительным сервисам.
    """
    if not isinstance(living_zones, gpd.GeoDataFrame):
        raise ValueError("Input must be a GeoDataFrame")

    # Дополнительная фильтрация перед визуализацией
    living_zones.loc[living_zones["new_population_dop"] == 0, "need_dop_service"] = "no feasible service placement"

    # Визуализируем
    living_zones.explore(
        column="need_dop_service",
        cmap="Set2",
        legend=True,
        style_kwds={"color": "black", "weight": 0.5},
        tooltip=[
            "id_zones",
            "need_dop_service",
            "new_population",
            "new_population_dop",
        ],
        tiles="CartoDB positron",
    )
