#!/usr/bin/env python3
"""
Script para obtener los precios de todas las gasolineras de España
desde la API oficial del Ministerio (MITECO / Geoportal de Gasolineras).

Obtiene precios de Gasolina 95 E5 y Gasóleo A (diésel normal)
y los guarda en un archivo CSV con la fecha de ejecución.
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
            "latitud": station.get("Latitud", "").replace(",", ".")
            if station.get("Latitud")
            else "",
            "longitud": station.get("Longitud (WGS84)", "").replace(",", ".")
            if station.get("Longitud (WGS84)")
            else "",
            "horario": station.get("Horario", ""),
            "tipo_venta": station.get("Tipo Venta", ""),
            "margen": station.get("Margen", ""),
            "gasolina_95": parse_price(station.get(PRICE_FIELDS["gasolina_95"], "")),
            "diesel": parse_price(station.get(PRICE_FIELDS["diesel"], "")),
        }
        # Solo incluir estaciones que tengan al menos uno de los dos precios
        if row["gasolina_95"] is not None or row["diesel"] is not None:
            processed.append(row)
    return processed


def save_to_csv(stations: List[Dict], fecha_api: str, output_dir: str = "data") -> str:
    """Guarda los datos en un CSV con timestamp."""
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now()
    filename = f"precios_gasolineras_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    filepath = os.path.join(output_dir, filename)

    if not stations:
        print("No hay estaciones para guardar.")
        return filepath

    fieldnames = list(stations[0].keys()) + ["fecha_api", "fecha_descarga"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for station in stations:
            station["fecha_api"] = fecha_api
            station["fecha_descarga"] = now.isoformat()
            writer.writerow(station)

    print(f"Datos guardados en: {filepath}")
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
