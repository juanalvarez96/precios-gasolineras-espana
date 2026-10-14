#!/usr/bin/env python3
"""Mapa de precios de gasolineras.

Lee solo data/latest.csv. La descarga sigue siendo gasolineras.py.
"""

import html
import locale
from pathlib import Path

import folium
import pandas as pd
import streamlit as st
from folium.plugins import FastMarkerCluster
from streamlit_folium import st_folium

from gasolineras import LAT_RANGE, LON_RANGE

DATA_PATH = Path(__file__).resolve().parent / "data" / "latest.csv"

FUELS = (
    ("Gasolina 95", "gasolina_95"),
    ("Diésel", "diesel"),
)
FUEL_LABELS = {
    "gasolina_95": "Gasolina 95",
    "diesel": "Diésel",
}

# Vista inicial en la península. Canarias y Baleares quedan a un clic
# porque, si no, el encuadre de todo el país las deja en el borde.
ZONES = {
    "Península": (40.2, -3.7, 6),
    "Baleares": (39.55, 2.95, 8),
    "Canarias": (28.35, -16.0, 7),
    "Ceuta": (35.889, -5.316, 13),
    "Melilla": (35.292, -2.938, 13),
}

MARKER_CALLBACK = """
function (row) {
    var icon = L.divIcon({
        className: "gas-divicon",
        html: '<div class="gas-pin" style="--c:' + row[2] + '">⛽ ' + row[3] + '</div>',
        iconSize: [76, 24],
        iconAnchor: [38, 24],
        popupAnchor: [0, -20]
    });
    var marker = L.marker(new L.LatLng(row[0], row[1]), {icon: icon});
    marker.bindTooltip(row[3] + " €/L", {direction: "top", offset: [0, -16]});
    marker.bindPopup(row[4], {maxWidth: 320});
    return marker;
}
"""

MAP_CSS = """
<style>
.leaflet-div-icon.gas-divicon { background: transparent; border: none; }
.gas-pin {
    box-sizing: border-box;
    display: inline-flex;
    align-items: center;
    gap: 3px;
    padding: 1px 6px 1px 4px;
    border-radius: 999px;
    background: #fff;
    border: 2px solid var(--c, #444);
    color: #1c1917;
    font: 700 11px/1.2 ui-sans-serif, system-ui, sans-serif;
    box-shadow: 0 1px 2px rgba(0,0,0,.35);
    white-space: nowrap;
}
.gas-popup { font-family: ui-sans-serif, system-ui, sans-serif; font-size: 13px; line-height: 1.35; min-width: 210px; }
.gas-popup h4 { margin: 0 0 4px; font-size: 15px; }
.gas-popup .addr { color: #444; margin-bottom: 8px; }
.gas-popup .hours { color: #555; margin-top: 8px; }
</style>
"""


def format_euro(value) -> str:
    if value is None or value == "":
        return "—"
    try:
        if pd.isna(value):
            return "—"
        number = float(value)
    except (TypeError, ValueError):
        return "—"
    return f"{number:.3f}".replace(".", ",") + " €"


def format_count(value: int) -> str:
    return f"{value:,}".replace(",", ".")


