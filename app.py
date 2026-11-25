
import streamlit as st
import pandas as pd
import numpy as np
import geopandas as gpd
import folium
from streamlit_folium import st_folium

st.set_page_config(
    page_title="Kolhapur Village Infrastructure Map",
    layout="wide"
)

st.title("Kolhapur Village Infrastructure Map")
st.subheader("Village-wise Infrastructure Accessibility")

CSV_FILE = "Village Level Infrastructure all maharashtra data.csv"
ZIP_FILE = "Kolhapur_Village_Boundaries.geojson""

@st.cache_data
def load_map():

    # Load CSV
    df_raw = pd.read_csv(CSV_FILE)

    column_mapping = {
        'State Name (state_name)': 'state_name',
        'District Name (district_name)': 'district_name',
        'Village Name (village_name)': 'village_name',
        'Block Name (block_name)': 'block_name',
        'Gram Panchayat Name (gp_name)': 'gp_name',
        'Connected To All Weather Road (all_weather_road)': 'all_weather_road',
        'Internal Pucca Roads (Cc/ Brick Road) (cc_road)': 'cc_road',
        'Public Transport (pub_trans)': 'pub_trans',
        'Domestic Electricity (elec_domes)': 'elec_domes',
        'Piped Tap Water (tap_water)': 'tap_water',
        'Drainage Facilities (drainage)': 'drainage',
        'HHs using Clean Energy(LPG/Biogas) (clean_energy_hhs)': 'clean_energy_hhs',
        'Internet / Broadband Facility (internet_bb)': 'internet_bb'
    }

    data = df_raw.rename(columns=column_mapping).copy()

    infra_cols = [
        'all_weather_road', 'cc_road', 'pub_trans',
        'elec_domes', 'tap_water', 'drainage',
        'clean_energy_hhs', 'internet_bb'
    ]

    code_map = {
        'yes': 1, 'no': 0,
        'available': 1, 'not available': 0,
        'true': 1, 'false': 0,
        '<50% habitation covered': 2,
        '100% habitation coverrd': 4,
        '50% to 100% habitation covered': 3,
        'not covered': 0,
        'only one habitation covered': 1,
        'partially covered': 1,
        'fully covered': 2,
        'auto': 1, 'bus': 1, 'van': 1,
        'closed drainage': 4,
        'open kuccha drainage': 1,
        'open pucca drainage covered with tiles slabs': 3,
        'open pucca drainage uncovered': 2,
        '>12 hrs': 4, '1-4 hrs': 1,
        '4-8 hrs': 2, '8-12 hrs': 3
    }

    for col in infra_cols:
        data[col] = (
            data[col].astype(str).str.strip().str.lower()
            .replace(code_map)
        )
        data[col] = pd.to_numeric(
            data[col], errors='coerce'
        ).fillna(0)

    # Normalization
    for col in infra_cols:
        minimum = data[col].min()
        maximum = data[col].max()

        if maximum != minimum:
            data[col + '_norm'] = (
                (data[col] - minimum) / (maximum - minimum)
            )
        else:
            data[col + '_norm'] = 0.0

    normalized_cols = [col + '_norm' for col in infra_cols]

    # Infrastructure Score
    data['Infrastructure_Score'] = data[
        normalized_cols
    ].mean(axis=1)

    # Rank
    data['Rank'] = data[
        'Infrastructure_Score'
    ].rank(method='min', ascending=False).astype(int)

    # Accessibility Level
    def accessibility_level(score):
        if score >= 0.60:
            return 'High'
        elif score >= 0.40:
            return 'Medium'
        else:
            return 'Low'

    data['Accessibility_Level'] = (
        data['Infrastructure_Score'].apply(accessibility_level)
    )

    # Kolhapur data
    infra = data[
        data['district_name'].astype(str).str.strip().str.upper()
        == 'KOLHAPUR'
    ].copy()

    infra['village_key'] = (
        infra['village_name'].astype(str)
        .str.strip().str.upper()
    )

    infra = infra.groupby('village_key', as_index=False).agg({
        'Infrastructure_Score': 'mean',
        'Rank': 'min',
        'Accessibility_Level': 'first'
    })

    # Load village boundaries
    gdf = gpd.read_file(ZIP_FILE)

    gdf['district_clean'] = (
        gdf['District'].astype(str).str.upper().str.replace('>', 'A')
    )

    kolhapur = gdf[
        gdf['district_clean'].str.contains('KOLHAPUR', na=False)
    ].copy()

    kolhapur['village_key'] = (
        kolhapur['Vill_name'].astype(str)
        .str.strip().str.upper()
    )

    # Merge
    kolhapur_map = kolhapur.merge(
        infra,
        on='village_key',
        how='left'
    )

    kolhapur_map = kolhapur_map.to_crs(epsg=4326)

    return kolhapur_map


try:
    kolhapur_map = load_map()

    # Summary
    st.write("### Map Summary")

    c1, c2 = st.columns(2)

    c1.metric("Total Villages", len(kolhapur_map))

    c2.metric(
        "Matched Villages",
        int(kolhapur_map['Infrastructure_Score'].notna().sum())
    )

    st.write("### Village Infrastructure Map")

    # Create map
    m = folium.Map(
        location=[16.7, 74.2],
        zoom_start=9,
        tiles=None
    )

    def get_color(feature):

        level = feature['properties'].get(
            'Accessibility_Level'
        )

        if level == 'High':
            return 'green'
        elif level == 'Medium':
            return 'orange'
        elif level == 'Low':
            return 'red'
        else:
            return 'lightgray'

    folium.GeoJson(
        kolhapur_map,
        name='Village Infrastructure',

        style_function=lambda feature: {
            'fillColor': get_color(feature),
            'color': 'black',
            'weight': 0.7,
            'fillOpacity': 0.7
        },

        tooltip=folium.GeoJsonTooltip(
            fields=[
                'Vill_name',
                'Sub_dist',
                'Infrastructure_Score',
                'Rank',
                'Accessibility_Level'
            ],

            aliases=[
                'Village:',
                'Taluka:',
                'Infrastructure Score:',
                'Rank:',
                'Accessibility Level:'
            ]
        )

    ).add_to(m)

    # Fit map
    bounds = kolhapur_map.total_bounds

    m.fit_bounds([
        [bounds[1], bounds[0]],
        [bounds[3], bounds[2]]
    ])

    # Legend
    legend = """
    <div style="
    position:fixed;
    bottom:30px;
    left:30px;
    background:white;
    padding:12px;
    border:1px solid black;
    z-index:9999;
    font-size:14px;">

    <b>Infrastructure Accessibility</b><br>
    <span style="color:green;">●</span> High<br>
    <span style="color:orange;">●</span> Medium<br>
    <span style="color:red;">●</span> Low<br>
    <span style="color:gray;">●</span> No Data

    </div>
    """

    m.get_root().html.add_child(
        folium.Element(legend)
    )

    folium.LayerControl().add_to(m)

    st_folium(
        m,
        use_container_width=True,
        height=650
    )

except Exception as e:
    st.error(f"Error: {e}")
