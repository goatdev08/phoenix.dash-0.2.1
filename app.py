from __future__ import annotations

import pathlib
import subprocess
from datetime import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide", page_title="Phoenix Team Analyst 🐦‍🔥")

# ==============================================================================
#   0. GESTIÓN DE VERSIÓN DINÁMICA
# ==============================================================================

DEFAULT_VERSION = "0.2.3"
_version_file = pathlib.Path(__file__).with_name("VERSION")
if _version_file.exists():
    APP_VERSION = _version_file.read_text().strip()
else:
    try:
        APP_VERSION = (
            subprocess.check_output(["git", "describe", "--tags"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        APP_VERSION = DEFAULT_VERSION

# ==============================================================================
#   1. DETECCIÓN AUTOMÁTICA DE DISPOSITIVO (ESCRITORIO / MÓVIL)
# ==============================================================================

try:
    from streamlit_javascript import st_javascript

    raw_vw = st_javascript("return window.innerWidth;")
    viewport_width = int(float(raw_vw)) if raw_vw else 1200
except Exception:
    viewport_width = 1200  # Fallback escritorio

is_mobile = viewport_width < 992  # Bootstrap md breakpoint

# ==============================================================================
#   2. CARGA Y NORMALIZACIÓN DE DATOS
# ==============================================================================

RAW_CSV_URL = "https://raw.githubusercontent.com/goatdev08/phoenix.dash/main/archivo.csv"


@st.cache_data(show_spinner="📦 Cargando datos …")
def load_data(path: str | None = None) -> pd.DataFrame:
    """Carga el CSV remoto o local y normaliza columnas."""

    path = path or RAW_CSV_URL
    df = pd.read_csv(path)
    df.columns = [c.strip().replace("/", "").replace(" ", "_") for c in df.columns]

    if "Cat_Prueba" in df.columns:
        df.rename(columns={"Cat_Prueba": "Fase"}, inplace=True)

    phase_map = {
        "PRE-ELIMINAR": "Preliminar",
        "PRELIMINAR": "Preliminar",
        "PRE ELIMINAR": "Preliminar",
        "SEMIFINAL": "Semifinal",
        "SEMI-FINAL": "Semifinal",
        "FINAL": "Final",
    }
    df["Fase"] = df["Fase"].str.upper().str.replace("Ó", "O").map(phase_map).fillna(df["Fase"])
    order_dict = {"Preliminar": 1, "Semifinal": 2, "Final": 3}
    df["Fase_Orden"] = df["Fase"].map(order_dict)

    df["Valor"] = pd.to_numeric(df["Valor"], errors="coerce")
    return df


df = load_data()

# ==============================================================================
#   3. CONSTANTES Y DICCIONARIOS
# ==============================================================================

param_translation: dict[str, str] = {
    "T15 (1)": "Tiempo 15m (1)",
    "# de BRZ 1": "Numero de Brazadas (1)",
    "V1": "Velocidad (1)",
    "T25 (1)": "Tiempo 25m (1)",
    "# de BRZ 2": "Numero de Brazadas (2)",
    "V2": "Velocidad (2)",
    "T15 (2)": "Tiempo 15m (2)",
    "BRZ TOTAL": "Total de Brazadas",
    "V promedio": "Velocidad Promedio",
    "T25 (2)": "Tiempo 25m (2)",
    "DIST sin F": "Distancia sin Flecha",
    "F1": "Flechas (1)",
    "T TOTAL": "Tiempo Total",
    "DIST x BRZ": "Distancia por Brazada",
    "F2": "Flechas (2)",
    "F promedio": "Promedio Metros en Flecha",
}

param_categories = {
    "Tiempo": ["T15 (1)", "T25 (1)", "T15 (2)", "T25 (2)", "T TOTAL"],
    "Brazadas": ["# de BRZ 1", "# de BRZ 2", "BRZ TOTAL", "DIST x BRZ"],
    "Velocidad": ["V1", "V2", "V promedio"],
    "Flechas": ["F1", "F2", "F promedio", "DIST sin F"],
}

# ==============================================================================
#   4. HEADER Y PANEL DE FILTROS
# ==============================================================================

st.title("Phoenix Team Analyst 🐦‍🔥")

with st.sidebar:
    st.markdown("#### Versión de la app")
    st.success(APP_VERSION)

    st.divider()
    st.markdown("#### Filtros")

    sel_nadadores = st.multiselect(
        "Selecciona hasta 4 nadadores:", df.Nadador.unique(), max_selections=4
    )
    sel_estilos = (
        df.Estilo.unique().tolist()
        if st.checkbox("Todos los estilos")
        else st.multiselect("Estilo(s):", df.Estilo.unique())
    )
    sel_pruebas = (
        df.Distancia.unique().tolist()
        if st.checkbox("Todas las pruebas")
        else st.multiselect("Prueba(s):", df.Distancia.unique())
    )
    sel_fases = (
        df.Fase.unique().tolist()
        if st.checkbox("Todas las fases")
        else st.multiselect("Fase(s):", df.Fase.unique())
    )
    sel_parametros = (
        df.Parametro.unique().tolist()
        if st.checkbox("Todos los parámetros")
        else st.multiselect("Parámetro(s):", df.Parametro.unique())
    )

# ==============================================================================
#   5. FILTRADO DE DATAFRAME
# ==============================================================================

filtered_df = df[
    df.Nadador.isin(sel_nadadores)
    & df.Estilo.isin(sel_estilos)
    & df.Distancia.isin(sel_pruebas)
    & df.Fase.isin(sel_fases)
    & df.Parametro.isin(sel_parametros)
]

# ==============================================================================
#   6. DESCARGA DE CSV FILTRADO
# ==============================================================================

csv_data = filtered_df.to_csv(index=False).encode("utf-8")
st.sidebar.download_button(
    label="📥 Descargar datos filtrados",
    data=csv_data,
    file_name=f"Phoenix_filtered_{datetime.now():%Y%m%d}.csv",
    mime="text/csv",
)

# ==============================================================================
#   7. TABS PRINCIPALES (Gráficos y Detalles)
# ==============================================================================

tab_graficos, tab_detalles = st.tabs([
    "📊 Gráficos Comparativos",
    "📋 Detalles por Nadador",
])

# ------------------------------------------------------------------------------
#   7.1 GRÁFICOS COMPARATIVOS
# ------------------------------------------------------------------------------

def make_line_fig(df_subset: pd.DataFrame, titulo: str):
    fig = px.line(
        df_subset,
        x="Fase_Orden",
        y="Valor",
        color="Nadador",
        markers=True,
        line_group="Nadador",
        hover_data={"Fase": True, "Fase_Orden": False},
        title=titulo,
        category_orders={"Fase_Orden": [1, 2, 3]},
    )
    fig.update_xaxes(
        tickvals=[1, 2, 3],
        ticktext=["Preliminar", "Semifinal", "Final"],
        title="Fase",
    )
    return fig

with tab_graficos:
    if sel_estilos:
        st.markdown("**Estilos seleccionados:** " + ", ".join(sel_estilos))
    for categoria, lista_param in param_categories.items():
        presentes = [p for p in lista_param if p in filtered_df.Parametro.unique()]
        if not presentes:
            continue
        st.subheader(categoria)
        for parametro in presentes:
            nombre_legible = param_translation.get(parametro, parametro)
            df_param = filtered_df[filtered_df.Parametro == parametro]
            estilos_unicos = df_param.Estilo.unique()
            cols = st.columns(len(estilos_unicos)) if len(estilos_unicos) > 1 else [st]
            for idx, estilo in enumerate(estilos_unicos):
                df_estilo = df_param[df_param.Estilo == estilo]
                fig = make_line_fig(df_estilo, f"{nombre_legible} – {estilo}")
                fig.update_layout(
                    legend=dict(orientation="h", y=-0.25, x=0.5, xanchor="center"),
                    height=320 if is_mobile else 500,
                    margin=dict(t=50, b=40),
                )
                cols[idx].plotly_chart(fig, use_container_width=True)

# ------------------------------------------------------------------------------
#   7.2 DETALLES POR NADADOR
# ------------------------------------------------------------------------------

with tab_detalles:
    if sel_nadadores:
        for nadador in sel_nadadores:
            st.markdown(f"### {nadador}")
            sub_df = filtered_df[filtered_df.Nadador == nadador].copy()
            sub_df["Parametro"] = sub_df["Parametro"].map(param_translation).fillna(
                sub_df["Parametro"]
            )
            st.dataframe(
                sub_df,
                use_container_width=True,
                height=300 if is_mobile else 600,
            )
    else:
        st.info("Selecciona al menos un nadador para visualizar detalles.")

# ==============================================================================
#   8. RANKING GLOBAL (cuando no se selecciona nadador)
# ==============================================================================

if not sel_nadadores:
    st.header("🏆 Ranking de Nadadores por Estilo y Prueba (Tiempo Total)")
    ranking_df = (
        df[df.Parametro == "T TOTAL"]
        .dropna(subset=["Valor"])
        .groupby(["Estilo", "Distancia", "Nadador"], as_index=False)["Valor"].min()
    )
    if is_mobile:
        ranking_df["Nadador"] = ranking_df["Nadador"].apply(
            lambda x: f"{x.split()[0][0]}. {x.split()[-1]}"
        )
    ranking_df = ranking_df.sort_values(by=["Estilo", "Distancia", "Valor"])
    for (estilo, distancia), grp in ranking_df.groupby(["Estilo", "Distancia"]):
        st.subheader(f"{estilo} – {distancia}m")
        fig_rank = px.bar(
            grp,
            x="Nadador",
            y="Valor",
            color="Nadador",
            labels={"Valor": "Tiempo Total (s)"},
            title=f"Ranking – {estilo} {distancia}m",
        )
        fig_rank.update_layout(showlegend=False, height=350 if is_mobile else 520)
        st.plotly_chart(fig_rank, use_container_width=True)
        st.dataframe(grp, use_container_width=True, height=250 if is_mobile else 400)

# ==============================================================================
#   FOOTER
# ==============================================================================

st.caption(
    f"© {datetime.now():%Y} República Integra  ·  Versión {APP_VERSION}  ·  Powered by Streamlit"
)
