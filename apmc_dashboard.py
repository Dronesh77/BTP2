import streamlit as st
import pandas as pd
import plotly.express as px
import pyarrow as pa
import geopandas as gpd
# Set page configuration 
st.set_page_config(layout="wide", page_title="APMC Data Explorer")

# Load cleaned data with error handling
@st.cache_data
def load_data():
    try:
        return pd.read_excel("/Users/yutika/Documents/BTP/Cleaned_APMC_Data.xlsx")
    except FileNotFoundError:
        st.error("The specified file was not found.")
        return pd.DataFrame()  # Return an empty DataFrame in case of error

@st.cache_data
def load_geojson():
    try:
        # Update this path to your actual India shapefile location
        return gpd.read_file("/Users/yutika/Documents/BTP/Geodata-of-India-master/India.shp")  # or .shp file
    except FileNotFoundError:
        st.error("India shapefile not found. Choropleth map will not be available.")
        return None

# Load data
df = load_data()
india_gdf = load_geojson()




# Ensure the 'Date' column is in proper format
if not df.empty and 'Date' in df.columns:
    df['Date'] = pd.to_datetime(df['Date'])

# Check if data loaded correctly
if df.empty:
    st.stop()

# Normalize state names if geojson is loaded
if india_gdf is not None:
    df['State'] = df['State'].str.strip().str.title()
    india_gdf['st_nm'] = india_gdf['st_nm'].str.strip().str.title()
    
    # Rename shapefile column if needed
    if 'st_nm' in india_gdf.columns and 'State' not in india_gdf.columns:
        india_gdf = india_gdf.rename(columns={'st_nm': 'State'})

# Dashboard title with emoji and styling
st.title("📊 APMC Data Explorer Dashboard")
st.markdown("""
    <style>
    .main-header {
        font-size: 2.5rem;
        color: #1E88E5;
    }
    </style>
""", unsafe_allow_html=True)

# Create tabs for different views
tab1, tab2, tab3 = st.tabs(["📈 Price Analytics", "🗺️ Geospatial View", "📊 Market Stats"])

# Tab 1: Price Analytics
with tab1:
    # Filters directly in the tab instead of sidebar
    st.markdown("### Filters")
    col_filters = st.columns(3)
    
    with col_filters[0]:
        states_tab1 = st.multiselect("Select State(s)", df['State'].unique(), key="states_tab1")
    
    apmcs_tab1 = []
    commodities_tab1 = []
    
    with col_filters[1]:
        if states_tab1:
            apmc_options = df[df['State'].isin(states_tab1)]['APMC'].unique()
        else:
            apmc_options = df['APMC'].unique()
        apmcs_tab1 = st.multiselect("Select APMC(s)", apmc_options, key="apmcs_tab1")
    
    with col_filters[2]:
        if states_tab1 and apmcs_tab1:
            commodity_options = df[(df['State'].isin(states_tab1)) & 
                                  (df['APMC'].isin(apmcs_tab1))]['Commodity'].unique()
        elif states_tab1:
            commodity_options = df[df['State'].isin(states_tab1)]['Commodity'].unique()
        elif apmcs_tab1:
            commodity_options = df[df['APMC'].isin(apmcs_tab1)]['Commodity'].unique()
        else:
            commodity_options = df['Commodity'].unique()
        commodities_tab1 = st.multiselect("Select Commodity(ies)", commodity_options, key="commodities_tab1")
    
    # Apply filters for tab 1
    filtered_df_tab1 = df.copy()
    if states_tab1:
        filtered_df_tab1 = filtered_df_tab1[filtered_df_tab1['State'].isin(states_tab1)]
    if apmcs_tab1:
        filtered_df_tab1 = filtered_df_tab1[filtered_df_tab1['APMC'].isin(apmcs_tab1)]
    if commodities_tab1:
        filtered_df_tab1 = filtered_df_tab1[filtered_df_tab1['Commodity'].isin(commodities_tab1)]
    
    st.markdown("---")
    
    # Display Price Analytics content
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.markdown("### Filtered Data Preview")
        st.dataframe(filtered_df_tab1.head(10), height=300)
    
    with col2:
        st.markdown("### 📈 Modal Price Trend Over Time")
        if not filtered_df_tab1.empty:
            fig = px.line(filtered_df_tab1, x='Date', y='Modal Price', color='Commodity', markers=True,
                        title='Modal Price Over Time')
            fig.update_layout(height=400)
            st.plotly_chart(fig, use_container_width=True)
    
    st.markdown("### 📊 Price Distribution")
    fig2 = px.box(filtered_df_tab1, x='Commodity', y='Modal Price', points="all",
                title='Boxplot of Modal Prices by Commodity')
    st.plotly_chart(fig2, use_container_width=True)

