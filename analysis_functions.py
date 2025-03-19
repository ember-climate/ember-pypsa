import pandas as pd
import pypsa 
import seaborn as sns
import plotly.express as px


def capacity_by_country(network):
    capacity_by_fuel = network.generators.groupby(["carrier","bus"])["p_nom"].sum().reset_index()
    return capacity_by_fuel
    
def generation_by_fuel_by_country(network):
    p_by_carrier = network.generators_t.p.groupby([network.generators.carrier, network.generators.bus], axis=1).sum()
    generation_by_fuel_by_country = p_by_carrier.sum().reset_index().rename(columns={0:'MWh'})
    generation_by_fuel_by_country['TWh'] = generation_by_fuel_by_country['MWh']/1000000
    gen_wide = generation_by_fuel_by_country.pivot(index='bus', columns='carrier', values='TWh')
    
    # add in reservoir generation
    reservoir_gen = network.storage_units_t.p_dispatch.filter(like='Reservoir').sum().reset_index().rename(columns={0:'Reservoir'})
    reservoir_gen['Reservoir'] = reservoir_gen['Reservoir']/1000000
    reservoir_gen['bus'] = reservoir_gen['StorageUnit'].apply(lambda x:x.split('_')[0])
    gen_wide = gen_wide.merge(right=reservoir_gen[['bus','Reservoir']], how='left', on='bus')
    
    # add total gen
    gen_wide.fillna(0, inplace = True)
    gen_wide = gen_wide.set_index('bus', drop=True)
    gen_wide['total_generation_twh'] = gen_wide.sum(axis=1)
    
    # add in total demand
    demand = network.loads_t.p.sum().reset_index().rename(columns={0:'demand', 'Load':'bus'})
    demand['demand'] = demand['demand']/1000000
    gen_wide = gen_wide.merge(right=demand, how='left', left_on='bus', right_on='bus')
    return gen_wide

def generation_by_unit(network):
    p_by_unit = network.generators_t.p.sum()/1000000
    return p_by_unit

def interconnection_flows(network):
    # add in net imports
    links = network.links_t.p0.sum() / 1000000
    links = links.reset_index().rename(columns={0:'TWh'})
    links['from'] = links['Link'].apply(lambda x:x.split('_')[1] if x.split('_')[0] == 'link' else "h2_link")
    links['to'] = links['Link'].apply(lambda x: x.split('_')[2] if x.split('_')[0] == 'link' else "h2_link")
    from_grouped = links.groupby("from")['TWh'].sum().rename('from')
    to_grouped = links.groupby("to")['TWh'].sum().rename('to')
    net_flows = pd.concat([from_grouped, to_grouped], axis=1)
    net_flows['net_imports'] = net_flows['to'] - net_flows['from']
    return links, net_flows

def prices(network):
    return network.buses_t.marginal_price


