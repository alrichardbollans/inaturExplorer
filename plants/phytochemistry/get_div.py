import os
from pathlib import Path

import pandas as pd
from phytochempy.chemical_diversity_metrics import calculate_FAD_measures

from getting_inat_data import app_configs

COMPOUND_ID_COL = 'Standard_SMILES'
FAD_INDICES = ['FAD', 'MFAD', 'APWD']
COMPOUND_OCCURRENCES_CSV = Path(__file__).resolve().parent / 'compound_occurrences.csv'  # https://github.com/alrichardbollans/VascularPlantChemodiversity/commit/c998ebb1cb1953e479e4ecc7ea793e1d557a9f77
ALL_DIV_CSV = Path(__file__).resolve().parent / 'all_phytochemdiv.csv'


def get_user_compounds(acc_df: pd.DataFrame) -> pd.DataFrame:
    """Known compound occurrences for the accepted species in acc_df (one row per species/compound)."""
    compound_data = pd.read_csv(COMPOUND_OCCURRENCES_CSV, index_col=0)
    compound_data = compound_data[compound_data['accepted_species'].isin(acc_df['accepted_species'])]
    return compound_data.drop_duplicates(subset=['accepted_species', COMPOUND_ID_COL], keep='first')


def get_user_diversity_data(acc_df: pd.DataFrame, out_path: str = None, compound_data: pd.DataFrame = None):
    if compound_data is None:
        compound_data = get_user_compounds(acc_df)

    working_data = pd.merge(compound_data, acc_df[['username', 'accepted_species']].drop_duplicates(), on='accepted_species')

    # Remove duplicates
    working_data = working_data.drop_duplicates(subset=['username', COMPOUND_ID_COL], keep='first')

    FAD_measures = calculate_FAD_measures(working_data, compound_grouping='username')

    FAD_measures = FAD_measures.dropna(subset=FAD_INDICES, how='all')

    max_div = pd.read_csv(ALL_DIV_CSV)
    FAD_measures['FAD_proportion'] = FAD_measures['FAD'] / max_div['FAD']
    FAD_measures.to_csv(out_path or os.path.join(app_configs["cache_dir"], f'user_diversity.csv'))

    return FAD_measures


def check_total_div():
    compound_data = pd.read_csv(COMPOUND_OCCURRENCES_CSV, index_col=0)

    compound_data['username'] = 'all'

    # Remove duplicates
    working_data = compound_data.drop_duplicates(subset=['username', COMPOUND_ID_COL], keep='first')

    FAD_measures = calculate_FAD_measures(working_data, compound_grouping='username')

    FAD_measures.to_csv(ALL_DIV_CSV)

    return FAD_measures
