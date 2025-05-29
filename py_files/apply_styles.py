# apply_styles.py
import geopandas as gpd
import folium

# Определяем словарь для преобразования значений в тексты и цвета
model_mapping = {
    None: {'label': 'no model', 'color': 'lightgray'},
    'central': {'label': 'central', 'color': 'pink'},
    'medium': {'label': 'medium', 'color': 'lightblue'},
    'low_rise': {'label': 'low_rise', 'color': 'orange'}
}

# Функция для получения метки и цвета из словаря
def get_label_and_color(value):
    return model_mapping.get(value, {'label': 'no model', 'color': 'lightgray'})

# Функция для применения стилей
def apply_styles(zones):
    # Применяем к столбцу city_model
    zones['label_and_color'] = zones['city_model'].apply(lambda x: get_label_and_color(x))
    zones['label'] = zones['label_and_color'].apply(lambda x: x['label'])
    zones['color'] = zones['label_and_color'].apply(lambda x: x['color'])
    
    return zones

# Функция для отображения карты
def create_map(zones):
    # Создаем карту с использованием geopandas.explore
    m_1 = zones.explore(
        column='label',  # Столбец для отображения текстовых меток
        color=zones['color'],  # Используем кастомные цвета
        legend=True,  # Включаем легенду
        legend_kwds={
            'title': 'Модели городской застройки. Присвоение атрибутов',  # Заголовок легенды
            'labels': [model_mapping[key]['label'] for key in model_mapping if model_mapping[key]['label'] != 'no model'],  # Исключаем 'no model'
            'colors': [model_mapping[key]['color'] for key in model_mapping if model_mapping[key]['label'] != 'no model']  # Цвета для каждой категории
        },
        tiles='CartoDB positron',  # Фоновая карта
        style_kwds={'fillOpacity': 0.5, 'weight': 0.5}  # Стили для заливки и обводки
    )
    
    # Возвращаем карту для отображения
    return m_1
