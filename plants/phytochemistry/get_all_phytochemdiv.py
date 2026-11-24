import pandas as pd
from phytochempy.chemical_diversity_metrics import calculate_FAD_measures

from plants.plant_summaries import COMPOUND_ID_COL


def check_all_div():
    compound_data = pd.read_csv('/home/atp/Documents/repos/VascularPlantChemodiversity/outputs/compound_occurrences.csv', index_col=0)

    compound_data['username'] = 'all'

    # Remove duplicates
    working_data = compound_data.drop_duplicates(subset=['username', COMPOUND_ID_COL], keep='first')

    FAD_measures = calculate_FAD_measures(working_data, compound_grouping='username')

    FAD_measures.to_csv('all_phytochemdiv.csv')

    return FAD_measures


def main():
    check_all_div()


if __name__ == '__main__':
    main()
