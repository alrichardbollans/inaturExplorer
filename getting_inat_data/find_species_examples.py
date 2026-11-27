import pandas as pd
from pyinaturalist import get_observations, Observation

from getting_inat_data import generic_throttling, LICENSES, get_df_from_obs


def find_an_example(species_name: str) -> dict:
    generic_throttling()
    observations = get_observations(taxon_name=species_name, photos=True, license=LICENSES[0], photo_license=LICENSES[0], quality_grade='research',
                                    per_page=1)

    obs = Observation.from_json_list(observations)

    return obs


def get_multiple_examples(species_list) -> pd.DataFrame:
    collected_obs = []
    for s in species_list:
        collected_obs += find_an_example(s)

    return get_df_from_obs(collected_obs)


def main():
    get_multiple_examples(['Puma concolor'])


if __name__ == '__main__':
    main()