@st.cache_data(max_entries=4, show_spinner=False)
def load_stations(path_str: str, mtime_ns: int) -> pd.DataFrame:
    del mtime_ns  # invalida la caché cuando data/latest.csv cambia
    path = Path(path_str)
    df = pd.read_csv(path, dtype={"cp": "string"})
    for column in ("latitud", "longitud", "gasolina_95", "diesel"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    for column in ("rotulo", "direccion", "localidad", "provincia", "horario", "fecha_api", "fecha_descarga"):
        if column not in df.columns:
            df[column] = ""
        df[column] = df[column].fillna("").astype(str)
    return df


def valid_coordinates(df: pd.DataFrame) -> pd.DataFrame:
    """Se queda con coordenadas en España y corrige las que vienen cruzadas."""
    out = df.copy()
    lat = out["latitud"]
    lon = out["longitud"]
    good = lat.between(*LAT_RANGE) & lon.between(*LON_RANGE)
    swapped = ~good & lon.between(*LAT_RANGE) & lat.between(*LON_RANGE)
    out.loc[swapped, "latitud"] = lon[swapped].to_numpy()
    out.loc[swapped, "longitud"] = lat[swapped].to_numpy()
    return out.loc[good | swapped].copy()


def color_anchors(prices: pd.Series) -> tuple[float, float]:
    if prices.empty:
        return 0.0, 1.0
    if len(prices) < 20:
        return float(prices.min()), float(prices.max())
    low, high = prices.quantile([0.05, 0.95])
    return float(low), float(high)


def price_color(price: float, low: float, high: float) -> str:
    """Verde si está entre lo más barato del filtro, rojo si está entre lo más caro."""
    if high <= low:
        ratio = 0.5
    else:
        ratio = (price - low) / (high - low)
    ratio = max(0.0, min(1.0, ratio))
    # #2ea043 -> #d69e2e -> #c4302b
    if ratio < 0.5:
        mix = ratio / 0.5
        red, green, blue = 46, 160, 67
        target = (214, 158, 46)
    else:
        mix = (ratio - 0.5) / 0.5
        red, green, blue = 214, 158, 46
        target = (196, 48, 43)
    red = int(red + (target[0] - red) * mix)
    green = int(green + (target[1] - green) * mix)
    blue = int(blue + (target[2] - blue) * mix)
    return f"#{red:02x}{green:02x}{blue:02x}"


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


def popup_html(row, selected_column: str) -> str:
    title = html.escape(_text(row.get("rotulo")) or "Sin rótulo")
    address = html.escape(_text(row.get("direccion")) or "Dirección no indicada")
    place = " · ".join(
        part
        for part in (
            html.escape(_text(row.get("localidad"))),
            html.escape(_text(row.get("provincia"))),
        )
        if part
    )
    hours = html.escape(_text(row.get("horario")))
    if len(hours) > 280:
        hours = hours[:277] + "..."

    lines = []
    for column, label in FUEL_LABELS.items():
        weight = "700" if column == selected_column else "400"
        lines.append(
            f'<div style="font-weight:{weight}">{html.escape(label)}: {format_euro(row.get(column))}</div>'
        )
    hours_html = f'<div class="hours">{hours}</div>' if hours else ""
    return (
        '<div class="gas-popup">'
        f"<h4>{title}</h4>"
        f'<div class="addr">{address}<br>{place}</div>'
        + "".join(lines)
        + hours_html
        + "</div>"
    )


@st.cache_data(max_entries=8, show_spinner=False)
def marker_rows(stations: pd.DataFrame, fuel_column: str) -> list[list]:
    low, high = color_anchors(stations[fuel_column])
    rows = []
    for record in stations.to_dict("records"):
        price = float(record[fuel_column])
        rows.append(
            [
                float(record["latitud"]),
                float(record["longitud"]),
                price_color(price, low, high),
                f"{price:.3f}".replace(".", ","),
                popup_html(record, fuel_column),
            ]
        )
    return rows


def build_map(
    stations: pd.DataFrame,
    fuel_column: str,
    center: tuple[float, float] | None,
    zoom: int | None,
) -> folium.Map:
    if center is None:
        location = [40.2, -3.7]
        zoom_start = 6
    else:
        location = [center[0], center[1]]
        zoom_start = zoom or 6

    figure = folium.Map(
        location=location,
        zoom_start=zoom_start,
        tiles="OpenStreetMap",
        control_scale=True,
        min_zoom=5,
        max_zoom=18,
    )
    figure.get_root().header.add_child(folium.Element(MAP_CSS))

    if not stations.empty:
        FastMarkerCluster(
            marker_rows(stations, fuel_column),
            callback=MARKER_CALLBACK,
            name="Gasolineras",
            options={
                "disableClusteringAtZoom": 12,
                "spiderfyOnMaxZoom": True,
                "showCoverageOnHover": False,
                "maxClusterRadius": 48,
                "chunkedLoading": True,
            },
        ).add_to(figure)
        if center is None:
            figure.fit_bounds(
                [
                    [float(stations["latitud"].min()), float(stations["longitud"].min())],
                    [float(stations["latitud"].max()), float(stations["longitud"].max())],
                ],
                max_zoom=14,
            )
    return figure


def sorted_provinces(names: pd.Series) -> list[str]:
    values = sorted({str(name).strip() for name in names if str(name).strip()})
    try:
        locale.setlocale(locale.LC_COLLATE, "es_ES.UTF-8")
        return sorted(values, key=locale.strxfrm)
    except locale.Error:
        return values


def render(df: pd.DataFrame) -> None:
    missing = [column for column in ("latitud", "longitud", "gasolina_95", "diesel", "provincia") if column not in df.columns]
    if missing:
        st.error(
            "A `data/latest.csv` le faltan columnas: "
            + ", ".join(missing)
            + ". Vuelve a ejecutar `python gasolineras.py`."
        )
        return

    located = valid_coordinates(df)
    dropped = len(df) - len(located)
    fuel_labels = [label for label, _column in FUELS]

    with st.sidebar:
        st.header("Filtros")
        fuel_label = st.segmented_control(
            "Combustible",
            fuel_labels,
            default=fuel_labels[0],
            required=True,
            width="stretch",
            key="combustible",
        )
        fuel_column = dict(FUELS)[fuel_label]
        provinces = sorted_provinces(located["provincia"])
        province = st.selectbox("Provincia", ["Todas", *provinces], key="provincia")
        zone = "Península"
        if province == "Todas":
            zone = st.segmented_control(
                "Zona del mapa",
                list(ZONES),
                default="Península",
                required=True,
                width="stretch",
                wrap=True,
                key="zona",
            )
        st.divider()
        st.caption(
            "Verde es de lo más barato del filtro y rojo de lo más caro "
            "(percentil 5 a 95). Acerca el mapa para leer el precio de cada estación."
        )
        st.caption("El icono es genérico. Los logos de marca quedan para más adelante.")

    scoped = located if province == "Todas" else located[located["provincia"] == province]
    visible = scoped.dropna(subset=[fuel_column])
    hidden_without_price = len(scoped) - len(visible)

    fecha_api = ""
    fecha_descarga = ""
    if "fecha_api" in df.columns and not df.empty:
        fecha_api = _text(df["fecha_api"].iloc[0])
    if "fecha_descarga" in df.columns and not df.empty:
        fecha_descarga = _text(df["fecha_descarga"].iloc[0])

    st.title(":material/local_gas_station: Precios de gasolineras")
    caption_bits = ["Gasolina 95 y diésel. Fuente: Ministerio para la Transición Ecológica."]
    if fecha_api:
        caption_bits.append(f"Datos de la API: {fecha_api}.")
    if fecha_descarga:
        caption_bits.append(f"Descarga: {fecha_descarga}.")
    st.caption(" ".join(caption_bits))

    if visible.empty:
        st.warning(f"No hay estaciones con precio de {fuel_label} para este filtro.")
        return

    prices = visible[fuel_column]
    cheap, typical, expensive = prices.min(), prices.median(), prices.max()
    with st.container(horizontal=True):
        st.metric("Estaciones", format_count(len(visible)), border=True)
        st.metric("Más barato", format_euro(cheap), border=True)
        st.metric("Mediana", format_euro(typical), border=True)
        st.metric("Más caro", format_euro(expensive), border=True)

    notes = []
    if hidden_without_price:
        notes.append(
            f"{format_count(hidden_without_price)} estaciones sin precio de {fuel_label} no se muestran."
        )
    if dropped:
        notes.append(f"{format_count(dropped)} filas sin coordenadas válidas se han dejado fuera.")
    if notes:
        st.caption(" ".join(notes))

    with st.spinner("Preparando el mapa…"):
        if province == "Todas":
            lat, lon, zoom = ZONES[zone]
            gas_map = build_map(visible, fuel_column, (lat, lon), zoom)
        else:
            gas_map = build_map(visible, fuel_column, None, None)

    st_folium(
        gas_map,
        height=700,
        use_container_width=True,
        returned_objects=[],
        key=f"mapa-{fuel_column}-{province}-{zone}-{len(visible)}",
    )

    st.subheader(f"Las más baratas · {fuel_label}")
    table = visible.sort_values(fuel_column, ascending=True).head(25).copy()
    table["Gasolina 95"] = table["gasolina_95"].map(format_euro)
    table["Diésel"] = table["diesel"].map(format_euro)
    table = table.rename(
        columns={
            "rotulo": "Rótulo",
            "localidad": "Localidad",
            "provincia": "Provincia",
            "direccion": "Dirección",
            "horario": "Horario",
        }
    )
    st.caption(f"25 precios más bajos de las {format_count(len(visible))} estaciones del filtro.")
    st.dataframe(
        table[["Rótulo", "Localidad", "Provincia", "Dirección", "Gasolina 95", "Diésel", "Horario"]],
        hide_index=True,
        height=420,
        alt="Las 25 gasolineras más baratas del filtro",
    )


st.set_page_config(
    page_title="Precios de gasolineras",
    page_icon="⛽",
    layout="wide",
)
if not DATA_PATH.is_file():
    st.title(":material/local_gas_station: Precios de gasolineras")
    st.error(
        "Desde la raíz del repositorio ejecuta `python gasolineras.py` y vuelve a abrir esta página.",
        title="Falta data/latest.csv",
    )
else:
    try:
        stations = load_stations(str(DATA_PATH), DATA_PATH.stat().st_mtime_ns)
    except Exception as exc:
        st.title(":material/local_gas_station: Precios de gasolineras")
        st.error(str(exc), title="No se ha podido leer data/latest.csv")
    else:
        render(stations)
