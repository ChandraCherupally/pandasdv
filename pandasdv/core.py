"""
-----------------
Core validation functions for survey data quality checks.

Includes:
- FLT_LIST
- SR
- MULTI
- GRID
- RANK_CHECK
- OETEXT
- NULL_CHECK
"""

import pandas as pd
import numpy as np
from .io_utils import *


def FLT_LIST(COND=None, LIST=[]):
    """
    Function to filter and list cases based on a condition.
    
    Parameters:
    COND : boolean Series
        Condition to filter the DataFrame.
    LIST : list of str
        List of columns to display in the filtered output.
    """

    from .io_utils import df
    num_cases_read = df.shape[0]
    filtered_df = df[COND]
    num_cases_listed = filtered_df.shape[0]
    if num_cases_listed > 0:
        print(filtered_df[LIST].reset_index(drop=True).to_string(index=False))
    print(f"\nNumber of cases listed: {num_cases_listed} of {num_cases_read}\n")

#### Example
#### FLT_LIST(COND=df['CID'].isna() | (df['CID']<=0), LIST=['CID', 'CID'])


def SR(Rout='QFILTER', QVAR=[], RNG=[], LIST=[]):
    """
    Function to process Single Response variables.
    
    Parameters:
    Rout : str
        Column name for the filter variable.
    QVAR : str
        Column name for the question variable.
    RNG : list of int
        List of valid range values for the question variable.
    LIST : list of str
        List of columns to display in the filtered output.
    """
    print(f"{QVAR}:")
    from .io_utils import df

    if Rout not in df.columns:
        df[Rout] = 1  

    condition_qfilter1 = (df[Rout] == 1) & (df[QVAR].isna() | ~df[QVAR].isin(RNG))
    condition_qfilter0 = (df[Rout] != 1) & ~df[QVAR].isna()
    condition = condition_qfilter1 | condition_qfilter0

    FLT_LIST(condition, [df.columns[0], QVAR] + LIST)
    df.drop(columns=[Rout], inplace=True)

#### Example for filter question
#### df['QFILTER'] = 0
#### df.loc[df['Q30'].between(2,5), 'QFILTER'] = 1
### SR(Rout='QFILTER', QVAR='Q30a', RNG=list(range(1,17)) + [97],LIST=['CID','Q30a','Q30'])

#### Example for Ask all question
#### df['QFILTER'] = 1
#### SR(Rout='QFILTER',QVAR='Q1', RNG=list(range(3,9)), LIST=['CID','Q1'])


def MULTI(Rout='QFILTER', QVAR=[], QEX=[], LIST=[]):
    """
    Function to process Multi question variables with exclusive checks.
    
    Parameters:
    Rout : str
        Column name for the filter variable.
    QVAR : list of str
        List of question variable column names.
    QEX : list of str
        List of exclusive variable column names.
    LIST : list of str
        List of columns to display in the filtered output.
    """

    print(f"{QVAR[0]} to {QVAR[-1]}:")
    from .io_utils import df

    if Rout not in df.columns:
        df[Rout] = 1  

    QVARS_ALL = QVAR + QEX
    df['QCount1'] = df[QVARS_ALL].eq(1).sum(axis=1)
    df['QCount2'] = df[QVARS_ALL].isin([0, 1]).sum(axis=1)
    NR = len(QVARS_ALL)

    # Nothing Selected
    print(f"{QVAR[0]} - Nothing Selected:")
    condition1 = (df['QCount1'] == 0) & (df[Rout] == 1)
    FLT_LIST(condition1, [df.columns[0], Rout] + QVARS_ALL + LIST)

    # Invalid Punches
    print(f"{QVAR[0]} - Invalid Punches:")
    condition2 = (df['QCount2'] != NR) & (df[Rout] == 1)
    FLT_LIST(condition2, [df.columns[0], Rout] + QVARS_ALL + LIST)

    # Exclusive Check
    if QEX:
        df['QCount3'] = df[QEX].eq(1).sum(axis=1)
        print(f"{QVAR[0]} - Exclusive Check:")
        condition3 = ((df['QCount1'] > 1) & (df['QCount3'] == 1)) | (df['QCount3'] > 1)
        FLT_LIST(condition3, [df.columns[0], Rout] + QVARS_ALL + LIST)

    # Filter OFF Check
    if df[Rout].eq(0).any():
        print(f"{QVAR[0]} - Filter OFF Check:")
        condition4 = (df[QVARS_ALL].isna().sum(axis=1) != NR) & (df[Rout] != 1)
        FLT_LIST(condition4, [df.columns[0], Rout] + QVARS_ALL + LIST)

    df.drop(columns=['QCount1', 'QCount2', 'QCount3', Rout], errors='ignore', inplace=True)

