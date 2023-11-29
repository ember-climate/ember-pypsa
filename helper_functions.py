import numpy as np
import pandas as pd
import random


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



