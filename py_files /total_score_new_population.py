# total_score_new_population.py

import numpy as np
import pandas as pd
import geopandas as gpd
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.preprocessing import MinMaxScaler
from sklearn.cluster import KMeans

def analyze_zones(living_zones: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    zones_0 = living_zones.copy()

    core_cols = ["new_population", "deficit_density", "difference_from_normative"]
    extra_cols = ["kindergarten_free_places", "school_employed_places", "polyclinic_free_places"]

    zones_0[core_cols + extra_cols] = zones_0[core_cols + extra_cols].apply(pd.to_numeric, errors="coerce")

    mask = (
        (zones_0["new_population"] > 2) &
        (zones_0["deficit_density"] >= 0) &
        (zones_0["difference_from_normative"] > 0)
    )

    zones_to_score = zones_0[mask].copy()

    scaler = MinMaxScaler()
    for col in core_cols:
        zones_to_score[f"normalized_{col}"] = scaler.fit_transform(zones_to_score[[col]])

    # Кластеризация
    kmeans = KMeans(n_clusters=3, random_state=42)
    zones_to_score["cluster"] = kmeans.fit_predict(zones_to_score[core_cols])

    # Корреляции и веса
    corr_matrix = zones_to_score[core_cols].corr()
    weights = corr_matrix.abs().mean() / corr_matrix.abs().mean().sum()

    # Считаем итоговый балл
    zones_to_score["total_score"] = sum(
        weights[col] * zones_to_score[f"normalized_{col}"] for col in core_cols
    )

    zones_to_score["total_score"] = MinMaxScaler(feature_range=(0, 100)).fit_transform(
        zones_to_score[["total_score"]]
    )

    # Обработка оставшихся зон
    zones_not_to_score = zones_0[~mask].copy()

    missing_cols = [col for col in extra_cols if col not in zones_not_to_score.columns]
    if missing_cols:
        print(f"Отсутствуют следующие колонки: {missing_cols}")

    if not missing_cols:
        zones_not_to_score[extra_cols] = scaler.fit_transform(zones_not_to_score[extra_cols])
        zones_not_to_score["negative_score"] = zones_not_to_score[extra_cols].sum(axis=1)
        zones_not_to_score["negative_score"] = MinMaxScaler(feature_range=(-100, 0)).fit_transform(
            zones_not_to_score[["negative_score"]]
        )
        zones_not_to_score["total_score"] = zones_not_to_score["negative_score"]

    # Объединяем
    zones_0["total_score"] = zones_to_score["total_score"].fillna(0)
    zones_0.update(zones_not_to_score[["total_score"]])

    # Категории
    conditions = [
        (zones_0["total_score"] <= -33),
        (zones_0["total_score"] > -33) & (zones_0["total_score"] <= 33),
        (zones_0["total_score"] > 33),
    ]
    choices = ["низкий потенциал", "средний потенциал", "высокий потенциал"]
    zones_0["score_category"] = np.select(conditions, choices, default="неопределено")

    # Визуализация
    fig, axs = plt.subplots(1, 2, figsize=(15, 5))
    sns.heatmap(corr_matrix, annot=True, cmap="YlGnBu", fmt=".2f", ax=axs[0])
    axs[0].set_title("Корреляционная матрица признаков")
    sns.barplot(x=weights.values, y=weights.index, palette="viridis", ax=axs[1])
    axs[1].set_title("Важность признаков на основе корреляции")
    axs[1].set_xlabel("Вес признака")
    axs[1].set_xlim(0, 1)
    plt.tight_layout()
    plt.show()

    return zones_0

def save_to_geojson(gdf: gpd.GeoDataFrame, filename='processed_zones.geojson'):
    gdf.to_file(filename, driver='GeoJSON')
