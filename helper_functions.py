import numpy as np
import pandas as pd
import random
import google.auth
import pygsheets
import sys
import tensorflow as tf
import torch
import dask.dataframe as dd
from dask import delayed


def get_input_data_sources(regions:list, data:list) -> list:
    data_sources = [i[1] for i in zip(regions, data) if i[0] == True]
    if "" in data_sources:
        data_sources.remove("")
        print("Warning: check countries selected have valid input data sources. Empty string in input data.")
    return data_sources
    
def load_data(input_data_sources:list, load_data_source:str) -> dict:
    input_data_dicts = []
    
    for source in input_data_sources:
        if load_data_source == 'LOCAL':
            input_data_dicts.append(load_data_locally(source))
        if load_data_source == 'REMOTE':
            input_data_dicts.append(load_data_from_google_sheet(source))
        if load_data_source == 'REALTIME':
            input_data_dicts.append(load_real_time_data(source))
        if load_data_source not in ['REMOTE', 'LOCAL', 'REALTIME']:
            print("Please enter input as either 'LOCAL', 'REMOTE', or 'REALTIME'")
    data_dict = concat_data(input_data_dicts)
    return data_dict

def concat_data(input_data_dicts:dict) -> dict:
    data_dict = {}
    for sheet_dict in input_data_dicts:
        for tab in sheet_dict.keys():
            new_df = sheet_dict[tab]
            # remove empty column headers
            if "" in new_df.columns:
                new_df = new_df.drop([""], axis=1)
            # if tab doesnt exist, fill with df from sheet_dict
            if tab not in data_dict.keys():
                data_dict[tab] = new_df
            # if tab already there, append to existing df
            else:
                existing_df = data_dict[tab]
                # if timeseries, concat horizontally 
                if "timeseries" in tab:
                    updated_df = pd.concat([existing_df, new_df], axis=1)
                else:
                    updated_df = pd.concat([existing_df, new_df], axis=0)
                data_dict[tab] = updated_df
    return data_dict

    
def load_data_locally(data_file):
    dfs = pd.read_excel(data_file, sheet_name=None, index_col=0, parse_dates=True)
    return dfs

