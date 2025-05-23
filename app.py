
import pathlib
import subprocess
from datetime import datetime
from functools import lru_cache

import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(layout="wide")

# ────────────────────────────────────────────────────────────────────────────────
# 0. GESTIÓN DE VERSIÓN DINÁMICA
# ────────────────────────────────────────────────────────────────────────────────

DEFAULT_VERSION = "0.2.1"

_version_file = pathlib.Path(__file__).with_name("VERSION")
if _version_file.exists():
    APP_VERSION = _version_file.read_text().strip()
else:
    # Si no hay archivo, intenta extraer la última Git tag
    try:
        APP_VERSION = (
            subprocess.check_output(["git", "describe", "--tags"], stderr=subprocess.DEVNULL)
            .decode()
            .strip()
        )
    except Exception:
        APP_VERSION = DEFAULT_VERSION

# ────────────────────────────────────────────────────────────────────────────────
# 1. DETECCIÓN AUTOMÁTICA DE DISPOSITIVO (ESCRITORIO / MÓVIL)
# ────────────────────────────────────────────────────────────────────────────────

try:
    from streamlit_javascript import st_javascript

    viewport_width = st_javascript("return window.innerWidth;") or 1200
except Exception:
    viewport_width = 1200  # Fallback – escritorio

is_mobile = viewport_width < 992  # Bootstrap md breakpoint

# ────────────────────────────────────────────────────────────────────────────────
# 2. CARGA Y NORMALIZACIÓN DE DATOS (con caching agresivo)
# ────────────────────────────────────────────────────────────────────────────────

RAW_CSV_URL = "https://raw.githubusercontent.com/goatdev08/phoenix.dash/main/archivo.csv"


@st.cache_data(show_spinner="Cargando datos…")
def load_data(path: str | None = None) -> pd.DataFrame:
    """Carga el CSV y normaliza nomenclatura."""

    path = path or RAW_CSV_URL
    df = pd.read_csv(path)
    df.columns = [c.strip().replace("/", "").replace(" ", "_") for c in df.columns]

    # Estandarizar columna de fase (antes Cat_Prueba) y su orden lógico.
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

# ────────────────────────────────────────────────────────────────────────────────
# 3. CONSTANTES Y DICCIONARIOS AUXILIARES
# ────────────────────────────────────────────────────────────────────────────────

