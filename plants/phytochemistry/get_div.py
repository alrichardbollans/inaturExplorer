import os
import tempfile
from pathlib import Path

import pandas as pd
from phytochempy.chemical_diversity_metrics import calculate_FAD_measures
from wcvpy.wcvp_download import plot_number_accepted_taxa_in_regions
from wcvpy.wcvp_name_matching import get_accepted_info_from_names_in_column

from getting_inat_data.retrieving_results import get_user_data
COMPOUND_ID_COL = 'Standard_SMILES'
FAD_INDICES = ['FAD', 'MFAD', 'APWD']

def add_diversity_data(acc_df: pd.DataFrame):
    compound_data = pd.read_csv('/home/atp/Documents/repos/VascularPlantChemodiversity/outputs/compound_occurrences.csv', index_col=0)

    compound_data = compound_data[compound_data['accepted_species'].isin(acc_df['accepted_species'])]

    working_data = pd.merge(compound_data, acc_df[['username', 'accepted_species']], on='accepted_species')

    # Remove duplicates
    working_data = working_data.drop_duplicates(subset=['username', COMPOUND_ID_COL], keep='first')

    FAD_measures = calculate_FAD_measures(working_data, compound_grouping='username')

    FAD_measures = FAD_measures.dropna(subset=FAD_INDICES, how='all')

    max_div = pd.read_csv('all_phytochemdiv.csv')
    FAD_measures['FAD_proportion'] = FAD_measures['FAD'] / max_div['FAD']
    FAD_measures.to_csv(os.path.join(cache_dir, f'user_diversity.csv'))

    return FAD_measures


def main():
    pass


if __name__ == '__main__':
    main()
