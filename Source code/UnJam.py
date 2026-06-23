# ==============================================================================
# UnJam: Intelligent Enforcement Decision Support System

# Usage:
#   python UnJam.py
#   streamlit run app.py
# ==============================================================================

import argparse
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path


REQUIRED_PACKAGES = {
    "pandas": "pandas",
    "numpy": "numpy",
    "sklearn": "scikit-learn",
    "xgboost": "xgboost",
    "folium": "folium",
    "streamlit": "streamlit",
    "streamlit_folium": "streamlit-folium",
    "plotly": "plotly",
    "joblib": "joblib",
}


def encode_geohash(latitude, longitude, precision=6):
    base32 = "0123456789bcdefghjkmnpqrstuvwxyz"
    lat_interval = [-90.0, 90.0]
    lon_interval = [-180.0, 180.0]
    geohash = []
    bit = 0
    ch = 0
    even_bit = True
    bits = [16, 8, 4, 2, 1]

    while len(geohash) < precision:
        if even_bit:
            mid = (lon_interval[0] + lon_interval[1]) / 2
            if longitude >= mid:
                ch |= bits[bit]
                lon_interval[0] = mid
            else:
                lon_interval[1] = mid
        else:
            mid = (lat_interval[0] + lat_interval[1]) / 2
            if latitude >= mid:
                ch |= bits[bit]
                lat_interval[0] = mid
            else:
                lat_interval[1] = mid

        even_bit = not even_bit
        if bit < 4:
            bit += 1
        else:
            geohash.append(base32[ch])
            bit = 0
            ch = 0

    return "".join(geohash)


def ensure_packages(skip_install=False):
    missing = [
        package_name
        for import_name, package_name in REQUIRED_PACKAGES.items()
        if importlib.util.find_spec(import_name) is None
    ]
    if missing and skip_install:
        raise RuntimeError(
            "Missing packages: "
            + ", ".join(missing)
            + ". Re-run without --no-install or install them manually."
        )
    if missing:
        print("Installing missing packages: " + ", ".join(missing))
        subprocess.check_call([sys.executable, "-m", "pip", "install", *missing])


def clean_text_series(series, fallback):
    series = series.astype("string").fillna("")
    series = series.str.strip()
    series = series.replace({"": fallback, "nan": fallback, "NaN": fallback, "None": fallback})
    return series.fillna(fallback)