param_translation = {
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

# ────────────────────────────────────────────────────────────────────────────────
# 4. HEADER Y PANEL DE FILTROS (con session_state)
# ────────────────────────────────────────────────────────────────────────────────


def init_state(key, value):
    if key not in st.session_state:
        st.session_state[key] = value


init_state("nadadores", [])
init_state("estilos", [])
init_state("pruebas", [])
init_state("fases", [])
init_state("parametros", [])

st.title("Phoenix Team Analyst 🐦‍🔥")

with st.sidebar:
    st.markdown("#### Versión de app")
    st.success(APP_VERSION)

    st.markdown("### Filtros")

    st.session_state["nadadores"] = st.multiselect(
        "Selecciona hasta 4 nadadores:",
        df.Nadador.unique(),
        default=st.session_state["nadadores"],
        max_selections=4,
    )

    st.session_state["estilos"] = (
        df.Estilo.unique().tolist()
        if st.checkbox("Todos los estilos", value=not st.session_state["estilos"])
        else st.multiselect("Estilo(s):", df.Estilo.unique(), default=st.session_state["estilos"])
    )

    st.session_state["pruebas"] = (
        df.Distancia.unique().tolist()
        if st.checkbox("Todas las pruebas", value=not st.session_state["pruebas"])
        else st.multiselect("Prueba(s):", df.Distancia.unique(), default=st.session_state["pruebas"])
    )

    st.session_state["fases"] = (
        df.Fase.unique().tolist()
        if st.checkbox("Todas las fases", value=not st.session_state["fases"])
        else st.multiselect("Fase(s):", df.Fase.unique(), default=st.session_state["fases"])
    )

    st.session_state["parametros"] = (
        df.Parametro.unique().tolist()
        if st.checkbox("Todos los parámetros", value=not st.session_state["parametros"])
        else st.multiselect(
            "Parámetro(s):", df.Parametro.unique(), default=st.session_state["parametros"]
        )
    )

# ────────────────────────────────────────────────────────────────────────────────
# 5. FILTRADO DE DATAFRAME
# ────────────────────────────────────────────────────────────────────────────────

filtered_df = df[
    df.Nadador.isin(st.session_state["nadadores"])
    & df.Estilo.isin(st.session_state["estilos"])
    & df.Distancia.isin(st.session_state["pruebas"])
    & df.Fase.isin(st.session_state["fases"])
    & df.Parametro.isin(st.session_state["parametros"])
]

# ────────────────────────────────────────────────────────────────────────────────
# 6. BOTÓN PARA DESCARGAR CSV FILTRADO
# ────────────────────────────────────────────────────────────────────────────────

csv_data = filtered_df.to_csv(index=False).encode()
st.sidebar.download_button(
    "📥 Descargar datos filtrados",
    csv_data,
    file_name=f"Phoenix_filtered_{datetime.now():%Y%m%d}.csv",
    mime="text/csv",
)

# ────────────────────────────────────────────────────────────────────────────────
# 7. TABS PRINCIPALES
# ────────────────────────────────────────────────────────────────────────────────

tab1, tab2 = st.tabs(["📊 Gráficos Comparativos", "📋 Detalles por Nadador"])

# ╭──────────────────────────────────────────────────────────────────────────────╮
# │ TAB 1 · GRÁFICOS COMPARATIVOS                                              │
# ╰──────────────────────────────────────────────────────────────────────────────╯

with tab1:

    # Chips de estilos seleccionados (UX claridad)
    if st.session_state["estilos"]:
        st.markdown("**Estilos seleccionados:** " + ", ".join(st.session_state["estilos"]))

    for category, param_list in param_categories.items():
        selected_in_category = [p for p in param_list if p in filtered_df.Parametro.unique()]
        if not selected_in_category:
            continue

        st.markdown(f"### {category}")

        for parametro in selected_in_category:
            nombre_legible = param_translation.get(parametro, parametro)
            param_df = filtered_df[filtered_df.Parametro == parametro]

            estilos_unicos = param_df.Estilo.unique()
            n_estilos = len(estilos_unicos)

            # Crear columnas dinámicas si hay múltiples estilos
            cols = st.columns(n_estilos) if n_estilos > 1 else [st]

            for idx, estilo in enumerate(estilos_unicos):
                estilo_df = param_df[param_df.Estilo == estilo]

                @st.cache_resource(show_spinner=False)
                def make_fig(df_subset: pd.DataFrame, titulo: str):
                    fig_local = px.line(
                        df_subset,
                        x="Fase_Orden",
                        y="Valor",
                        color="Nadador",
                        markers=True,
                        line_group="Nadador",
                        hover_data={"Fase": True, "Fase_Orden": False},
                        title=titulo,
                    )
                    fig_local.update_xaxes(visible=False)
                    return fig_local

                fig_title = f"{nombre_legible} – {estilo}"
                fig = make_fig(estilo_df, fig_title)

                show_legend = (
                    not is_mobile or st.checkbox("Mostrar leyenda", key=f"legend_{parametro}_{estilo}")
                )
                fig.update_layout(
                    showlegend=show_legend,
                    legend=dict(orientation="h", yanchor="bottom", y=-0.35, xanchor="center", x=0.5),
                    margin=dict(t=50, b=30 if is_mobile else 60),
                    height=350 if is_mobile else 520,
                )

                cols[idx].plotly_chart(fig, use_container_width=True)

# ╭──────────────────────────────────────────────────────────────────────────────╮
# │ TAB 2 · DETALLES POR NADADOR                                               │
# ╰──────────────────────────────────────────────────────────────────────────────╯

with tab2:
    if st.session_state["nadadores"]:
        for nadador in st.session_state["nadadores"]:
            st.markdown(f"#### {nadador}")
            sub_df = filtered_df[filtered_df.Nadador == nadador].copy()
            sub_df["Parametro"] = sub_df["Parametro"].map(param_translation).fillna(sub_df["Parametro"])
            st.dataframe(sub_df, use_container_width=True, height=300 if is_mobile else 600)
    else:
        st.info("Selecciona al menos un nadador para ver los detalles.")

# ────────────────────────────────────────────────────────────────────────────────
# 8. RANKING GLOBAL CUANDO NO SE FILTRA NADADOR
# ────────────────────────────────────────────────────────────────────────────────

if not st.session_state["nadadores"]:
    st.subheader("🏆 Ranking de Nadadores por Estilo y Prueba (Tiempo Total)")

    tiempo_total_df = df[df.Parametro == "T TOTAL"].dropna(subset=["Valor"])
    grouped = tiempo_total_df.groupby(["Estilo", "Distancia", "Nadador"], as_index=False)["Valor"].min()

    if is_mobile:
        grouped["Nadador"] = grouped["Nadador"].apply(lambda x: f"{x.split()[0][0]}. {x.split()[-1]}")

    grouped_sorted = grouped.sort_values(by=["Estilo", "Distancia", "Valor"])

    for (estilo, distancia), group in grouped_sorted.groupby(["Estilo", "Distancia"]):
        st.markdown(f"### {estilo} – {distancia}m")

        fig = px.bar(
            group,
            x="Nadador",
            y="Valor",
            color="Nadador",
            title=f"Ranking – {estilo} {distancia}m (Tiempo Total)",
            labels={"Valor": "Tiempo Total (s)"},
        )

        fig.update_layout(
            showlegend=False,
            margin=dict(t=50, b=30 if is_mobile else 60),
            height=350 if is_mobile else 520,
        )

        st.plotly_chart(fig, use_container_width=True)
        st.dataframe(group, use_container_width=True, height=300 if is_mobile else 500)
