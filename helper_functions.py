import numpy as np
import pandas as pd
import random

def apply_country_chp_profile(column,chp):
    # apply country chp profile based on temperature to unit columns
    country = column.name
    chp_series = chp[country]
    return chp_series


def apply_nuclear_outages(chp, gen_nuclear, french_nucl_cf, other_nucl_cf):
    nuclear_max_timeseries = pd.DataFrame(index=chp.index, columns=gen_nuclear.bus)
    nuclear_max_timeseries = nuclear_max_timeseries.apply(func=apply_nuclear_outage_profile, args=(french_nucl_cf,other_nucl_cf, chp.index), axis=0)
    nuclear_max_timeseries.columns = gen_nuclear.index
    return nuclear_max_timeseries

def apply_nuclear_outage_profile(column,french_nucl_cf,other_nucl_cf, index_timeseries):
    country = column.name
    # create nuclear outage profile for French reactors
    if country == 'France':
        nuclear_time_series = create_maintenance_profile(french_nucl_cf)
    else:
        nuclear_time_series = create_maintenance_profile(other_nucl_cf)
    return pd.Series(index=index_timeseries, data=nuclear_time_series, name=country)

def apply_ramping(row):
    # apply gas min_ramp_up time (hours)
    # 3/4 hour start up time for ccgts
    if row['type'] == 'CC':
        if row['age'] == 'new':
            ramp = 3
        else:
            ramp = 4
    # 0 gas cold start time for ocgts
    else:
        ramp=0
    return ramp

def chp_unit_profile(chp, original_df):
    chp_timeseries = pd.DataFrame(chp,columns=original_df.bus)
    chp_timeseries = chp_timeseries.apply(func=apply_country_chp_profile,  axis=0, args=(chp,))
    chp_timeseries.columns = original_df.index
    return chp_timeseries

def create_maintenance_profile(cf):
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
        if 0 not in sub_set:
            values[start_index:end_index] = [0]*duration
    return values

def grouped_gas_ramping(gen_gas):
    grouped_gas = gen_gas.groupby(['bus', 'type', 'age']).agg({'carrier':'first','p_nom':sum, 'marginal_cost': 'mean','efficiency':'mean'}).reset_index()
    grouped_gas['min_up_time'] = grouped_gas[['type','age']].apply(apply_ramping, axis=1)
    grouped_gas = grouped_gas.set_index(grouped_gas['bus'] + '_' + grouped_gas['type'] + '_' + grouped_gas['age'])
    return grouped_gas
                