#### Example
#### df['QFILTER'] = 0
#### df.loc[df['Q28'].between(2,5), 'QFILTER'] = 1
#### MULTI(Rout='QFILTER', QVAR=['Q29_1', 'Q29_2','Q29_3'], EX=['Q29_99'], NR=4)


def GRID(Rout='QFILTER', QVAR=[], CVAR=[], COD=[], LIST=[]):
    """
    Function to process grid questions with specific codes and filter checks.
    
    Parameters:
    Rout : str
        Column name for the filter variable.
    QVAR : list of str
        List of question variable column names.
    COD : list of int
        List of valid codes for the question variables.
    LIST : list of str
        List of columns to display in the filtered output.
    """

    print(f"{QVAR[0]} to {QVAR[-1]}")
    from .io_utils import df
    NR = len(QVAR)

    if Rout not in df.columns:
        df[Rout] = 1

    if not CVAR:
        valid_mask = df[QVAR].isin(COD)
        df['QCount1'] = valid_mask.sum(axis=1)

        print(f"{QVAR[0]} - Invalid Punches:")
        condition1 = (df[Rout] == 1) & (df['QCount1'] != NR)
        FLT_LIST(COND=condition1, LIST=[df.columns[0], Rout] + QVAR)

        if (df[Rout] == 0).sum() > 0:
            print(f"{QVAR[0]} - Filter OFF Check:")
            condition2 = ((df[Rout] == 0) | df[Rout].isna()) & (df[QVAR].isna().sum(axis=1) != NR)
            FLT_LIST(COND=condition2, LIST=[df.columns[0], Rout] + QVAR + LIST)

        df.drop(columns=['QCount1'], inplace=True)

    else:
        for i, (x_col, d_col) in enumerate(zip(QVAR, CVAR), start=1):
            df['err'] = 0
            print(x_col + ':')
            err_mask1 = ((df[Rout] == 1) & ((df[d_col] == 1) & (df[x_col].isna() | ~df[x_col].isin(COD))))
            err_mask2 = ((df[Rout] == 1) & ((df[d_col] != 1) & df[x_col].notna()))
            err_mask3 = ((df[Rout] != 1) & (df[x_col].notna()))
            
            df.loc[err_mask1, 'err'] = i
            df.loc[err_mask2, 'err'] = i + 100
            df.loc[err_mask3, 'err'] = i + 200

            FLT_LIST(COND=(df['err'] > 0), LIST=[df.columns[0], 'err', Rout, d_col, x_col] + LIST)

        df.drop(columns=['err', Rout], inplace=True)

# Perform the GRID check
## GRID(Rout='QFILTER', QVAR=['Q56_1', 'Q56_2'], COD=[1, 2, 3, 4, 5], LIST=[])

# Perform the GRID_FLT check
## GRID(QVAR=['QCN5e_1', 'QCN5e_2', 'QCN5e_3', 'QCN5e_4', 'QCN5e_5'], CVAR=['QCN5d_1', 'QCN5d_2', 'QCN5d_3', 'QCN5d_4', 'QCN5d_5'], COD=[1, 2, 3, 4, 5], LIST=[])

