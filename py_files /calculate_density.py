import geopandas as gpd
import pandas as pd
from IPython.display import display

def calculate_density(living_zones: gpd.GeoDataFrame, crs_epsg: int = 32637) -> gpd.GeoDataFrame:
    """
    Расчёт плотности населения и дефицита плотности для жилых зон.
    """

    if not isinstance(living_zones, gpd.GeoDataFrame):
        raise TypeError("Аргумент living_zones должен быть GeoDataFrame.")

    # Установка или преобразование CRS
    if living_zones.crs is None:
        print(f"[INFO] CRS не задан. Устанавливаю EPSG:4326 и преобразую в {crs_epsg}.")
        living_zones = living_zones.set_crs(epsg=4326)

    if not living_zones.crs.is_projected or living_zones.crs.to_epsg() != crs_epsg:
        print(f"[INFO] Преобразую CRS в EPSG:{crs_epsg}.")
        living_zones = living_zones.to_crs(epsg=crs_epsg)

    print(f"[DEBUG] Текущая CRS: {living_zones.crs}")

    # Лимиты плотности (в чел/м²)
    density_limits = {
        "low_rise": 0.008,   # 80 чел/га
        "medium":   0.035,   # 350 чел/га
        "central":  0.045    # 450 чел/га
    }

    living_zones["limit_density"] = living_zones["city_model"].map(density_limits)
    living_zones["area_zone"] = living_zones.geometry.area
    living_zones["density_population"] = living_zones["sum_population"] / living_zones["area_zone"]
    living_zones["deficit_density"] = living_zones["limit_density"] - living_zones["density_population"]

    display(living_zones[[
        "city_model", "area_zone", "sum_population", "density_population",
        "limit_density", "deficit_density"
    ]].head())

    return living_zones
