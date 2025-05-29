import os
import geopandas as gpd
import json

def check_geojson(folder):
    layers = ["boundary", "building", "zones", "school", "polyclinic", "kindergarten", "green_zones", "parks"]
    
    # Загружаем обязательные и рекомендуемые столбцы из JSON файла
    with open(os.path.join(folder, 'required_columns.json'), 'r') as f:
        columns_info = json.load(f)

    # Проверка слоев
    for name in layers:
        path = os.path.join(folder, f"{name}.geojson")
        if os.path.exists(path):
            globals()[name] = gpd.read_file(path)
            
            # Проверка обязательных столбцов
            missing_required_columns = [col for col in columns_info.get(name, {}).get('required', []) if col not in globals()[name].columns]
            if missing_required_columns: 
                print(f"Ошибка: в слое '{name}' отсутствуют обязательные столбцы: {', '.join(missing_required_columns)}")
            
            # Проверка рекомендуемых столбцов
            missing_recommended_columns = [col for col in columns_info.get(name, {}).get('recommended', []) if col not in globals()[name].columns]
            if missing_recommended_columns: 
                print(f"Предупреждение: в слое '{name}' отсутствуют рекомендуемые столбцы: {', '.join(missing_recommended_columns)}")
            
        else:
            print(f"Ошибка: файл {path} не найден")

if __name__ == "__main__":
    folder = os.path.join(os.getcwd(), 'project')  # Папка с проектом
    check_geojson(folder)
