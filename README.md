# Precios de Gasolineras en España

Repositorio para obtener los precios actualizados de **todas las gasolineras** de España en el momento de la ejecución.

## Características

- Obtiene datos de la **API oficial** del Ministerio para la Transición Ecológica y el Reto Demográfico (MITECO) / Geoportal de Gasolineras.
- Extrae específicamente:
  - **Gasolina 95 E5**
  - **Gasóleo A** (diésel normal)
- Guarda los resultados en un archivo CSV con fecha y hora de ejecución.
- En cada ejecución reescribe `data/latest.csv`, la foto que lee el mapa.
- Mapa interactivo (Streamlit + OpenStreetMap) con filtro entre gasolina 95 y diésel.
- Diseñado para ejecutarse **todos los días**.

## Plan de desarrollo
Ver el documento [PLAN.md](PLAN.md) para la hoja de ruta de la interfaz gráfica (mapa interactivo con Streamlit).

## Fuente de datos

- Endpoint: `https://energia.serviciosmin.gob.es/ServiciosRestCarburantes/PreciosCarburantes/EstacionesTerrestres/`
  (alternativa estable a la URL principal de sedeaplicaciones.minetur.gob.es)
- Datos públicos y de libre reutilización.
- Los precios se actualizan con frecuencia (aproximadamente cada media hora según la disponibilidad de las estaciones).

## Requisitos

- Python 3.8+
- Dependencias:

```bash
pip install -r requirements.txt
```

## Uso

Ejecutar el script:

```bash
python gasolineras.py
```

El script descargará los datos, procesará los precios de gasolina 95 y diésel, y generará dos CSV en `data/`:

```
precios_gasolineras_YYYYMMDD_HHMMSS.csv
latest.csv
```

`latest.csv` se sustituye en cada ejecución. El histórico con fecha se conserva al lado.

## Mapa

La aplicación no consulta la API: solo abre `data/latest.csv`. Actualiza los precios y luego arranca el mapa:

```bash
python gasolineras.py
streamlit run app.py
```

En la barra lateral se elige el combustible (Gasolina 95 o Diésel) y, si hace falta, la provincia. El mapa usa OpenStreetMap y agrupa las estaciones; al acercar el zoom cada marca muestra el precio. El color va del verde (más barato dentro del filtro) al rojo (más caro). El popup incluye rótulo, dirección, localidad, provincia, horario y los dos precios.

## Ejecución diaria

### Opción 1: Cron (Linux / macOS)

Añadir al crontab (`crontab -e`) para ejecutar todos los días a las 8:00:

```cron
0 8 * * * cd /ruta/al/repositorio && /usr/bin/python3 gasolineras.py >> logs/ejecucion.log 2>&1
```

### Opción 2: GitHub Actions

Se puede configurar un workflow que se ejecute diariamente y suba los CSV generados (o los almacene como artifacts).

### Opción 3: Task Scheduler (Windows)

Crear una tarea programada que ejecute el script diariamente.

## Estructura de los datos CSV

Cada fila representa una estación de servicio con al menos precio de gasolina 95 o diésel:

| Campo | Descripción |
|-------|-------------|
| id | Identificador de la estación |
| rotulo | Marca / rótulo |
| direccion | Dirección |
| localidad | Localidad |
| municipio | Municipio |
| provincia | Provincia |
| cp | Código postal |
| latitud | Latitud |
| longitud | Longitud |
| horario | Horario de apertura |
| tipo_venta | Tipo de venta (P = público) |
| margen | Margen de la vía |
| gasolina_95 | Precio Gasolina 95 E5 (€/litro) |
| diesel | Precio Gasóleo A (€/litro) |
| fecha_api | Fecha informada por la API |
| fecha_descarga | Fecha y hora de descarga |

## Notas

- Los precios vienen en formato español (coma como separador decimal) y se convierten a float.
- Si la API trae latitud y longitud intercambiadas, el script las corrige cuando el par solo encaja al revés. Las coordenadas que no caen en España (península, Baleares, Canarias, Ceuta y Melilla) no salen en el mapa.
- Solo se guardan estaciones que tienen al menos uno de los dos precios solicitados.
- El volumen de datos es elevado (más de 11.000 estaciones), por lo que la descarga puede tardar unos segundos.

## Licencia de los datos

Los datos proceden del sector público español y pueden reutilizarse conforme a la Ley 37/2007 de reutilización de la información del sector público.
