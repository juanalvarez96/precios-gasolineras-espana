#!/usr/bin/env python3
"""
Script para obtener los precios de todas las gasolineras de España
desde la API oficial del Ministerio (MITECO / Geoportal de Gasolineras).

Obtiene precios de Gasolina 95 E5 y Gasóleo A (diésel normal)
y los guarda en un CSV con la fecha de ejecución y en data/latest.csv,
que es el archivo que lee la aplicación.
"""

import requests
import json
import csv
import os
from datetime import datetime
from typing import List, Dict, Optional

# URL de la API oficial (alternativa que funciona de forma más estable)
API_URL = "https://energia.serviciosmin.gob.es/ServiciosRestCarburantes/PreciosCarburantes/EstacionesTerrestres/"

# Campos de interés
PRICE_FIELDS = {
    "gasolina_95": "Precio Gasolina 95 E5",
    "diesel": "Precio Gasoleo A",
}

STATION_FIELDS = [
    "IDEESS",
    "Rótulo",
    "Dirección",
    "Localidad",
    "Municipio",
    "Provincia",
    "C.P.",
    "Latitud",
    "Longitud (WGS84)",
    "Horario",
    "Tipo Venta",
    "Margen",
]

# Orden estable del CSV. Lo comparten el archivo con timestamp y data/latest.csv.
CSV_FIELDS = [
    "id",
    "rotulo",
    "direccion",
    "localidad",
    "municipio",
    "provincia",
    "cp",
    "latitud",
    "longitud",
    "horario",
    "tipo_venta",
    "margen",
    "gasolina_95",
    "diesel",
    "fecha_api",
    "fecha_descarga",
]

LATEST_CSV_NAME = "latest.csv"

# Caja que cubre península, Baleares, Canarias, Ceuta y Melilla.
# Latitud y longitud no se solapan, así que un par cruzado se detecta sin ambigüedad.
LAT_RANGE = (27.0, 44.8)
LON_RANGE = (-19.0, 5.0)


def _in_spain(lat: float, lon: float) -> bool:
    return LAT_RANGE[0] <= lat <= LAT_RANGE[1] and LON_RANGE[0] <= lon <= LON_RANGE[1]


def parse_coord(value: str) -> Optional[float]:
    if value is None:
        return None
    text = str(value).strip().replace(",", ".")
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def normalize_coordinates(
    lat: Optional[float], lon: Optional[float]
) -> Optional[tuple[float, float]]:
    """Devuelve latitud y longitud dentro de España.

    La API a veces trae los ejes intercambiados. Si el par solo encaja al revés,
    se corrige. Si no cae en la caja ni al derecho ni al revés, devuelve None.
    """
    if lat is None or lon is None:
        return None
    if _in_spain(lat, lon):
        return lat, lon
    if _in_spain(lon, lat):
        return lon, lat
    return None


def parse_price(price_str: str) -> Optional[float]:
    """Convierte el precio de formato español (1,234) a float."""
    if not price_str or price_str.strip() == "":
        return None
    try:
        return float(price_str.replace(",", "."))
    except ValueError:
        return None


def fetch_stations() -> tuple[List[Dict], str]:
    """Descarga la lista completa de estaciones con precios."""
    print(f"Descargando datos desde {API_URL}...")
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
    }
    response = requests.get(API_URL, headers=headers, timeout=180)
    response.raise_for_status()
    data = response.json()

    fecha = data.get("Fecha", "Desconocida")
    stations = data.get("ListaEESSPrecio", [])
    print(f"Fecha de los datos: {fecha}")
    print(f"Número de estaciones: {len(stations)}")
    return stations, fecha


def process_stations(stations: List[Dict]) -> List[Dict]:
    """Procesa las estaciones extrayendo solo gasolina 95 y diésel."""
    processed = []
    for station in stations:
        row = {
            "id": station.get("IDEESS", ""),
            "rotulo": station.get("Rótulo", ""),
            "direccion": station.get("Dirección", ""),
            "localidad": station.get("Localidad", ""),
            "municipio": station.get("Municipio", ""),
            "provincia": station.get("Provincia", ""),
            "cp": station.get("C.P.", ""),
            "horario": station.get("Horario", ""),
            "tipo_venta": station.get("Tipo Venta", ""),
            "margen": station.get("Margen", ""),
            "gasolina_95": parse_price(station.get(PRICE_FIELDS["gasolina_95"], "")),
            "diesel": parse_price(station.get(PRICE_FIELDS["diesel"], "")),
        }
        fixed = normalize_coordinates(
            parse_coord(station.get("Latitud", "")),
            parse_coord(station.get("Longitud (WGS84)", "")),
        )
        if fixed is None:
            row["latitud"] = (station.get("Latitud") or "").replace(",", ".")
            row["longitud"] = (station.get("Longitud (WGS84)") or "").replace(",", ".")
        else:
            row["latitud"] = f"{fixed[0]:.6f}"
            row["longitud"] = f"{fixed[1]:.6f}"
        # Solo incluir estaciones que tengan al menos uno de los dos precios
        if row["gasolina_95"] is not None or row["diesel"] is not None:
            processed.append(row)
    return processed


def _csv_cell(key: str, value):
    """Formatea una celda. Los precios salen siempre con 3 decimales."""
    if value is None:
        return ""
    if key in ("gasolina_95", "diesel") and isinstance(value, (int, float)):
        return f"{value:.3f}"
    return value


def _write_csv(filepath: str, rows: List[Dict]) -> None:
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: _csv_cell(key, row.get(key)) for key in CSV_FIELDS})


def save_to_csv(stations: List[Dict], fecha_api: str, output_dir: str = "data") -> str:
    """Guarda un CSV con timestamp y actualiza data/latest.csv con las mismas filas.

    latest.csv es la foto fija que lee la aplicación. Se reescribe en cada
    ejecución, también cuando no hay estaciones, para no dejar datos viejos.
    No modifica los diccionarios de entrada.
    """
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now()
    downloaded_at = now.isoformat(timespec="seconds")
    filename = f"precios_gasolineras_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(output_dir, filename)
    latest_path = os.path.join(output_dir, LATEST_CSV_NAME)

    rows = []
    for station in stations:
        row = dict(station)
        row["fecha_api"] = fecha_api
        row["fecha_descarga"] = downloaded_at
        rows.append(row)

    _write_csv(filepath, rows)
    _write_csv(latest_path, rows)

    print(f"Datos guardados en: {filepath}")
    print(f"Snapshot actualizado: {latest_path}")
    print(f"Estaciones con precios de 95 o diésel: {len(stations)}")
    return filepath


def main():
    try:
        stations, fecha_api = fetch_stations()
        processed = process_stations(stations)
        save_to_csv(processed, fecha_api)
        print("Proceso completado correctamente.")
    except Exception as e:
        print(f"Error durante la ejecución: {e}")
        raise


if __name__ == "__main__":
    main()
