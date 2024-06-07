import streamlit as st
import pandas as pd
import plotly.graph_objects as go

# Load the compute.csv file
file_path = 'compute.csv'
compute_df = pd.read_csv(file_path)

# Helper function to clean and convert price fields
def clean_price(price):
    if isinstance(price, str):
        return float(price.replace('$', '').replace(',', '').strip())
    return float(price)

# Applying the cleaning function to the necessary columns
compute_df['ASP $'] = compute_df['ASP $'].apply(clean_price)
compute_df['Price/Hr Spot'] = compute_df['Price/Hr Spot'].apply(lambda x: clean_price(x) if pd.notnull(x) else 0)
compute_df['Price/Hr OnDemand'] = compute_df['Price/Hr OnDemand'].apply(lambda x: clean_price(x) if pd.notnull(x) else 0)

def calculate_tco(gpu_name, deployment_term, data_center_cost_per_month, network_cost_per_month,
                  rack_cost_setup, server_cost, switch_cost, server_power, switch_power,
                  server_ru, switch_ru, gpus_per_server, servers_per_rack,
                  duty_cycle, electricity_cost_per_kwhr, data_center_pue, platform_cut):

    # Calculate total GPUs
    total_gpus = gpus_per_server * servers_per_rack
    
    # Extract GPU details from the dataframe
    gpu = compute_df[compute_df['Card'] == gpu_name].iloc[0]
    
    gpu_capex = total_gpus * gpu['ASP $']
    rack_capex = rack_cost_setup + (servers_per_rack * server_cost) + switch_cost
    capex_total = gpu_capex + rack_capex
    capex_total_per_month = capex_total / (deployment_term * 12)

    power_gpu = total_gpus * gpu['Power (W)']
    power_max_rack_limit = servers_per_rack * server_power + switch_power
    opex_power = (power_gpu * duty_cycle / 100 + power_max_rack_limit) * electricity_cost_per_kwhr * 24 * 30 / 1000 * data_center_pue
    opex_data_center = data_center_cost_per_month
    opex_networking = network_cost_per_month
    opex_total = opex_power + opex_data_center + opex_networking
    opex_total_per_month = opex_total

    tco_total_per_month = capex_total_per_month + opex_total_per_month
    tco_per_hour_per_card = tco_total_per_month / (total_gpus * 30 * 24)

    revenue_per_month = (duty_cycle / 100) * total_gpus * 24 * 30 * gpu['Price/Hr OnDemand'] * (1 - platform_cut / 100)
    profit_per_month_per_rack = revenue_per_month - tco_total_per_month
    roi_capex_months = capex_total / (revenue_per_month - opex_total_per_month)

    return {
        'CapEx': capex_total,
        'GPU CapEx': gpu_capex,
        'Rack CapEx': rack_capex,
        'CapEx Total per Month': capex_total_per_month,
        'OpEx': opex_total,
        'OpEx Power': opex_power,
        'OpEx Data Center': opex_data_center,
        'OpEx Networking': opex_networking,
        'OpEx Total per Month': opex_total_per_month,
        'TCO Total per Month': tco_total_per_month,
        'TCO per Hour per Card': tco_per_hour_per_card,
        'Revenue per Month': revenue_per_month,
        'Profit per Month per Rack': profit_per_month_per_rack,
        'ROI on CapEx only (months)': roi_capex_months,
        'Total GPUs': total_gpus,
        'Price/Hr OnDemand': gpu['Price/Hr OnDemand']
    }

st.set_page_config(layout="wide")
st.title("Data Center GPU Rack TCO Calculator")