def RANK_CHECK(Rout='QFILTER', QVAR=[], MAXR=0, MINR=None):
    """
    Function to process rank order questions with specific checks:
    1. Invalid Punches
    2. Duplicate Ranks
    3. Filter OFF Check

    Parameters:
    Rout : str
        Column name for the routing/filter variable.
    QVAR : list of str
        List of rank order question columns.
    MAXR : int
        Maximum rank value.
    LIST : list of str
        List of columns to display in the filtered output.
    """
    from .io_utils import df

    print(f"{QVAR[0]}:")
    NR = len(QVAR)
    
    valid_ranks = (df[QVAR] >= 1) & (df[QVAR] <= MAXR)
    df['QCount1'] = valid_ranks.sum(axis=1)
    
    if MINR is not None:
        df['QMAXR'] = df[QVAR].max(axis=1)
        print(f"{QVAR[0]} - Minimum Rank Check:")
        condition_min_rank = (df[Rout] == 1) & (df['QMAXR'] < MINR)
        FLT_LIST(COND=condition_min_rank, LIST=[df.columns[0], Rout, 'QCount1'] + QVAR)

    print(f"{QVAR[0]} - Invalid Punches:")
    if MINR is not None:
        condition_invalid = (df[Rout] == 1) & ((df[QVAR].isna().sum(axis=1) != (NR - df['QCount1'])) | (df['QCount1'] == 0))
    else:
        condition_invalid = (df[Rout] == 1) & ((df['QCount1'] != MAXR) | (df[QVAR].isna().sum(axis=1) != (NR - MAXR)))
    FLT_LIST(COND=condition_invalid, LIST=[df.columns[0], Rout, 'QCount1'] + QVAR)

    print(f"{QVAR[0]} - Duplicate Ranks:")
    df['err'] = 0
    for i in range(1, MAXR + 1):
        rank_count = (df[QVAR] == i).sum(axis=1)
        if MINR is not None:
            df.loc[(df[Rout] == 1) & (i <= df['QCount1']) & (rank_count != 1), 'err'] = i
        else:
            df.loc[(df[Rout] == 1) & (rank_count != 1), 'err'] = i

    condition_duplicate = df['err'] != 0
    FLT_LIST(COND=condition_duplicate, LIST=[df.columns[0], Rout, 'QCount1'] + QVAR)

    print(f"{QVAR[0]} - Filter OFF Check:")
    condition_filter_off = (df[Rout] == 0) & (df[QVAR].isna().sum(axis=1) != NR)
    FLT_LIST(COND=condition_filter_off, LIST=[df.columns[0], Rout] + QVAR)

    df.drop(columns=['QCount1', 'err', 'QMAXR'], errors='ignore', inplace=True)

# Example usage
# Assuming 'Routing' is the routing variable, and the rank order questions are in columns Q180_Orderr1 to Q180_Orderr6
# RANK_CHECK(df, Rout='QFILTER', QVAR=['Q180_Orderr1', 'Q180_Orderr2', 'Q180_Orderr3', 'Q180_Orderr4', 'Q180_Orderr5', 'Q180_Orderr6'], MAXR=3, LIST=[])


def OETEXT(Rout='QFILTER', QVAR=[], LIST=[]):
    """
    Validate Open-Ended text responses.
    """
    from .io_utils import df

    if isinstance(QVAR, str):
        QVAR = [QVAR]
    
    
    if Rout not in df.columns:
        df[Rout] = 1  

    for i in QVAR:
        print(i + ':')
        condition_qfilter1 = (df[Rout] == 1) & (df[i] == '')
        condition_qfilter0 = (df[Rout] != 1) & (df[i] != '')
        condition = condition_qfilter1 | condition_qfilter0
        FLT_LIST(condition, [df.columns[0]] + [i] + LIST)

    df.drop(columns=[Rout], inplace=True)


def NULL_CHECK(QVAR=[], LIST=[]):
    """
    Check for null or blank values across columns.
    """
    from .io_utils import df
    if isinstance(QVAR, str):
        QVAR = [QVAR]

    print(f"NULL Checking columns: {QVAR[0]} to {QVAR[-1]}:")
    

    for i in QVAR:
        print(i + ':')
        if df[i].dtype == 'object':
            condition_non_blank = df[i] != ''
            FLT_LIST(condition_non_blank, [df.columns[0], i] + LIST)
        else:
            condition_non_null = df[i].notna()
            FLT_LIST(condition_non_null, [df.columns[0], i] + LIST)

#helpers

def lst_no(min_val, max_val=None):
    """Generate list of integers inclusive of both ends."""
    if max_val is None:
        max_val = min_val
    return list(range(min_val, max_val + 1))
