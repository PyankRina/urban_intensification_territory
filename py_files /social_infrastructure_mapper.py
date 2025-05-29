import geopandas as gpd
import pandas as pd


def process_and_buffer(gdf):
    """
    Подготовка слоя учреждений: переименование колонок, перевод СК и создание буферов.
    """
    gdf = gdf.rename(columns={
        'carried_capacity_without': 'free_places',
        'carried_capacity_within': 'employed_places'
    }).to_crs(32637)

    required = ['id_service', 'free_places', 'employed_places', 'buffer_zone']
    for col in required:
        if col not in gdf.columns:
            raise ValueError(f"Отсутствует обязательный столбец: {col}")

    gdf['geometry'] = gdf.buffer(gdf['buffer_zone'] * 1.2)
    return gdf[['id_service', 'free_places', 'employed_places', 'geometry']].to_crs(32637)


def intersect_and_aggregate(buffer_gdf, zones_gdf, label):
    """
    Определяет учреждения, буфер которых пересекается с жилыми зонами,
    и выбирает учреждение с максимальной площадью пересечения для каждой зоны.
    """
    buffer_gdf = buffer_gdf.to_crs(3857)
    zones_gdf = zones_gdf.to_crs(3857)

    intersected = gpd.overlay(buffer_gdf, zones_gdf, how='intersection')
    intersected['intersection_area'] = intersected.area

    intersected['centroid'] = intersected.centroid
    joined = gpd.sjoin(intersected.set_geometry('centroid'), zones_gdf, predicate='within')

    idx_max_area = joined.groupby('index_right')['intersection_area'].idxmax()
    selected = joined.loc[idx_max_area]

    result = zones_gdf.reset_index().merge(
        selected[['index_right', 'free_places', 'employed_places', 'id_service']],
        left_on='index', right_on='index_right', how='left'
    ).drop(columns=['index_right'])

    result.rename(columns={
        'free_places': f'{label}_free_places',
        'employed_places': f'{label}_employed_places',
        'id_service': f'{label}_id_service'
    }, inplace=True)

    return result[
        [f'{label}_free_places', f'{label}_employed_places', f'{label}_id_service']
    ]


def process_services(zones, kindergarten, school, polyclinic):
    """
    Основной цикл обработки: буферизация, пересечение и агрегирование для всех типов учреждений.
    Возвращает GeoDataFrame с информацией по свободным/занятым местам в пределах жилых зон.
    """
    zones_out = zones.copy()

    layers = {
        'kindergarten': kindergarten,
        'school': school,
        'polyclinic': polyclinic
    }

    for label, gdf in layers.items():
        print(f"🔹 Обработка слоя: {label}")
        buffered = process_and_buffer(gdf)
        agg = intersect_and_aggregate(buffered, zones, label)

        # Инициализация колонок по умолчанию
        for col in [f'{label}_free_places', f'{label}_employed_places', f'{label}_id_service']:
            zones_out[col] = None if 'id_service' in col else pd.NA

        living_mask = zones_out['is_living_zones'] == True

        # Заполняем значения только для жилых зон
        zones_out.loc[living_mask, f'{label}_free_places'] = agg.loc[living_mask, f'{label}_free_places']
        zones_out.loc[living_mask, f'{label}_employed_places'] = agg.loc[living_mask, f'{label}_employed_places']
        zones_out.loc[living_mask, f'{label}_id_service'] = agg.loc[living_mask, f'{label}_id_service']

        # Остальным проставляем нули и None
        zones_out[f'{label}_free_places'] = zones_out[f'{label}_free_places'].fillna(0)
        zones_out[f'{label}_employed_places'] = zones_out[f'{label}_employed_places'].fillna(0)
        zones_out[f'{label}_id_service'] = zones_out[f'{label}_id_service'].replace('', None)

    living_zones = zones_out[zones_out["is_living_zones"] == True].copy()
    return living_zones
