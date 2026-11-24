import os

from wcvpy.wcvp_name_matching import get_accepted_info_from_names_in_column, get_species_binomial_from_full_name


WCVP_VERSION = '14'


def resolve_names(user_df):
    user_df = user_df[user_df['kingdom'] == 'Plantae']
    user_df = user_df[user_df['phylum'] == 'Tracheophyta']
    acc_df = get_accepted_info_from_names_in_column(user_df, 'name', match_level='direct', wcvp_version=WCVP_VERSION)
    acc_df = acc_df.dropna(subset=['accepted_name'])

    acc_df['tree_name'] = acc_df['accepted_name'].apply(lambda x: get_species_binomial_from_full_name(x).replace(' ', '_'))


    return acc_df
