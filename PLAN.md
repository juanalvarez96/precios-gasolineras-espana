# Plan de Interfaz Gráfica (Mapa de Gasolineras)

## Objetivo
Crear una aplicación web interactiva que permita visualizar en un mapa todas las gasolineras de España con sus precios, con filtro entre Gasolina 95 y Diésel, usando datos actualizados diariamente.

## Decisión de framework
**Streamlit** (recomendado sobre Gradio)

### Comparativa
| Aspecto | Streamlit | Gradio |
|---------|-----------|--------|
| Mapas interactivos | Excelente (Folium, Pydeck, Plotly) | Limitado |
| Filtros y widgets | Muy natural para datos | Correcto pero menos orientado a dashboards |
| Rendimiento con muchos puntos | Bueno (clustering) | Más pesado |
| Integración con datos diarios | Directa | Similar |

## Arquitectura propuesta

### Datos (ejecución diaria)
- El script `gasolineras.py` sigue ejecutándose diariamente (cron o GitHub Actions).
- Además del CSV con timestamp, el script debe generar/actualizar un archivo fijo:
  - `data/latest.csv`
- La aplicación **solo lee** `data/latest.csv` (no consulta la API en cada visita).

### Interfaz (`app.py`)
- **Sidebar**:
  - Selector de combustible: `Gasolina 95` / `Diesel`
  - (Futuro) Filtros por provincia, rango de precio, marca.
- **Mapa principal**:
  - Proveedor gratuito: **OpenStreetMap** vía Folium + `streamlit-folium` (o Pydeck si se necesita más rendimiento).
  - Muestra solo las estaciones que tienen precio del combustible seleccionado.
  - Cada marcador muestra:
    - Icono de gasolinera (genérico al inicio).
    - Precio del combustible seleccionado (en popup / tooltip / label).
  - Popup con: rótulo, dirección, localidad, provincia, horario, ambos precios.

### Iconos / Logos
- **Fase 1**: Icono genérico de gasolinera (emoji ⛽ o PNG libre) + precio.
- **Fase 2**: Mapping de marcas (`rotulo`) a logos específicos (Repsol, BP, Cepsa, Ballenoil, etc.).

### Rendimiento
- Usar clustering (MarkerCluster de Folium o equivalente en Pydeck) para manejar ~11.000 puntos.
- Posibilidad de filtrar por provincia o viewport del mapa si es necesario.

## Estructura de archivos final
```
app.py                          # Aplicación Streamlit
gasolineras.py                  # Script de descarga diaria (ya existente)
data/latest.csv                 # Snapshot actualizado diariamente
requirements.txt                # Añadir streamlit, streamlit-folium, folium
PLAN.md                         # Este documento
README.md
.github/workflows/daily-prices.yml
```

## Flujo de ejecución diaria
1. Workflow / cron ejecuta `gasolineras.py`.
2. Se genera el CSV con timestamp y se actualiza `data/latest.csv`.
3. La app Streamlit siempre carga `data/latest.csv`.
4. El usuario abre la app, elige el combustible y ve el mapa actualizado.

## Proveedor de mapas
- OpenStreetMap (gratuito, sin API key).
- Implementado con Folium o Pydeck.

## Próximos pasos
1. Hecho. `gasolineras.py` escribe el CSV con timestamp y `data/latest.csv`.
2. Hecho. `app.py` muestra el mapa (Folium, MarkerCluster) y el filtro de combustible.
3. Hecho. `requirements.txt` incluye streamlit, folium y streamlit-folium.
4. Hecho en local con `streamlit run app.py`.
5. Pendiente y opcional: desplegar en Streamlit Cloud. Hace falta cuenta y decidir si `data/latest.csv` se publica; ahora mismo `data/` y `*.csv` están en `.gitignore`.
