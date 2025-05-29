import os
import geopandas as gpd
import json
def check_geojson(folder):
    layers = ["boundary", "buildings", "zones", "school", "polyclinic", "kindergarten", "green", "park"]
    
    required_columns_path = os.path.join(folder, 'required_columns.json')
    if not os.path.exists(required_columns_path):
        print(f"Ошибка: файл {required_columns_path} не найден")
        return {}

    with open(required_columns_path, 'r', encoding='utf-8') as f:
        columns_info = json.load(f)

    data = {}  # Храним GeoDataFrame тут

    for name in layers:
        path = os.path.join(folder, f"{name}.geojson")
        if os.path.exists(path):
            gdf = gpd.read_file(path)
            data[name] = gdf

            missing_required = [col for col in columns_info.get(name, {}).get('required', []) if col not in gdf.columns]
            if missing_required:
                print(f"Ошибка: в слое '{name}' отсутствуют обязательные столбцы: {', '.join(missing_required)}")

            missing_recommended = [col for col in columns_info.get(name, {}).get('recommended', []) if col not in gdf.columns]
            if missing_recommended:
                print(f"Предупреждение: в слое '{name}' отсутствуют рекомендуемые столбцы: {', '.join(missing_recommended)}")
        else:
            print(f"Ошибка: файл {path} не найден")

    return data
