import numpy as np
import pandas as pd


def apply_country_chp_profile(column,chp):
    # apply country chp profile based on temperature to unit columns
    country = column.name
    chp_series = chp[country]
    return chp_series

def apply_ramping(row):
    # apply gas ramp up and down value
    if row['type'] == 'CC':
        if row['age'] == 'new':
            ramp = 0.65
        elif row['age'] == 'old':
            ramp = 0.55
        else:
            ramp = 0.6
    else:
        if row['age'] == 'new':
            ramp = 0.85
        elif row['age'] == 'old':
            ramp = 0.75
        else:
            ramp = 0.8
    return ramp, ramp

def chp_unit_profile(chp, original_df):
    chp_timeseries = pd.DataFrame(chp,columns=original_df.bus)
    chp_timeseries = chp_timeseries.apply(func=apply_country_chp_profile,  axis=0, args=(chp,))
    chp_timeseries.columns = original_df.index
    return chp_timeseries

def grouped_gas_ramping(gen_gas):
    grouped_gas = gen_gas.groupby(['bus', 'type', 'age']).agg({'carrier':'first','p_nom':sum, 'marginal_cost': 'mean','efficiency':'mean'}).reset_index()
    grouped_gas[['ramp_limit_up','ramp_limit_down']] = grouped_gas[['type','age']].apply(apply_ramping, result_type='expand', axis=1)
    grouped_gas = grouped_gas.set_index(grouped_gas['bus'] + '_' + grouped_gas['type'] + '_' + grouped_gas['age'])
    return grouped_gas
                