# Tab 2: Geospatial View
with tab2:
    st.markdown("### 🗺️ State-wise Price Comparison")

    if india_gdf is None:
        st.error("Geospatial data not available. Please ensure the India shapefile is correctly loaded.")
    else:
        # Select commodity
        map_commodity = st.selectbox(
            "Select Commodity for Map Visualization",
            options=sorted(df['Commodity'].unique()),
            key="map_commodity"
        )

        # Select date (optional)
        available_dates = sorted(df['Date'].dropna().unique())
        map_date = st.selectbox(
            "Select Date (optional, aggregated if not selected)",
            options=[""] + [str(date)[:10] for date in available_dates],  # prepend empty string for 'no selection'
            key="map_date"
        )

        # Filter by commodity
        commodity_df = df[df['Commodity'] == map_commodity]

        # Further filter by date if selected
        if map_date:
            commodity_df = commodity_df[commodity_df['Date'].astype(str).str.startswith(map_date)]

        # Compute average modal price per state
        avg_price = commodity_df.groupby('State')['Modal Price'].mean().reset_index()

        # Merge with India GeoDataFrame
        merged = india_gdf.copy()
        merged = merged.merge(avg_price, on='State', how='left')

        # Color and display setup
        merged['Color'] = merged['Modal Price'].notnull().map({True: 1, False: 0})
        merged['Display Price'] = merged['Modal Price'].fillna(0)

        # Max/min price for hover data
        price_extremes = commodity_df.groupby('State')['Modal Price'].agg(['min', 'max']).reset_index()
        merged = merged.merge(price_extremes, on='State', how='left')

        # Plotly map
        fig = px.choropleth(
            merged,
            geojson=merged.geometry,
            locations=merged.index,
            color='Display Price',
            color_continuous_scale=[
                [0, "lightgray"],
                [0.000001, "green"],
                [1, "red"]
            ],
            range_color=[0.000001, merged['Modal Price'].max() if merged['Modal Price'].notnull().any() else 1],
            hover_name='State',
            hover_data={
                'Modal Price': ':.2f',
                'min': ':.2f',
                'max': ':.2f',
                'Display Price': False,
                'Color': False
            },
            title=f"Average Modal Price for {map_commodity} by State" + (f" on {map_date}" if map_date else " (Aggregated)"),
            labels={'Modal Price': 'Avg Modal Price (INR)', 'min': 'Min Price', 'max': 'Max Price'}
        )

        fig.update_geos(
            fitbounds="locations",
            visible=False,
            showcoastlines=False,
            showland=True,
            landcolor="rgb(240, 240, 240)"
        )

        fig.update_layout(
            height=600,
            margin={"r": 0, "t": 50, "l": 0, "b": 0},
            coloraxis_colorbar=dict(
                title="Price (INR)",
                tickvals=[merged['Modal Price'].min(), merged['Modal Price'].max()] if merged['Modal Price'].notnull().any() else [0, 1],
                ticktext=[f"{merged['Modal Price'].min():.0f}", f"{merged['Modal Price'].max():.0f}"] if merged['Modal Price'].notnull().any() else ["0", "1"]
            )
        )

        st.plotly_chart(fig, use_container_width=True)

        st.markdown("""
        <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 20px;">
            <b>Note:</b> Gray states do not have data for the selected commodity.
        </div>
        """, unsafe_allow_html=True)

        # State-wise data display
        st.markdown("### State-wise Average Price Data")
        all_states_df = pd.DataFrame({'State': india_gdf['State'].unique()})
        all_states_df = all_states_df.merge(avg_price, on='State', how='left')
        all_states_df = all_states_df.sort_values('Modal Price', ascending=False, na_position='last')

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"#### States with {map_commodity} Data")
            st.dataframe(avg_price.sort_values('Modal Price', ascending=False), use_container_width=True)
        with col2:
            st.markdown("#### All States")
            all_states_df_display = all_states_df.copy()
            all_states_df_display['Modal Price'] = all_states_df_display['Modal Price'].fillna("No Data")
            st.dataframe(all_states_df_display, use_container_width=True)

        st.markdown("---")

    # Arrival Map Section
    st.markdown("### 🗺️ State-wise Commodity Arrival Map")
    arrival_commodity = st.selectbox(
        "Select Commodity for Arrival Visualization",
        options=sorted(df['Commodity'].unique()),
        key="arrival_commodity"
    )

    arrival_df = df[df['Commodity'] == arrival_commodity]
    arrival_by_state = arrival_df.groupby('State')['Commodity Arrivals'].sum().reset_index()

    merged_arrival = india_gdf.copy()
    merged_arrival = merged_arrival.merge(arrival_by_state, on='State', how='left')
    merged_arrival['Display Arrival'] = merged_arrival['Commodity Arrivals'].fillna(0)

    fig_arrival = px.choropleth(
        merged_arrival,
        geojson=merged_arrival.geometry,
        locations=merged_arrival.index,
        color='Display Arrival',
        color_continuous_scale="Blues",
        hover_name='State',
        hover_data={
            'Commodity Arrivals': ':.0f',
            'Display Arrival': False
        },
        title=f"Total {arrival_commodity} Arrivals by State",
        labels={'Commodity Arrivals': 'Total Arrivals'}
    )

    fig_arrival.update_geos(
        fitbounds="locations",
        visible=False,
        showcoastlines=False,
        showland=True,
        landcolor="rgb(240, 240, 240)"
    )

    fig_arrival.update_layout(
        height=600,
        margin={"r": 0, "t": 50, "l": 0, "b": 0},
        coloraxis_colorbar=dict(
            title="Arrivals",
            ticks="outside"
        )
    )

    st.plotly_chart(fig_arrival, use_container_width=True)

    st.markdown("""
    <div style="background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-top: 10px;">
        <b>Note:</b> States with no data for the selected commodity will appear in light gray.
    </div>
    """, unsafe_allow_html=True)