def load_data_from_google_sheet(url):
    # worksheet details
    sheets_scope = [ "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    credentials, _ = google.auth.default(scopes=sheets_scope)
    gs = pygsheets.authorize(custom_credentials=credentials)
    sheet = gs.open_by_url(url)

    ## read worksheets
    dfs = {}
    sheet_names = [s.title for s in sheet.worksheets()]
    for wsheet_title in sheet_names:
        df = sheet.worksheet_by_title(wsheet_title).get_as_df(include_tailing_empty=False)
        new_index = df.iloc[:, 0]
        df.set_index(new_index, inplace=True)
        df = df.iloc[:, 1:]
        if df.index.name == 't':
            df.index = pd.to_datetime(df.index, format="%d/%m/%Y %H:%M:%S")
        dfs[wsheet_title] = df

    # if googlesheets import used, save input worksheets to repo
    doc_name = sheet.title
    with pd.ExcelWriter('INPUT-' + doc_name + '.xlsx', engine='openpyxl') as writer:
        for wks in sheet.worksheets():
            df = wks.get_as_df()
            df.to_excel(writer, sheet_name=wks.title, index=False)
    return dfs

def load_real_time_data(source):
    # Placeholder function to load real-time data from a specified source
    # Implement the logic to load real-time data from the source
    pass

def train_ml_models(data):
    # Placeholder function to train machine learning models using TensorFlow and PyTorch
    # Implement the logic to train models using the provided data
    pass

def integrate_ml_predictions(network, predictions):
    # Placeholder function to integrate machine learning model predictions into the PyPSA network
    # Implement the logic to integrate predictions into the network
    pass

def dask_parallel_computing(data):
    # Placeholder function to use Dask for parallel computing in data loading and processing
    # Implement the logic to use Dask for parallel computing
    pass

def add_network_components(network, input_dict, p_min_nuclear):
    print("adding links")
    links = input_dict['links']
    network.madd("Link", links.index,
                 bus0=links['bus0'].tolist(), bus1=links['bus1'].tolist(),
                 p_nom=links['p_nom'].tolist(), p_max_pu=links['p_max_pu'].to_list())
    
    gen_cbf = input_dict['gen_cbf']
    network.madd("Generator", gen_cbf.index, suffix='_CBF', carrier='CBF',
                 bus=gen_cbf.index.tolist(), p_nom=gen_cbf['p_nom'].to_list(), p_nom_extendable=False,
                 marginal_cost=gen_cbf['marginal_cost'].to_list())
    
    print("adding loads")
    load = input_dict['load_timeseries']
    network.madd("Load", load.columns, bus=load.columns, p_set=load)
    load_hydrogen = input_dict['load_hydrogen_timeseries']
    network.madd("Load", load_hydrogen.columns, bus=load_hydrogen.columns, p_set=load_hydrogen, carrier='Hydrogen')

    print("adding RES generation")
    gen_pv = input_dict['gen_pv']
    pv = input_dict['pv_timeseries']
    network.madd('Generator',
                 gen_pv['bus'],
                 suffix='_PV',
                 bus=gen_pv['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_pv['p_nom'].to_list(),
                 carrier='PV',
                 marginal_cost=gen_pv['marginal_cost'].to_list(),
                 p_max_pu=pv)

    gen_wind = input_dict['gen_wind']
    wind = input_dict['wind_timeseries']
    network.madd('Generator',
                 gen_wind['bus'],
                 suffix='_Wind',
                 bus=gen_wind['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_wind['p_nom'].to_list(),
                 carrier='Wind',
                 marginal_cost=gen_wind['marginal_cost'].to_list(),
                 p_max_pu=wind)

    gen_wind_offshore = input_dict['gen_wind_offshore']
    wind_offshore = input_dict['wind_offshore_timeseries']
    network.madd('Generator',
                 gen_wind_offshore['bus'],
                 suffix='_Wind_offshore',
                 bus=gen_wind_offshore['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_wind_offshore['p_nom'].to_list(),
                 carrier='Wind offshore',
                 marginal_cost=gen_wind_offshore['marginal_cost'].to_list(),
                 p_max_pu=wind_offshore)

    print("adding fossil fuel generation")
    gen_gas = input_dict['gen_gas']
    network.madd('Generator',
                 gen_gas.index,
                 bus=gen_gas['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_gas['p_nom'].to_list(),
                 carrier=gen_gas['carrier'].to_list(),
                 marginal_cost=gen_gas['marginal_cost'].to_list(),
                 efficiency=gen_gas['efficiency'].to_list()
                 )
    gen_oil = input_dict['gen_oil']
    network.madd('Generator',
                 gen_oil.index,
                 bus=gen_oil['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_oil['p_nom'].to_list(),
                 carrier='Oil',
                 marginal_cost=gen_oil['marginal_cost'].to_list(),
                 efficiency=gen_oil['efficiency'].to_list()
                 )
    gen_coal = input_dict['gen_coal']
    network.madd('Generator',
                 gen_coal.index,
                 bus=gen_coal['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_coal['p_nom'].to_list(),
                 carrier=gen_coal['carrier'].to_list(),
                 marginal_cost=gen_coal['marginal_cost'].to_list(),
                 efficiency=gen_coal['efficiency'].to_list()
                 )
    print("adding bio, hydro + nuclear")
    gen_nuclear = input_dict['gen_nuclear']
    chp = input_dict['chp_timeseries']
    nuclear_p_max_time_series, nuclear_p_min_time_series = create_nuclear_timeseries(chp, gen_nuclear, p_min_nuclear)
    network.madd('Generator',
                 gen_nuclear.index,
                 bus=gen_nuclear['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_nuclear['p_nom'].to_list(),
                 carrier='Nuclear',
                 marginal_cost=gen_nuclear['marginal_cost'].to_list(),
                 efficiency=gen_nuclear['efficiency'].to_list(),
                 p_max_pu=nuclear_p_max_time_series,
                 p_min_pu=nuclear_p_min_time_series
                 )
    gen_biomass = input_dict['gen_biomass']
    network.madd('Generator',
                 gen_biomass.index,
                 bus=gen_biomass['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_biomass['p_nom'].to_list(),
                 carrier=gen_biomass['carrier'].to_list(),
                 marginal_cost=gen_biomass['marginal_cost'].to_list(),
                 efficiency=gen_biomass['efficiency'].to_list(),
                 p_max_pu=gen_biomass['p_max_pu'].to_list()
                 )
    gen_biogas = input_dict['gen_biogas']
    network.madd('Generator',
                 gen_biogas['bus'],
                 suffix='_Biogas',
                 bus=gen_biogas['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_biogas['p_nom'].to_list(),
                 carrier='Biogas',
                 marginal_cost=gen_biogas['marginal_cost'].to_list(),
                 efficiency=gen_biogas['efficiency'].to_list(),
                 p_max_pu=gen_biogas['p_max_pu'].to_list()
                 )
    gen_ror = input_dict['gen_ror']
    ror = input_dict['ror_timeseries']
    network.madd('Generator',
                 gen_ror['bus'],
                 suffix='_ROR',
                 bus=gen_ror['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_ror['p_nom'].to_list(),
                 carrier=gen_ror['carrier'].to_list(),
                 marginal_cost=gen_ror['marginal_cost'].to_list(),
                 p_max_pu=ror
                 )
    gen_other_res = input_dict['gen_other_res']
    network.madd('Generator',
                 gen_other_res['bus'],
                 suffix='_OtherRES',
                 bus=gen_other_res['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_other_res['p_nom'].to_list(),
                 carrier='Other RES',
                 marginal_cost=gen_other_res['marginal_cost'].to_list(),
                 p_max_pu=gen_other_res['p_max_pu'].to_list()
                 )
    gen_dsr = input_dict['gen_dsr']
    network.madd('Generator',
                 gen_dsr['bus'],
                 suffix='_DSR',
                 bus=gen_dsr['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_dsr['p_nom'].to_list(),
                 carrier='DSR',
                 marginal_cost=gen_dsr['marginal_cost'].to_list(),
                 p_max_pu=gen_dsr['p_max_pu'].to_list()
                 )

    print("adding CHPs")
    gen_gas_chp = input_dict['gen_gas_chp']
    gen_coal_chp = input_dict['gen_coal_chp']
    gen_oil_chp = input_dict['gen_oil_chp']
    gen_res_chp = input_dict['gen_res_chp']
    gas_chp_timeseries, coal_chp_timeseries, oil_chp_timeseries, res_chp_timeseries = \
        create_chp_timeseries(chp,gen_gas_chp,gen_coal_chp,gen_oil_chp, gen_res_chp)

    network.madd('Generator',
                 gen_gas_chp.index,
                 bus=gen_gas_chp['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_gas_chp['p_nom'].to_list(),
                 carrier=gen_gas_chp['carrier'].to_list(),
                 marginal_cost=gen_gas_chp['marginal_cost'].to_list(),
                 p_max_pu=gas_chp_timeseries,
                 p_min_pu=0.9 * gas_chp_timeseries,
                 efficiency=gen_gas_chp['efficiency'].to_list()
                 )

    network.madd('Generator',
                 gen_coal_chp.index,
                 bus=gen_coal_chp['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_coal_chp['p_nom'].to_list(),
                 carrier=gen_coal_chp['carrier'].to_list(),
                 marginal_cost=gen_coal_chp['marginal_cost'].to_list(),
                 p_max_pu=coal_chp_timeseries,
                 p_min_pu=0.9 * coal_chp_timeseries,
                 efficiency=gen_coal_chp['efficiency'].to_list()
                 )

    network.madd('Generator',
                 gen_oil_chp.index,
                 bus=gen_oil_chp['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_oil_chp['p_nom'].to_list(),
                 carrier=gen_oil_chp['carrier'].to_list(),
                 marginal_cost=gen_oil_chp['marginal_cost'].to_list(),
                 p_max_pu=oil_chp_timeseries,
                 p_min_pu=0.9 * oil_chp_timeseries,
                 efficiency=gen_oil_chp['efficiency'].to_list()
                 )

    network.madd('Generator',
                 gen_res_chp.index,
                 bus=gen_res_chp['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_res_chp['p_nom'].to_list(),
                 carrier=gen_res_chp['carrier'].to_list(),
                 marginal_cost=gen_res_chp['marginal_cost'].to_list(),
                 p_max_pu=res_chp_timeseries,
                 p_min_pu=0.9 * res_chp_timeseries,
                 efficiency=gen_res_chp['efficiency'].to_list()
                 )
    gen_bio_chp = input_dict['gen_bio_chp']
    chp_bio = input_dict['chp_bio_timeseries']
    network.madd('Generator',
                 gen_bio_chp.index,
                 bus=gen_bio_chp['bus'].to_list(),
                 p_nom_extendable=False,
                 p_nom=gen_bio_chp['p_nom'].to_list(),
                 carrier=gen_bio_chp['carrier'].to_list(),
                 marginal_cost=gen_bio_chp['marginal_cost'].to_list(),
                 p_max_pu=chp_bio,
                 p_min_pu=chp_bio * 0.9,
                 efficiency=gen_bio_chp['efficiency'].to_list()
                 )
    print("adding storage")
    st_hps = input_dict['st_hps']
    network.madd("StorageUnit", st_hps.index, bus=st_hps['bus'].tolist(), carrier=st_hps['carrier'].tolist(),
                 p_nom=st_hps['p_nom'].tolist(), p_nom_extendable=False, max_hours=st_hps['max_hours'].to_list(),
                 p_max_pu=st_hps['p_max_pu'].tolist(),
                 efficiency_dispatch=st_hps['efficiency_dispatch'].tolist(),
                 standing_loss=st_hps['standing_loss'].tolist())

    st_reservoir = input_dict['st_reservoir']
    dispatch_reservoir = input_dict['dispatch_reservoir_timeseries']
    inflow_reservoir = input_dict['inflow_reservoir_timeseries']
    network.madd("StorageUnit", st_reservoir.index , bus=st_reservoir['bus'].tolist(),
                 carrier=st_reservoir['carrier'].tolist(),
                 p_nom=st_reservoir['p_nom'].tolist(), p_nom_extendable=False,
                 max_hours=st_reservoir['max_hours'].to_list(),
                 p_max_pu=dispatch_reservoir,
                 p_min_pu = 0,
                 efficiency_dispatch=st_reservoir['efficiency_dispatch'].tolist(),
                 efficiency_store=st_reservoir['efficiency_store'].tolist(),
                 standing_loss=0,
                 cyclic_state_of_charge = True,
                 state_of_charge_initial=st_reservoir['state_of_charge_initial'].tolist(),
                 inflow = inflow_reservoir
                 )
    st_battery = input_dict['st_battery']
    network.madd("StorageUnit", st_battery.index, bus=st_battery['bus'].tolist(), carrier=st_battery['carrier'].tolist(),
                 p_nom=st_battery['p_nom'].tolist(), p_nom_extendable=False, max_hours=st_battery['max_hours'].to_list(),
                 p_max_pu=st_battery['p_max_pu'].tolist(),
                 efficiency_dispatch=st_battery['efficiency_dispatch'].tolist(),
                 standing_loss=st_battery['standing_loss'].tolist())
    st_other = input_dict['st_other']
    network.madd("StorageUnit", st_other.index, bus=st_other['bus'].tolist(), carrier=st_other['carrier'].tolist(),
                 p_nom=st_other['p_nom'].tolist(), p_nom_extendable=False, max_hours=st_other['max_hours'].to_list(),
                 p_max_pu=st_other['p_max_pu'].tolist(),
                 efficiency_dispatch=st_other['efficiency_dispatch'].tolist(),
                 standing_loss=st_other['standing_loss'].tolist())
    links_electrolysis = input_dict['links_electrolysis']
    network.madd("Link", links_electrolysis.index,
                 bus0=links_electrolysis['bus0'].tolist(), bus1=links_electrolysis['bus1'].tolist(),
                 p_nom=links_electrolysis['p_nom'].tolist(),
                 p_nom_extendable=links_electrolysis['p_nom_extendable'].tolist(),
                 carrier=links_electrolysis['carrier'].tolist(),
                 efficiency=links_electrolysis['efficiency'].tolist())
    st_hydrogen = input_dict['st_hydrogen']
    network.madd("Store", st_hydrogen.index, bus=st_hydrogen['bus'].tolist(), carrier=st_hydrogen['carrier'].tolist(),
                 e_nom=st_hydrogen['e_nom'].tolist(), e_nom_extendable=False, e_cyclic=True)

    return network


def create_chp_timeseries(chp, gen_gas_chp, gen_coal_chp, gen_oil_chp, gen_res_chp):
    # create chp timeseries based on country temperature profile
    gas_chp_timeseries=chp_unit_profile(chp, gen_gas_chp)
    coal_chp_timeseries=chp_unit_profile(chp, gen_coal_chp)
    oil_chp_timeseries=chp_unit_profile(chp, gen_oil_chp)
    res_chp_timeseries=chp_unit_profile(chp, gen_res_chp)
    return gas_chp_timeseries, coal_chp_timeseries, oil_chp_timeseries, res_chp_timeseries

def create_nuclear_timeseries(chp, gen_nuclear, p_min_nuclear):
    # create nuclear time series to replicate maintenance profile
    nuclear_p_max_time_series, nuclear_p_min_time_series = apply_nuclear_outages(chp, gen_nuclear,
                                                                                 nuclear_p_min=p_min_nuclear,
                                                                                 french_nucl_cf=0.85,
                                                                                 other_nucl_cf=0.95)
    return nuclear_p_max_time_series, nuclear_p_min_time_series


def apply_nuclear_outages(source_for_time_index:pd.DataFrame, gen_nuclear:pd.DataFrame, nuclear_p_min: float, french_nucl_cf:float, other_nucl_cf:float) -> pd.DataFrame:
    """
    This function creates a generation profile for nuclear units (using one capacity factor for France, and another for all other countries)     and sets the level of capacity generation available - either 1 or 0, replicating an annual maintenance schedule

    Parameters
    ----------
        source_for_time_index: Pandas.DataFrame
            df used to copy the time index for the nuclear outages df
        gen_nuclear: Pandas.DataFrame
            Dataframe with nuclear unit information
        nuclear_p_min: float
            minimum generation level (outside maintenance window)
        french_nucl_cf: float
            capacity factor of French units - determines level of downtime
        other_nucl_cf: float
            capacity factor of countries other than France units - determines level of downtime

    Returns
    -------
        pandas.DataFrame:
            nuclear p_max_pu time series for all units
        pandas.DataFrame:
            nuclear p_min_pu time series for all units
    """
    nuclear_max_timeseries = pd.DataFrame(index=source_for_time_index.index, columns=gen_nuclear.bus)
    nuclear_max_timeseries = nuclear_max_timeseries.apply(func=apply_nuclear_outage_profile, args=(french_nucl_cf,other_nucl_cf, source_for_time_index.index),     axis=0)
    nuclear_max_timeseries.columns = gen_nuclear.index
    # for the minimum series, set equal to nuclear_p_min when p_max = 1
    nuclear_min_timeseries = nuclear_max_timeseries.copy()
    nuclear_min_timeseries[nuclear_min_timeseries == 1] = nuclear_p_min
    return nuclear_max_timeseries, nuclear_min_timeseries


def apply_nuclear_outage_profile(column:pd.Series, french_nucl_cf:float, other_nucl_cf:float, index_timeseries:pd.Series) -> pd.Series:
    """
    This function applies the nuclear outage profile to each unit (column) in nuclear unit generation dataframe

    Parameters
    ----------
        column: Pandas.Series
            nuclear unit to apply outage function to
        french_nucl_cf: float
            capacity factor of French units - determines level of downtime
        other_nucl_cf: float
            capacity factor of countries other than France units - determines level of downtime
        index_timeseries: Pandas.Series
            Dataframe with nuclear unit information

    Returns
    -------
        pandas.Series:
            nuclear p_max_pu time series for unit
    """
    country = column.name
    # create nuclear outage profile for French reactors
    if country == 'France':
        nuclear_time_series = create_maintenance_profile(french_nucl_cf)
    else:
        nuclear_time_series = create_maintenance_profile(other_nucl_cf)
    return pd.Series(index=index_timeseries, data=nuclear_time_series, name=country)



def chp_unit_profile(chp:pd.DataFrame, original_df:pd.DataFrame) -> pd.DataFrame:
    """
    This function creates a chp profile for each unit, based on their location using the existing data in chp. The data in chp is derived
    from atlite temperature profiles per country, where chp output is scaled to match the temperature (so chp=1 corresponds to minimum
    temperatures, and chp=0 corresponds to maximum). 

    Parameters
    ----------
        chp: Pandas.DataFrame
            country CHP profiles
        original_df: Pandas.DataFrame
            Dataframe with unit information

    Returns
    -------
        pandas.DataFrame:
            unit CHP time-series
    """
    chp_timeseries = pd.DataFrame(data=chp,columns=original_df.bus)
    chp_timeseries.columns = original_df.index
    return chp_timeseries


def create_maintenance_profile(cf:float) ->list[float]:
    """
    This function creates a maintenance profile for nuclear units, creating a timeseries with 1 and 0 indicating full generation or downtime     respectively

    Parameters
    ----------
        cf: float
            annual average capacity factor of nuclear units
    Returns
    -------
        list[float]:
            hourly p_max_pu of nuclear unit
    """
    # create binary nuclear maintenance profile 
    hours_out = (1-cf)*(365*24)
    values = [1]*24*365
    while sum(values) >= cf*365*24:
        # starting point between March & Oct
        start_index = random.randint(np.floor(24*365*0.25),np.floor(24*365*0.75))
        # minimum duration = 1 week, max = 1 month
        duration = random.randint(7*24,31*24)
        end_index = start_index + duration
        sub_set = values[start_index:end_index]
        # if maintenance has already been scheduled during chosen time (ie if there are 0's in the subset), pick again
        if 0 not in sub_set:
            values[start_index:end_index] = [0]*duration
    return values



