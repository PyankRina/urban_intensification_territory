import os
import geopandas as gpd
import pandas as pd
from objectnat import get_service_provision, clip_provision

def process_services(matrix, combined_service, balanced_buildings, output_path):
    """
    Обрабатывает данные обеспеченности по разным типам сервисов, 
    рассчитывает покрытие, делает clip и сохраняет результаты.

    :param matrix: pandas.DataFrame — матрица соседства
    :param combined_service: GeoDataFrame — объединённый слой с сервисами
    :param buildings: GeoDataFrame — здания с населением
    :param output_path: str — путь к директории, куда будут сохранены выходные файлы
    :return: кортеж GeoDataFrame: (school, kindergarten, polyclinic)
    """

    # --- Подготовка зданий ---
    adjacency_matrix = matrix
    cleaned_buildings = balanced_buildings.copy()
    combined_crs = combined_service.crs
    projected_crs = "EPSG:32637"  # UTM зона 37N (для Ярославля)

    adjacency_matrix.index = adjacency_matrix.index.astype(int)
    adjacency_matrix.columns = adjacency_matrix.columns.astype(int)
    cleaned_buildings.index = cleaned_buildings.index.astype(int)
    cleaned_buildings["demand"] = cleaned_buildings["population"]
    cleaned_buildings = cleaned_buildings.dropna(subset=["demand"]).copy()
    cleaned_buildings = cleaned_buildings.assign(building_index=range(len(cleaned_buildings)))

    os.makedirs(output_path, exist_ok=True)

    # --- Обработка по каждому типу сервиса ---
    for service_type in combined_service["type"].unique():
        print(f"\n🔧 Обработка типа: {service_type}")

        services = combined_service[combined_service["type"] == service_type].copy()
        services = services.dropna(subset=["buffer_zone"])

        if services.empty:
            print(f"⚠️ Пропущено: нет валидных сервисов типа {service_type}")
            continue

        services = services.to_crs(projected_crs)
        services["adjusted_buffer"] = services["buffer_zone"] * 1.2
        services["geometry"] = services.geometry.buffer(services["adjusted_buffer"])
        services = services.to_crs(combined_crs)

        if "non_living_area" in services.columns:
            services["capacity"] = services["non_living_area"]
        services["demand"] = services["capacity"]

        buffer_threshold = int(services["adjusted_buffer"].mean()) // 50
        print(f"📏 Threshold: {buffer_threshold}")

        build_prov, services_prov, links_prov = get_service_provision(
            buildings=cleaned_buildings,
            services=services,
            adjacency_matrix=adjacency_matrix,
            threshold=buffer_threshold
        )

        print(f"🏥 Сервисов до clip: {len(services_prov)}")

        to_clip_gdf = build_prov.copy().to_crs(projected_crs)
        to_clip_gdf["geometry"] = to_clip_gdf.geometry.buffer(int(services["adjusted_buffer"].mean()))
        to_clip_gdf = to_clip_gdf.to_crs(combined_crs)

        build_prov_clipped, services_prov_clipped, links_prov_clipped = clip_provision(
            build_prov, services_prov, links_prov, to_clip_gdf
        )

        print(f"✂️ Сервисов после clip: {len(services_prov_clipped)}")

        services_file = os.path.join(output_path, f"{service_type}_services_prov_CLIPPED.geojson")
        services_prov_clipped.to_file(services_file, driver="GeoJSON")
        print(f"✅ Сохранено: {services_file}")

        clipped_proj = services_prov_clipped.to_crs(projected_crs)
        centroids = clipped_proj.copy()
        centroids["geometry"] = centroids.geometry.centroid
        centroids = centroids.to_crs(combined_crs)

        centroid_file = os.path.join(output_path, f"{service_type}_services_centroids_CLIPPED.geojson")
        centroids.to_file(centroid_file, driver="GeoJSON")
        print(f"📍 Центроиды сохранены: {centroid_file}")

    # --- Загрузка центроидов для ключевых типов ---
    service_types = ["school", "kindergarten", "polyclinic"]
    centroid_vars = {}

    for service_type in service_types:
        centroid_file = os.path.join(output_path, f"{service_type}_services_centroids_CLIPPED.geojson")

        if os.path.exists(centroid_file):
            gdf = gpd.read_file(centroid_file)
            centroid_vars[service_type] = gdf
            print(f"📥 Загружено: {service_type} — {len(gdf)} объектов")
        else:
            print(f"⚠️ Не найден файл для: {service_type}")

    return (
        centroid_vars.get("school"),
        centroid_vars.get("kindergarten"),
        centroid_vars.get("polyclinic")
    )
