# service_data_processing.py

import pandas as pd
import geopandas as gpd
import numpy as np

# Данные для типов сервисов
SERVICE_TYPES = [
    {
        "name": "school",
        "bricks": [
            {"capacity": 250, "area": 3200.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 300, "area": 4000.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 600, "area": 8200.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 1100, "area": 130000000.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 250, "area": 2200.0, "is_integrated": True, "parking_area": 200.0},
            {"capacity": 300, "area": 3600.0, "is_integrated": True, "parking_area": 300.0},
            {"capacity": 450, "area": 7100.0, "is_integrated": True, "parking_area": 600.0},
            {"capacity": 650, "area": 1000000000.0, "is_integrated": True, "parking_area": 600.0},
        ],
    },
    {
        "name": "kindergarten",
        "bricks": [
            {"capacity": 150, "area": 230.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 220, "area": 400.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 420, "area": 700000000.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 120, "area": 180.0, "is_integrated": True, "parking_area": 250.0},
            {"capacity": 180, "area": 320.0, "is_integrated": True, "parking_area": 300.0},
            {"capacity": 320, "area": 600.0, "is_integrated": True, "parking_area": 320.0},
            {"capacity": 400, "area": 700000000.0, "is_integrated": True, "parking_area": 600.0},
        ],
    },
    {
        "name": "polyclinic",
        "bricks": [
            {"capacity": 300, "area": 850.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 500, "area": 1400.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 650, "area": 2000.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 800, "area": 10000000.0, "is_integrated": False, "parking_area": 0},
            {"capacity": 200, "area": 400.0, "is_integrated": True, "parking_area": 125.0},
            {"capacity": 350, "area": 700.0, "is_integrated": True, "parking_area": 150.0},
            {"capacity": 660, "area": 710000000.0, "is_integrated": True, "parking_area": 600.0},
        ],
    }
]

# Буферные зоны
BUFFER_SIZES = {
    "kindergarten_medium": 300,
    "kindergarten_central": 300,
    "kindergarten_low_rise": 300,
    "school_central": 500,
    "school_medium": 300,
    "school_low_rise": 500,
    "polyclinic_medium": 800,
    "polyclinic_central": 800,
    "polyclinic_low_rise": 1000,
}

def process_service_data(school, kindergarten, polyclinic, balanced_buildings):
    """
    Обработка данных о сервисах и их интеграция с данными зданий.

    Parameters:
    school (GeoDataFrame): Геоданные школ
    kindergarten (GeoDataFrame): Геоданные детских садов
    polyclinic (GeoDataFrame): Геоданные поликлиник
    balanced_buildings (GeoDataFrame): Геоданные зданий

    Returns:
    GeoDataFrame: Обработанные и интегрированные данные о сервисах
    """

    # 1. Обработка столбцов с id_service для разных типов объектов
    school['id_service'] = ["3." + str(i+1) for i in range(len(school))]
    col_3 = school.pop('id_service')
    school.insert(0, 'id_service', col_3)

    kindergarten['id_service'] = ["4." + str(i+1) for i in range(len(kindergarten))]
    col_4 = kindergarten.pop('id_service')
    kindergarten.insert(0, 'id_service', col_4)

    polyclinic['id_service'] = ["5." + str(i+1) for i in range(len(polyclinic))]
    col_4 = polyclinic.pop('id_service')
    polyclinic.insert(0, 'id_service', col_4)

    # Объединение данных в одну GeoDataFrame
    combined_service = gpd.GeoDataFrame(pd.concat([school, kindergarten, polyclinic], ignore_index=True))

    # 2. Приведение всех данных к одной проекции и выполнение spatial join
    combined_service = combined_service.to_crs(balanced_buildings.crs)

    service_filtered = balanced_buildings[["id_build", "id_zones", "is_living", "city_model", "build_floor_area", "geometry"]]
    joined = gpd.sjoin(combined_service, service_filtered, how="left", predicate="within").drop(columns=["index_right"], errors="ignore")
    joined["source"] = np.where(joined["id_build"].notna(), "within", np.nan)

    # Фильтрация точек без совпадений
    missing = joined[joined["id_build"].isna()].copy()

    # 3. Поиск ближайших зданий для точек без совпадений
    def find_nearest_building(missing_row):
        missing_point = missing_row.geometry
        distances = balanced_buildings.distance(missing_point)
        nearest_building_idx = distances.idxmin()
        return balanced_buildings.loc[nearest_building_idx]

    # Перенос атрибутов ближайших зданий
    for idx, row in missing.iterrows():
        nearest_building = find_nearest_building(row)
        for col in ["id_build", "id_zones", "is_living", "city_model", "build_floor_area"]:
            missing.at[idx, col] = nearest_building[col]
        missing.at[idx, "source"] = "nearest"

    # Объединение всех точек обратно в основной датафрейм
    combined_service = pd.concat([joined[joined["id_build"].notna()], missing], ignore_index=True)
    combined_service = combined_service[combined_service.geometry.notna()].copy()

    # Присваиваем столбцы, связанные с интеграцией
    combined_service["is_integrated"] = combined_service["is_living"] == True
    combined_service["area"] = combined_service["build_floor_area"]
    combined_service['city_model'] = combined_service['city_model'].fillna('medium')
    combined_service['city_model'] = combined_service['city_model'].apply(
        lambda x: 'medium' if pd.isna(x) or x == 0 else x
    )

    # 4. Применение функций для расчета вместимости
    def get_capacity(row, service_types):
        service_type = next((s for s in service_types if s["name"].lower() == row["type"].lower()), None)
        if not service_type:
            print(f"Не найден type: {row['type']}")
            return None
        matching_bricks = [b for b in service_type["bricks"] if b["is_integrated"] == row["is_integrated"]]
        if not matching_bricks:
            print(f"Нет подходящих bricks для type: {row['type']}, is_integrated: {row['is_integrated']}")
            return None
        for brick in matching_bricks:
            if row["area"] <= brick["area"]:
                return brick["capacity"]
        print(f"Нет соответствия по площади для type: {row['type']}, area: {row['area']}")
        return None

    if 'capacity' not in combined_service.columns:
        combined_service["is_integrated"] = combined_service["is_integrated"].astype(bool)
        combined_service["capacity"] = combined_service.apply(lambda row: get_capacity(row, SERVICE_TYPES), axis=1)

    # 5. Применение буферных зон
    def get_buffer(row):
        key = f"{row['type']}_{row['city_model']}"
        return BUFFER_SIZES.get(key, None)

    combined_service["buffer_zone"] = combined_service.apply(get_buffer, axis=1)

    # Генерация уникального идентификатора для каждого сервиса
    combined_service["identification_service"] = (
        combined_service["type"].astype(str) + "_" +
        combined_service["city_model"].astype(str) + "_" +
        combined_service["buffer_zone"].astype(str)
    )

    # Вывод количества пропущенных значений в столбцах
    print(f"Пропущенные значения в 'buffer_zone': {combined_service['buffer_zone'].isna().sum()}")
    print(f"Пропущенные значения в 'city_model': {combined_service['city_model'].isna().sum()}")
    print(f"Пропущенные значения в 'capacity': {combined_service['capacity'].isna().sum()}")

    return combined_service
