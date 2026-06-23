
import json
import base64
from pathlib import Path

import folium
import joblib
import numpy as np
import pandas as pd
import streamlit as st
from folium.plugins import MarkerCluster
from streamlit_folium import st_folium


st.set_page_config(
    page_title="UnJam Command Centre",
    layout="wide",
    initial_sidebar_state="expanded",
)

APP_TITLE = "UnJam"
APP_TAGLINE = "AI That Knows What’s Blocking Your City"
LOGO_PATH = Path(__file__).resolve().parent / "assets" / "unjam_logo.png"


def image_data_uri(path):
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


logo_data_uri = image_data_uri(LOGO_PATH)

st.markdown(
    """
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /*
      Important: do not hide Streamlit's header. The sidebar restore control can
      live there after the user collapses the sidebar.
    */
    [data-testid="stHeader"] {
        background: rgba(15, 23, 42, 0.92);
    }
    [data-testid="collapsedControl"],
    [data-testid="stSidebarCollapsedControl"] {
        visibility: visible !important;
        opacity: 1 !important;
        display: flex !important;
        z-index: 999999 !important;
    }

    .stApp {
        background:
            linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(8, 10, 14, 0.98)),
            repeating-linear-gradient(90deg, rgba(255,255,255,0.025) 0, rgba(255,255,255,0.025) 1px, transparent 1px, transparent 68px);
        color: #F8FAFC;
    }
    [data-testid="stSidebar"] {
        background:
            linear-gradient(180deg, #101318 0%, #161B22 58%, #0B0F14 100%);
        color: white;
        border-right: 1px solid rgba(255, 255, 255, 0.08);
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    .metric-card {
        background: rgba(17, 24, 39, 0.78);
        backdrop-filter: blur(10px);
        -webkit-backdrop-filter: blur(10px);
        padding: 18px;
        border-radius: 8px;
        box-shadow: 0 10px 30px rgba(0, 0, 0, 0.24);
        border: 1px solid rgba(255, 255, 255, 0.11);
        color: white;
    }
    .metric-card:hover {
        transform: translateY(-2px);
        border: 1px solid rgba(37, 99, 235, 0.55);
    }
    .ai-badge {
        background: #E11D48;
        color: white;
        padding: 4px 12px;
        border-radius: 999px;
        font-size: 0.78rem;
        font-weight: 700;
        display: inline-block;
    }
    .queue-row {
        margin-bottom: 10px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        gap: 16px;
    }
    .queue-title {
        margin: 0;
        overflow-wrap: anywhere;
    }
    .sidebar-brand {
        display: flex;
        align-items: center;
        gap: 12px;
        padding: 10px 0 4px 0;
    }
    .sidebar-logo {
        width: 58px;
        height: 72px;
        object-fit: contain;
        object-position: center;
        border: 0;
        box-shadow: none;
        background: transparent;
    }
    .sidebar-name {
        font-size: 1.45rem;
        font-weight: 800;
        line-height: 1;
        letter-spacing: 0;
    }
    .sidebar-tagline {
        color: #CBD5E1;
        font-size: 0.78rem;
        line-height: 1.25;
        margin-top: 5px;
    }
    .hero-panel {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 24px;
        padding: 18px 0 8px 0;
    }
    .hero-kicker {
        color: #FACC15;
        font-size: 0.78rem;
        font-weight: 800;
        letter-spacing: 0.08em;
        text-transform: uppercase;
    }
    .hero-title {
        margin: 4px 0 0 0;
        font-size: clamp(2.4rem, 5vw, 4.8rem);
        line-height: 0.95;
        font-weight: 900;
        letter-spacing: 0;
        color: #F8FAFC;
    }
    .hero-subtitle {
        margin: 8px 0 0 0;
        color: #CBD5E1;
        font-size: clamp(1rem, 1.8vw, 1.45rem);
        font-weight: 600;
    }
    .hero-accent {
        display: flex;
        gap: 8px;
        margin-top: 14px;
    }
    .signal-dot {
        width: 38px;
        height: 6px;
        border-radius: 999px;
        display: inline-block;
    }
    .hero-logo {
        width: min(22vw, 118px);
        max-height: 190px;
        object-fit: contain;
        filter: drop-shadow(0 18px 28px rgba(0,0,0,0.42));
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def clean_text_series(series, fallback):
    series = series.astype("string").fillna("")
    series = series.str.strip()
    series = series.replace({"": fallback, "nan": fallback, "NaN": fallback, "None": fallback})
    return series.fillna(fallback)


def clean_dashboard_data(df):
    df = df.copy()

    for col, fallback in [
        ("location", "Bengaluru hotspot"),
        ("police_station", "UNKNOWN"),
        ("vehicle_type", "UNKNOWN"),
        ("geohash", "unknown-block"),
    ]:
        if col not in df.columns:
            df[col] = fallback
        df[col] = clean_text_series(df[col], fallback)

    missing_location = df["location"].isin(["Bengaluru hotspot", "UNKNOWN"])
    fallback_location = df["police_station"].where(
        ~df["police_station"].isin(["UNKNOWN", ""]),
        "Bengaluru hotspot",
    )
    df.loc[missing_location, "location"] = (
        fallback_location[missing_location].astype(str)
        + " / "
        + df.loc[missing_location, "geohash"].astype(str)
    )

    numeric_cols = [
        "latitude",
        "longitude",
        "priority_score",
        "speed_increase_pct",
        "delay_recovery_inr",
        "fuel_saving_inr",
        "economic_loss_inr",
        "fuel_saved_liters",
        "demand",
    ]
    for col in numeric_cols:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = pd.to_numeric(df[col], errors="coerce")
        df[col] = df[col].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    df["priority_score"] = df["priority_score"].clip(0, 10)
    df["display_location"] = df["location"].astype(str)
    return df


def format_inr(value):
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        value = 0
    return f"INR {value:,.0f}"


def format_inr_lakh(value):
    value = pd.to_numeric(value, errors="coerce")
    if pd.isna(value):
        value = 0
    return f"INR {value / 100000:.3f} lakh"


@st.cache_data
def load_dataframe():
    return clean_dashboard_data(pd.read_pickle("final_urbanpulse_data.pkl"))


@st.cache_resource
def load_resources():
    model = joblib.load("ranker_model.pkl")
    with open("feature_names.json", "r", encoding="utf-8") as f:
        features = json.load(f)
    with open("metrics.json", "r", encoding="utf-8") as f:
        metrics = json.load(f)
    return model, features, metrics


df = load_dataframe()
model, features, metrics = load_resources()


with st.sidebar:
    logo_html = (
        f'<img class="sidebar-logo" src="{logo_data_uri}" alt="UnJam logo">'
        if logo_data_uri
        else ""
    )
    st.markdown(
        f"""
        <div class="sidebar-brand">
            {logo_html}
            <div>
                <div class="sidebar-name">{APP_TITLE}</div>
                <div class="sidebar-tagline">{APP_TAGLINE}</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.markdown("### Command Centre")
    st.divider()

    st.markdown("#### Resource Optimization")
    top_k = st.slider("Deployment Focus (Top K Hotspots)", 10, 1000, 100)

    all_stations = ["All Units"] + sorted(df["police_station"].dropna().unique().tolist())
    selected_station = st.selectbox("Enforcement Unit", all_stations)

    st.divider()
    st.markdown("#### Ranking Performance")
    st.write(f"**NDCG Score:** {metrics.get('NDCG', 0):.3f}")
    st.caption("Geohash block validation active")

    st.divider()
    st.markdown("#### System Status")
    st.success("XGBRanker: Online")
    st.info("Mode: Learning-to-Rank")


if selected_station != "All Units":
    filtered = df[df["police_station"] == selected_station].copy()
else:
    filtered = df.copy()

filtered = (
    filtered.sort_values(by="priority_score", ascending=False)
    .head(top_k)
    .reset_index(drop=True)
)

top_location = filtered.iloc[0]["display_location"] if not filtered.empty else "N/A"
speed_gain = float(filtered["speed_increase_pct"].mean()) if not filtered.empty else 0.0

hero_logo_html = (
    f'<img class="hero-logo" src="{logo_data_uri}" alt="UnJam location logo">'
    if logo_data_uri
    else ""
)

st.markdown(
    f"""
    <div style="display: flex; align-items: center; gap: 10px;">
        <div class="hero-panel" style="width: 100%;">
            <div>
                <div class="hero-kicker">Bengaluru Enforcement Intelligence</div>
                <h1 class="hero-title">{APP_TITLE}</h1>
                <p class="hero-subtitle">{APP_TAGLINE}</p>
                <div class="hero-accent">
                    <span class="signal-dot" style="background:#E11D48;"></span>
                    <span class="signal-dot" style="background:#FACC15;"></span>
                    <span class="signal-dot" style="background:#22C55E;"></span>
                </div>
            </div>
            {hero_logo_html}
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)
st.markdown("---")

col_h1, col_h2, col_h3, col_h4 = st.columns(4)
with col_h1:
    st.markdown(
        f'<p style="font-size: 0.9rem; color: #94A3B8; margin-bottom: 0;">Violations Analysed</p>'
        f'<h3 style="margin-top: 0;">{len(df):,}</h3>',
        unsafe_allow_html=True,
    )
with col_h2:
    st.markdown(
        '<p style="font-size: 0.9rem; color: #94A3B8; margin-bottom: 0;">Model Type</p>'
        '<h3 style="margin-top: 0; color: #22C55E;">LambdaMART</h3>',
        unsafe_allow_html=True,
    )
with col_h3:
    st.markdown(
        f'<p style="font-size: 0.9rem; color: #94A3B8; margin-bottom: 0;">Top Priority Road</p>'
        f'<h3 style="margin-top: 0; color: #F59E0B; overflow-wrap: anywhere;">{top_location}</h3>',
        unsafe_allow_html=True,
    )
with col_h4:
    st.markdown(
        f'<p style="font-size: 0.9rem; color: #94A3B8; margin-bottom: 0;">Validation</p>'
        f'<h3 style="margin-top: 0;">NDCG {metrics.get("NDCG", 0):.2f}</h3>',
        unsafe_allow_html=True,
    )

st.markdown("---")

st.markdown(
    f"""
    <div style="background: rgba(37, 99, 235, 0.10); padding: 20px; border-radius: 8px;
                border-left: 5px solid #3B82F6; margin-bottom: 20px;
                border: 1px solid rgba(59, 130, 246, 0.30);">
        <h4 style="margin-top: 0; color: #60A5FA;">Simulation: Operational Impact of Top-{top_k} Deployment</h4>
        <div style="display: flex; justify-content: space-between; gap: 16px; flex-wrap: wrap;">
            <div><p style="margin: 0; font-size: 0.9rem; color: #94A3B8;">Est. Speed Gain</p><h3 style="margin: 0; color: #10B981;">+{speed_gain:.1f}%</h3></div>
            <div><p style="margin: 0; font-size: 0.9rem; color: #94A3B8;">Fuel Recoverable</p><h3 style="margin: 0; color: #10B981;">{filtered["fuel_saved_liters"].sum():,.0f} L</h3></div>
            <div><p style="margin: 0; font-size: 0.9rem; color: #94A3B8;">Economic Recovery</p><h3 style="margin: 0; color: #3B82F6;">{format_inr_lakh(filtered["economic_loss_inr"].sum())}</h3></div>
            <div><p style="margin: 0; font-size: 0.9rem; color: #94A3B8;">Deployment Load</p><h3 style="margin: 0; color: #EF4444;">{len(filtered)} Units</h3></div>
        </div>
        <p style="font-size: 0.74rem; color: #64748B; margin-top: 10px;">
            Based on estimated deployment cycle capacity.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(
        f"""
        <div class="metric-card">
            <p style="color: #94A3B8; font-size: 0.9rem; margin: 0;">Priority Zones</p>
            <h2 style="margin: 0;">{len(filtered):,}</h2>
            <p style="color: #3B82F6; font-size: 0.8rem; margin: 0;">High-intensity targets</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        f"""
        <div class="metric-card">
            <p style="color: #94A3B8; font-size: 0.9rem; margin: 0;">Economic Value</p>
            <h2 style="margin: 0;">{format_inr_lakh(filtered["economic_loss_inr"].sum())}</h2>
            <p style="color: #10B981; font-size: 0.8rem; margin: 0;">Productivity potential</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        f"""
        <div class="metric-card">
            <p style="color: #94A3B8; font-size: 0.9rem; margin: 0;">Flow Efficiency</p>
            <h2 style="margin: 0;">{speed_gain:.1f}%</h2>
            <p style="color: #10B981; font-size: 0.8rem; margin: 0;">Avg corridor gain</p>
        </div>
        """,
        unsafe_allow_html=True,
    )
with col4:
    st.markdown(
        f"""
        <div class="metric-card">
            <p style="color: #94A3B8; font-size: 0.9rem; margin: 0;">Fuel Recovery</p>
            <h2 style="margin: 0;">{filtered["fuel_saved_liters"].sum():,.0f} L</h2>
            <p style="color: #EF4444; font-size: 0.8rem; margin: 0;">Potential saving</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

col_left, col_right = st.columns([2, 1])

with col_left:
    st.subheader("Deployment Priority Map")
    if not filtered.empty:
        map_center = [filtered["latitude"].mean(), filtered["longitude"].mean()]
    else:
        map_center = [12.9716, 77.5946]
    m = folium.Map(location=map_center, zoom_start=13, tiles=None)
    folium.TileLayer(
        tiles="https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
        attr="&copy; OpenStreetMap contributors &copy; CARTO",
        name="CARTO Positron",
        control=True,
    ).add_to(m)
    folium.TileLayer(
        tiles="OpenStreetMap",
        name="OpenStreetMap",
        control=True,
    ).add_to(m)
    hotspot_cluster = MarkerCluster(
        name="Priority hotspots",
        overlay=True,
        control=True,
        options={
            "showCoverageOnHover": False,
            "spiderfyOnMaxZoom": True,
            "maxClusterRadius": 42,
            "disableClusteringAtZoom": 16,
        },
    ).add_to(m)

    for rank, r in filtered.iterrows():
        color = "#EF4444" if r["priority_score"] > 8 else "#F59E0B" if r["priority_score"] > 5 else "#3B82F6"
        dot_icon = folium.DivIcon(
            icon_size=(16, 16),
            icon_anchor=(8, 8),
            html=(
                f"<div style='width: 12px; height: 12px; border-radius: 50%; "
                f"background: {color}; border: 2px solid white; "
                f"box-shadow: 0 1px 5px rgba(15, 23, 42, 0.45);'></div>"
            ),
        )
        popup_html = (
            f"<div style='font-family: Arial; width: 220px;'>"
            f"<h4 style='margin:0; color:{color};'>RANK: {rank + 1}</h4>"
            f"<p style='margin:5px 0;'><b>Location:</b> {r['display_location']}</p>"
            f"<p style='margin:5px 0;'><b>Vehicle:</b> {r['vehicle_type']}</p>"
            f"<hr><p style='margin:2px 0;'><b>Priority Score:</b> {r['priority_score']:.1f}/10</p>"
            f"<p style='margin:2px 0;'><b>Est. Benefit:</b> {format_inr(r['economic_loss_inr'])}</p>"
            f"</div>"
        )
        folium.Marker(
            location=[r["latitude"], r["longitude"]],
            icon=dot_icon,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"Rank {rank + 1} | Score {r['priority_score']:.1f}",
        ).add_to(hotspot_cluster)
    folium.LayerControl(position="topright", collapsed=True).add_to(m)
    st_folium(m, width=800, height=450)

with col_right:
    st.subheader("AI Dispatch Support")
    if not filtered.empty:
        top_v = filtered.iloc[0]
        st.markdown(
            f"""
            <div class="metric-card" style="border: 1px solid #2563EB;">
                <p class="ai-badge">CRITICAL RANK #1</p>
                <h4 style="margin: 10px 0; color: #60A5FA; overflow-wrap: anywhere;">{top_v["display_location"]}</h4>
                <p style="font-size: 0.9rem; color: #94A3B8;">Vehicle: <b>{top_v["vehicle_type"]}</b></p>
                <hr style="opacity: 0.12;">
                <div style="background: rgba(30, 41, 59, 0.82); padding: 14px; border-radius: 8px; border: 1px solid rgba(59, 130, 246, 0.24);">
                    <p style="margin: 0; font-size: 0.78rem; color: #94A3B8;"><b>Ranking Urgency:</b> Top target</p>
                    <p style="margin: 0; font-size: 0.78rem; color: #EF4444;"><b>Decision:</b> Immediate Dispatch</p>
                    <p style="margin: 0; font-size: 0.78rem; color: #F59E0B;"><b>Priority Score:</b> {top_v["priority_score"]:.1f}/10</p>
                    <hr style="opacity: 0.12; margin: 10px 0;">
                    <p style="margin: 0; font-size: 0.82rem; color: #60A5FA;"><b>Benefit: {format_inr(top_v["economic_loss_inr"])} Recovery</b></p>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

st.markdown("---")
st.subheader("Top-5 Enforcement Queue")
if not filtered.empty:
    pq = filtered.head(5).reset_index(drop=True)
    colors = ["#EF4444", "#F59E0B", "#FBBF24", "#34D399", "#3B82F6"]
    for idx, r in pq.iterrows():
        st.markdown(
            f"""
            <div class="metric-card" style="margin-bottom: 10px; border-left: 5px solid {colors[idx]};">
                <div class="queue-row">
                    <div>
                        <h4 class="queue-title" style="color: {colors[idx]};">#{idx + 1} {r["display_location"]}</h4>
                        <p style="font-size: 0.9rem; color: #94A3B8; margin: 0;">
                            Vehicle: <b>{r["vehicle_type"]}</b> | Score: <b>{r["priority_score"]:.1f}/10</b>
                        </p>
                    </div>
                    <div style="text-align: right; min-width: 120px;">
                        <p style="margin: 0; font-size: 0.8rem; color: #94A3B8;">Recovery</p>
                        <h4 style="margin: 0; color: #10B981;">{format_inr(r["economic_loss_inr"])}</h4>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
else:
    st.info("No records match the selected filters.")

with st.expander("AI Methodology (Learning-to-Rank)"):
    st.markdown(
        """
        **UnJam** is a spatial learning-to-rank system for prioritizing
        enforcement deployment.

        1. **Learning-to-Rank:** Uses XGBRanker with a pairwise LambdaMART objective.
        2. **Geospatial Block Validation:** Holds out geohash blocks for validation.
        3. **Evaluation:** Uses NDCG to measure ranking quality.
        """
    )

st.markdown("---")
st.markdown(
    "<p style='text-align: center; color: #64748B;'>2026 UnJam | AI That Knows What’s Blocking Your City</p>",
    unsafe_allow_html=True,
)