# Sidebar inputs
st.sidebar.header("Input Parameters")
gpu_name = st.sidebar.selectbox("GPU Name", compute_df['Card'].unique())
deployment_term = st.sidebar.number_input("Deployment Term (years)", value=5, min_value=1)
data_center_cost_per_month = st.sidebar.number_input("Data Center Cost per Month ($)", value=200)
network_cost_per_month = st.sidebar.number_input("Network Cost per Month ($)", value=600)
rack_cost_setup = st.sidebar.number_input("Rack Cost Setup ($)", value=1000)
server_cost = st.sidebar.number_input("Server Cost ($)", value=3500)
switch_cost = st.sidebar.number_input("Switch Cost ($)", value=500)
server_power = st.sidebar.number_input("Server Power (W)", value=600)
switch_power = st.sidebar.number_input("Switch Power (W)", value=200)
server_ru = st.sidebar.number_input("Server Rack Units", value=4)
switch_ru = st.sidebar.number_input("Switch Rack Units", value=1)
gpus_per_server = st.sidebar.number_input("GPUs per Server", value=8)
servers_per_rack = st.sidebar.number_input("Servers per Rack", value=4)
duty_cycle = st.sidebar.slider("Duty Cycle (%)", min_value=0, max_value=100, value=70)
electricity_cost_per_kwhr = st.sidebar.number_input("Electricity Cost per kWh ($)", value=0.12)
data_center_pue = st.sidebar.number_input("Data Center PUE", value=1)
platform_cut = st.sidebar.slider("Platform Cut (%)", min_value=0, max_value=100, value=20)

# Calculate TCO
result = calculate_tco(
    gpu_name=gpu_name,
    deployment_term=deployment_term,
    data_center_cost_per_month=data_center_cost_per_month,
    network_cost_per_month=network_cost_per_month,
    rack_cost_setup=rack_cost_setup,
    server_cost=server_cost,
    switch_cost=switch_cost,
    server_power=server_power,
    switch_power=switch_power,
    server_ru=server_ru,
    switch_ru=switch_ru,
    gpus_per_server=gpus_per_server,
    servers_per_rack=servers_per_rack,
    duty_cycle=duty_cycle,
    electricity_cost_per_kwhr=electricity_cost_per_kwhr,
    data_center_pue=data_center_pue,
    platform_cut=platform_cut
)

# Layout for results
left_column, right_column = st.columns(2)

# Display results
with left_column:
    st.subheader("TCO Summary")
    col1, col2 = st.columns(2)
    col1.metric("TCO $/hr", f"${result['TCO per Hour per Card']:.2f}", delta_color="inverse")
    col2.metric("Price/Hr OnDemand", f"${result['Price/Hr OnDemand']:.2f}", delta_color="normal")
    st.metric("OpEx Per Month", f"${result['OpEx Total per Month']:.2f}")
    st.metric("Total CapEx", f"${result['CapEx']:.2f}")
    st.metric("Number of GPUs Total", result['Total GPUs'])

with right_column:
    st.subheader("Payback Over Time")
    months = range(1, deployment_term * 12 + 1)
    cumulative_revenue = [result['Revenue per Month'] * i for i in months]
    cumulative_profit = [result['Profit per Month per Rack'] * i for i in months]
    capex_line = [result['CapEx']] * len(months)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=list(months), y=cumulative_revenue, mode='lines', name='Cumulative Revenue', line=dict(color='green')))
    fig.add_trace(go.Scatter(x=list(months), y=cumulative_profit, mode='lines', name='Cumulative Profit', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=list(months), y=capex_line, mode='lines', name='Total CapEx', line=dict(color='red', dash='dash')))
    
    fig.update_layout(
        xaxis_title='Months',
        yaxis_title='Amount ($)',
        hovermode='x unified'
    )
    
    # Add annotation for payback period
    payback_month = next((i for i, profit in enumerate(cumulative_profit) if profit >= result['CapEx']), None)
    if payback_month:
        fig.add_annotation(
            x=payback_month + 1,
            y=result['CapEx'],
            text=f"Payback Period: {payback_month + 1} months",
            showarrow=True,
            arrowhead=1
        )

    st.plotly_chart(fig)

# Display full results for debugging
st.subheader("Full Results")
st.write(result)