def res_curtailment(network):
    # curtailment calcs
    pv_potential = network.generators_t['p_max_pu'].filter(like='_PV')
    wind_potential = network.generators_t['p_max_pu'].filter(regex='_Wind').drop(network.generators_t['p_max_pu'].filter(regex='_Wind_offshore').columns, axis=1)
    wind_offshore_potential = network.generators_t['p_max_pu'].filter(regex='_Wind_offshore')

    p_by_carrier = network.generators_t.p.groupby([network.generators.carrier, network.generators.bus], axis=1).sum()
    for v in pv_potential.columns.to_list():
        pv_potential.loc[:, v] = pv_potential.loc[:, v] * network.generators[network.generators.carrier=='PV'].loc[v,'p_nom']
    for v in wind_potential.columns.to_list():
        wind_potential.loc[:, v] = wind_potential.loc[:, v] * network.generators[network.generators.carrier=='Wind'].loc[v,'p_nom']
    for v in wind_offshore_potential.columns.to_list():
        wind_offshore_potential.loc[:, v] = wind_offshore_potential.loc[:, v] * network.generators[network.generators.carrier=='Wind offshore'].loc[v,'p_nom']

    pv_potential.columns = pv_potential.columns.str.replace(r'_PV', '')
    wind_potential.columns = wind_potential.columns.str.replace(r'_Wind$', '')
    wind_offshore_potential.columns = wind_offshore_potential.columns.str.replace(r'_Wind_offshore$', '')
    solar_curtailment = pv_potential - p_by_carrier.iloc[:, p_by_carrier.columns.get_level_values(0) == 'PV'].\
                                       droplevel(level=0, axis=1)
    onshore_curtailment = wind_potential - p_by_carrier.iloc[:,
                                           p_by_carrier.columns.get_level_values(0) == 'Wind'].\
                                           droplevel(level=0,axis=1)
    offshore_curtailment = wind_offshore_potential - p_by_carrier.iloc[:, p_by_carrier.columns.
                                                     get_level_values(0) == 'Wind offshore'].\
                                                     droplevel(level=0, axis=1)

    annual_curtailment = pd.concat([solar_curtailment.sum().to_frame(name='PV_curtailment_twh') / 1000000,
                                    onshore_curtailment.sum().to_frame(name='Wind_curtailment_twh') / 1000000,
                                    offshore_curtailment.sum().to_frame(name='Wind_offshore_curtailment_twh') / 1000000],
                                   axis=1)
    annual_curtailment['PV_potential_twh'] = pv_potential.sum() / 1000000
    annual_curtailment['Wind_potential_twh'] = wind_potential.sum() / 1000000
    annual_curtailment['Wind_offshore_potential_twh'] = wind_offshore_potential.sum() / 1000000
    return annual_curtailment

def storage_outputs(network):
    state_of_charge = network.storage_units_t.state_of_charge
    storage_power_dispatch = network.storage_units_t.p_dispatch
    return state_of_charge, storage_power_dispatch

def hourly_dsf(network):
    return network.generators_t.p.filter(like='_DSR')

def generation_by_hour_eu(network):
    # hourly eu generation by fuel
    generation_t = network.generators_t.p.groupby([network.generators.carrier, network.generators.bus], axis=1).sum()
    eu_hourly_generation = generation_t.loc[:, ~generation_t.columns.get_level_values(1).isin(
        ['Albania', 'BosniaHerzegovina', 'Kosovo', 'Moldova', 'Montenegro', 'NorthMacedonia', 'Norway', 'Serbia',
         'Switzerland', 'UK', 'Ukraine'])]
    eu_hourly_by_fuel = eu_hourly_generation.groupby('carrier', axis=1).sum()
    return eu_hourly_by_fuel

def generation_by_hour_by_country(network):
    # hourly generation by fuel by country
    generation_t = network.generators_t.p.groupby([network.generators.carrier, network.generators.bus], axis=1).sum()
    hourly_gen = generation_t.stack(level=[0, 1]).reset_index(level=[1, 2]).rename(columns={0: 'MWh'})
    return hourly_gen

def calculate_custom_risk_metrics(network, internal_data):
    # Placeholder function to calculate custom risk metrics based on internal data
    # Implement the logic to calculate custom risk metrics
    pass

def generate_plant_specific_risk_profiles(network, plant_data):
    # Placeholder function to generate plant-specific risk profiles
    # Implement the logic to generate plant-specific risk profiles
    pass

def perform_scenario_based_risk_assessment(network, scenario_data):
    # Placeholder function to perform scenario-based risk assessment
    # Implement the logic to perform scenario-based risk assessment
    pass

def calculate_npv(cash_flows, discount_rate):
    npv = sum(cf / (1 + discount_rate) ** t for t, cf in enumerate(cash_flows, start=1))
    return npv

def visualize_risk_assessment_results(risk_assessment_data):
    # Placeholder function to visualize risk assessment results using seaborn and plotly
    # Implement the logic to visualize risk assessment results
    pass