# Tab 3: Market Stats
with tab3:
    # Filters directly in the tab instead of sidebar
    st.markdown("### Filters")
    col_filters = st.columns(3)
    
    with col_filters[0]:
        states_tab3 = st.multiselect("Select State(s)", df['State'].unique(), key="states_tab3")
    
    apmcs_tab3 = []
    commodities_tab3 = []
    
    with col_filters[1]:
        if states_tab3:
            apmc_options = df[df['State'].isin(states_tab3)]['APMC'].unique()
        else:
            apmc_options = df['APMC'].unique()
        apmcs_tab3 = st.multiselect("Select APMC(s)", apmc_options, key="apmcs_tab3")
    
    with col_filters[2]:
        if states_tab3 and apmcs_tab3:
            commodity_options = df[(df['State'].isin(states_tab3)) & 
                                  (df['APMC'].isin(apmcs_tab3))]['Commodity'].unique()
        elif states_tab3:
            commodity_options = df[df['State'].isin(states_tab3)]['Commodity'].unique()
        elif apmcs_tab3:
            commodity_options = df[df['APMC'].isin(apmcs_tab3)]['Commodity'].unique()
        else:
            commodity_options = df['Commodity'].unique()
        commodities_tab3 = st.multiselect("Select Commodity(ies)", commodity_options, key="commodities_tab3")
    
    # Apply filters for tab 3
    filtered_df_tab3 = df.copy()
    if states_tab3:
        filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['State'].isin(states_tab3)]
    if apmcs_tab3:
        filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['APMC'].isin(apmcs_tab3)]
    if commodities_tab3:
        filtered_df_tab3 = filtered_df_tab3[filtered_df_tab3['Commodity'].isin(commodities_tab3)]
    
    st.markdown("---")
    
    # Display Market Stats content
    st.markdown("### 🚛 Commodity Arrivals Over Time")
    fig3 = px.area(filtered_df_tab3, x='Date', y='Commodity Arrivals', color='Commodity',
                title='Commodity Arrivals Over Time')
    st.plotly_chart(fig3, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### 📌 Summary Statistics")
        st.write(filtered_df_tab3.describe())
    
    with col2:
        st.markdown("### APMC Comparison")
        if not filtered_df_tab3.empty:
            apmc_comparison = filtered_df_tab3.groupby('APMC')['Modal Price'].agg(['mean', 'min', 'max']).reset_index()
            fig4 = px.bar(apmc_comparison, x='APMC', y='mean', 
                         error_y='max', error_y_minus='min',
                         title='Average Price by APMC (with Min/Max range)',
                         labels={'mean': 'Average Modal Price'})
            st.plotly_chart(fig4, use_container_width=True)

    # Add basic statistical insights
    st.markdown("---")
    st.markdown("### 📊 Statistical Insights")

    if not filtered_df_tab3.empty:
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Price Statistics")
            # Calculate some basic statistics
            price_stats = {
                "Mean Price": filtered_df_tab3["Modal Price"].mean(),
                "Median Price": filtered_df_tab3["Modal Price"].median(),
                "Price Standard Deviation": filtered_df_tab3["Modal Price"].std(),
                "Price Range": filtered_df_tab3["Modal Price"].max() - filtered_df_tab3["Modal Price"].min(),
                "Price Coefficient of Variation": (filtered_df_tab3["Modal Price"].std() / filtered_df_tab3["Modal Price"].mean()) * 100 if filtered_df_tab3["Modal Price"].mean() != 0 else 0
            }
            
            # Display statistics
            for stat, value in price_stats.items():
                st.metric(label=stat, value=f"{value:.2f}")
        
        with col2:
            st.markdown("#### Arrival Statistics")
            if "Commodity Arrivals" in filtered_df_tab3.columns:
                # Calculate arrival statistics
                arrival_stats = {
                    "Mean Arrival": filtered_df_tab3["Commodity Arrivals"].mean(),
                    "Median Arrival": filtered_df_tab3["Commodity Arrivals"].median(),
                    "Total Arrivals": filtered_df_tab3["Commodity Arrivals"].sum(),
                    "Maximum Single-Day Arrival": filtered_df_tab3["Commodity Arrivals"].max()
                }
                
                # Display statistics
                for stat, value in arrival_stats.items():
                    st.metric(label=stat, value=f"{value:.2f}")

# Footer
st.markdown("---")
st.markdown("""
    <div style="text-align: center">
        <p>APMC Data Explorer Dashboard | Created with Streamlit</p>
    </div>
""", unsafe_allow_html=True)