def build_dashboard_code():
    return r'''
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
'''


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--parking-data", default="jan to may police violation_anonymized791b166.csv")
    parser.add_argument("--demand-data", default="train.csv")
    parser.add_argument(
        "--sample-rows",
        type=int,
        default=100000,
        help="Parking CSV rows to use. Set to 0 or a negative value to use the full file.",
    )
    parser.add_argument("--no-install", action="store_true", help="Do not auto-install missing packages.")
    parser.add_argument("--launch", action="store_true", help="Launch Streamlit after generating app.py.")
    args = parser.parse_args()

    ensure_packages(skip_install=args.no_install)

    import joblib
    import numpy as np
    import pandas as pd
    import xgboost as xgb
    from sklearn.metrics import ndcg_score
    from sklearn.model_selection import train_test_split

    print("Loading and merging datasets...")
    parking_path = Path(args.parking_data)
    demand_path = Path(args.demand_data)

    if parking_path.exists() and demand_path.exists():
        sample_rows = None if args.sample_rows <= 0 else args.sample_rows
        parking_df = pd.read_csv(parking_path, nrows=sample_rows)
        demand_df = pd.read_csv(demand_path)
    else:
        print("Input CSVs were not found. Creating a small demo dataset so the app still builds.")
        demo_hash = encode_geohash(12.9716, 77.5946, 6)
        parking_df = pd.DataFrame(
            {
                "latitude": [12.9716, 12.975, 12.969, 12.982, 12.965, 12.978],
                "longitude": [77.5946, 77.60, 77.59, 77.61, 77.58, 77.602],
                "vehicle_type": ["CAR", "BUS", "HGV", "SCOOTER", "VAN", "CAR"],
                "created_datetime": ["2024-01-01 08:00:00", "2024-01-01 09:00:00"] * 3,
                "location": ["MG Road", None, "Residency Road", "Brigade Road", "", "Richmond Circle"],
                "police_station": ["Station A", "Station A", "Station B", "Station B", "Station C", "Station C"],
            }
        )
        demand_df = pd.DataFrame(
            {
                "geohash": [demo_hash] * 6,
                "demand": [0.5, 0.8, 0.6, 0.7, 0.4, 0.65],
                "timestamp": ["2024-01-01 08:00:00", "2024-01-01 09:00:00"] * 3,
            }
        )

    for col in ["location", "police_station", "vehicle_type"]:
        if col not in parking_df.columns:
            parking_df[col] = "UNKNOWN"

    parking_df["latitude"] = pd.to_numeric(parking_df["latitude"], errors="coerce")
    parking_df["longitude"] = pd.to_numeric(parking_df["longitude"], errors="coerce")
    parking_df["created_datetime"] = pd.to_datetime(parking_df["created_datetime"], errors="coerce")
    parking_df = parking_df.dropna(subset=["latitude", "longitude", "created_datetime"]).copy()

    parking_df["vehicle_type"] = clean_text_series(parking_df["vehicle_type"], "UNKNOWN").str.upper()
    parking_df["police_station"] = clean_text_series(parking_df["police_station"], "UNKNOWN")
    parking_df["location"] = clean_text_series(parking_df["location"], "Bengaluru hotspot")

    parking_df["geohash"] = [
        encode_geohash(float(lat), float(lon), precision=6)
        for lat, lon in zip(parking_df["latitude"], parking_df["longitude"])
    ]
    parking_df["hour"] = parking_df["created_datetime"].dt.hour.fillna(8).astype(int)

    if "timestamp" in demand_df.columns:
        demand_df["hour"] = pd.to_datetime(demand_df["timestamp"], errors="coerce").dt.hour
    else:
        demand_df["hour"] = 8
    demand_df["hour"] = pd.to_numeric(demand_df["hour"], errors="coerce").fillna(8).astype(int)
    demand_df["demand"] = pd.to_numeric(demand_df.get("demand", 0.5), errors="coerce")
    demand_df["geohash"] = clean_text_series(demand_df.get("geohash", pd.Series(dtype=str)), "unknown-block")

    global_mean_demand = float(demand_df["demand"].mean()) if demand_df["demand"].notna().any() else 0.5
    demand_avg = demand_df.groupby(["geohash", "hour"], dropna=False)["demand"].mean().reset_index()
    merged_df = pd.merge(parking_df, demand_avg, on=["geohash", "hour"], how="left")
    merged_df["demand"] = pd.to_numeric(merged_df["demand"], errors="coerce").fillna(global_mean_demand)

    print(f"Merged data ready: {merged_df.shape}")
    print("Training UnJam ranker...")

    v_weights = {
        "CAR": 1.0,
        "SCOOTER": 0.3,
        "MOTOR CYCLE": 0.3,
        "BUS": 3.0,
        "HGV": 4.0,
        "LORRY/GOODS VEHICLE": 3.5,
        "PRIVATE BUS": 3.0,
        "BUS (BMTC/KSRTC)": 3.0,
        "LGV": 2.5,
        "TEMPO": 2.0,
        "VAN": 1.5,
        "GOODS AUTO": 1.0,
        "MAXI-CAB": 1.0,
        "MINI LORRY": 2.5,
        "TRACTOR": 3.0,
        "SCHOOL VEHICLE": 2.0,
        "UNKNOWN": 1.0,
    }

    merged_df["is_peak"] = merged_df["hour"].apply(lambda x: 1.2 if 8 <= x <= 11 or 17 <= x <= 20 else 1.0)
    base_intensity = (
        (merged_df["demand"] * 0.65)
        + (merged_df["vehicle_type"].map(v_weights).fillna(1.0) * 0.25)
    ) * merged_df["is_peak"]

    try:
        merged_df["ranking_intensity"] = pd.qcut(
            base_intensity.rank(method="first"),
            q=min(5, max(2, base_intensity.nunique())),
            labels=False,
            duplicates="drop",
        ).astype(int)
    except ValueError:
        merged_df["ranking_intensity"] = 1

    merged_df["hour_sin"] = np.sin(2 * np.pi * merged_df["hour"] / 24)
    merged_df["hour_cos"] = np.cos(2 * np.pi * merged_df["hour"] / 24)
    vehicle_dummies = pd.get_dummies(merged_df["vehicle_type"], prefix="veh")
    merged_df = pd.concat([merged_df, vehicle_dummies], axis=1)
    features = ["latitude", "longitude", "hour_sin", "hour_cos"] + list(vehicle_dummies.columns)

    merged_df["query_group"] = merged_df["police_station"].astype(str) + "_" + merged_df["hour"].astype(str)
    unique_geohashes = merged_df["geohash"].dropna().unique()

    if len(unique_geohashes) >= 2 and len(merged_df) >= 10:
        train_gh, val_gh = train_test_split(unique_geohashes, test_size=0.2, random_state=42)
        train_df = merged_df[merged_df["geohash"].isin(train_gh)].copy()
        val_df = merged_df[merged_df["geohash"].isin(val_gh)].copy()
    else:
        train_df = merged_df.copy()
        val_df = merged_df.copy()

    train_df = train_df.sort_values("query_group").reset_index(drop=True)
    val_df = val_df.sort_values("query_group").reset_index(drop=True)
    train_df = train_df.groupby("query_group").filter(lambda x: len(x) > 1)
    val_df = val_df.groupby("query_group").filter(lambda x: len(x) > 1)

    if train_df.empty:
        train_df = merged_df.copy()
    if val_df.empty:
        val_df = merged_df.copy()

    X_train = train_df[features].fillna(0)
    y_train = train_df["ranking_intensity"].fillna(0).astype(int)
    groups_train = train_df.groupby("query_group").size().tolist()
    X_val = val_df[features].fillna(0)
    y_val = val_df["ranking_intensity"].fillna(0).astype(int)
    groups_val = val_df.groupby("query_group").size().tolist()

    has_rank_pairs = any(group_size > 1 for group_size in groups_train)
    if has_rank_pairs:
        model = xgb.XGBRanker(
            objective="rank:pairwise",
            n_estimators=250,
            learning_rate=0.05,
            max_depth=6,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            tree_method="hist",
        )
        model.fit(
            X_train,
            y_train,
            group=groups_train,
            eval_set=[(X_val, y_val)],
            eval_group=[groups_val],
            verbose=False,
        )
    else:
        print("No multi-item ranking groups found. Using a regressor fallback for demo data.")
        model = xgb.XGBRegressor(
            objective="reg:squarederror",
            n_estimators=120,
            learning_rate=0.05,
            max_depth=4,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            tree_method="hist",
        )
        model.fit(X_train, y_train, verbose=False)

    val_preds = model.predict(X_val)
    scores = []
    start = 0
    for group_size in groups_val:
        end = start + group_size
        if group_size > 1:
            scores.append(ndcg_score([y_val.iloc[start:end].values], [val_preds[start:end]]))
        start = end
    ndcg = float(np.mean(scores)) if scores else 0.0
    print(f"Ranker trained. Mean NDCG: {ndcg:.4f}")

    raw_scores = pd.Series(model.predict(merged_df[features].fillna(0)), index=merged_df.index)
    raw_scores = raw_scores.replace([np.inf, -np.inf], np.nan).fillna(raw_scores.mean())
    min_s = float(raw_scores.min()) if raw_scores.notna().any() else 0.0
    max_s = float(raw_scores.max()) if raw_scores.notna().any() else 0.0
    if max_s > min_s:
        merged_df["priority_score"] = 10 * (raw_scores - min_s) / (max_s - min_s)
    else:
        merged_df["priority_score"] = 5.0
    merged_df["priority_score"] = pd.to_numeric(merged_df["priority_score"], errors="coerce").fillna(5.0).clip(0, 10)

    time_value_per_minute = 4.0
    petrol_price = 102.0
    delay_cost_per_unit = 15.0
    fuel_cost_per_unit = 10.0

    merged_df["speed_increase_pct"] = np.clip((merged_df["priority_score"] / 10) * 15, 0, 15)
    merged_df["delay_recovery_inr"] = merged_df["priority_score"] * merged_df["demand"] * delay_cost_per_unit
    merged_df["fuel_saving_inr"] = merged_df["priority_score"] * 0.5 * fuel_cost_per_unit
    merged_df["economic_loss_inr"] = (
        merged_df["delay_recovery_inr"] + merged_df["fuel_saving_inr"]
    ) * time_value_per_minute
    merged_df["fuel_saved_liters"] = merged_df["fuel_saving_inr"] / petrol_price

    numeric_cols = [
        "priority_score",
        "speed_increase_pct",
        "delay_recovery_inr",
        "fuel_saving_inr",
        "economic_loss_inr",
        "fuel_saved_liters",
        "latitude",
        "longitude",
        "demand",
    ]
    for col in numeric_cols:
        merged_df[col] = pd.to_numeric(merged_df[col], errors="coerce")
        merged_df[col] = merged_df[col].replace([np.inf, -np.inf], np.nan).fillna(0.0)

    missing_location = merged_df["location"].isin(["Bengaluru hotspot", "UNKNOWN", ""])
    merged_df.loc[missing_location, "location"] = (
        merged_df.loc[missing_location, "police_station"].astype(str)
        + " / "
        + merged_df.loc[missing_location, "geohash"].astype(str)
    )

    joblib.dump(model, "ranker_model.pkl")
    with open("feature_names.json", "w", encoding="utf-8") as f:
        json.dump(features, f)
    with open("metrics.json", "w", encoding="utf-8") as f:
        json.dump({"NDCG": ndcg}, f)

    merged_df.to_pickle("final_urbanpulse_data.pkl")
    Path("app.py").write_text(build_dashboard_code(), encoding="utf-8")

    print("Dashboard generated as app.py")
    print("Run: streamlit run app.py")

    if args.launch:
        subprocess.run([sys.executable, "-m", "streamlit", "run", "app.py"], check=False)


if __name__ == "__main__":
    main()
