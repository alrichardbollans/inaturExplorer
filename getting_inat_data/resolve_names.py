import os
from pathlib import Path

import pandas as pd
from wcvpy.wcvp_name_matching import get_species_binomial_from_full_name

WCVP_VERSION = '14'


def _deduplicate_taxa(taxa):
    """Keep the first row per taxon name, preferring rows where it matches the accepted name."""
    is_accepted = taxa['taxon_name'].eq(taxa['accepted_name']).fillna(False)
    has_accepted_row = taxa['taxon_name'].isin(taxa.loc[is_accepted, 'taxon_name'])
    out = taxa.loc[is_accepted | ~has_accepted_row]
    return out.drop_duplicates(subset='taxon_name')


def resolve_names(user_df):
    user_df = user_df[user_df['kingdom'] == 'Plantae']
    user_df = user_df[user_df['phylum'] == 'Tracheophyta']

    all_taxa = pd.read_csv(Path(__file__).resolve().parent / "wcvp_v14" / "all_taxa.csv.gz")
    all_taxa = all_taxa[all_taxa['taxon_name'].isin(user_df['name'])]
    all_taxa = _deduplicate_taxa(all_taxa)

    acc_df = pd.merge(user_df, all_taxa, left_on='name', right_on='taxon_name', how='left')
    acc_df = acc_df.dropna(subset=['accepted_name'])

    acc_df['accepted_species'] = acc_df['accepted_name'].apply(lambda x: get_species_binomial_from_full_name(x))
    acc_df['tree_name'] = acc_df['accepted_species'].apply(lambda x: x.replace(' ', '_'))
    print('Finished resolving names')
    return acc_df


if __name__ == '__main__':
    from wcvpy.wcvp_download import get_all_taxa

    needed_cols = [
        'taxon_name', 'accepted_name','accepted_family']

    at = get_all_taxa(version=WCVP_VERSION)[needed_cols]
    at = at.dropna(subset=['accepted_name'])
    at.to_csv(os.path.join('wcvp_v14', 'all_taxa.csv.gz'), index=False)

    user_df = pd.read_csv('/tmp/shiny_4zpxnkw9_cache/users/adamrb2/user.csv', index_col=0)
    acc_df = resolve_names(user_df)
