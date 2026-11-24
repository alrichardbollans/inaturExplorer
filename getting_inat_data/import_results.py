import json
import os

import pandas as pd
from pyinaturalist import get_taxa, get_observations, iNatClient, Observation
import datetime
import time

from getting_inat_data import resolve_names

# Define variables to keep track of throttling
count = 0
last_reset_time = datetime.datetime.now()
rate_limit = 60  # Max number of requests per minute

app_configs = json.load(open("../app_configs.json"))
cache_dir = app_configs["cache_dir"]


def generic_throttling():
    # Access the global variables
    global count
    global last_reset_time

    # Wait until we are below the rate limit
    if count >= rate_limit:
        while True:
            now = datetime.datetime.now()
            if (now - last_reset_time) <= datetime.timedelta(seconds=60):
                print("Waiting...")
                time.sleep(1)
            else:
                count = 0
                last_reset_time = datetime.datetime.now()
                break
    count += 1


def find_taxon(name: str):
    """Resolve a species name to the best-matching taxon."""

    generic_throttling()

    response = get_taxa(q=name, per_page=1)
    if not response["results"]:
        raise ValueError(f"No species found matching '{name}'")
    return response["results"][0]


def count_observations_across_inat(taxon_id, **filters):
    raise NotImplementedError
    """Return the number of observations for a taxon_id.
    Extra filters (e.g. quality_grade='research', place_id=6857) pass straight through."""
    generic_throttling()

    response = get_observations(taxon_id=taxon_id, per_page=0, **filters)
    return response["total_results"]


def get_user_data(username: str):
    generic_throttling()

    observations = get_observations(user_id=username, page='all')

    user_obs = Observation.from_json_list(observations)

    df_list = [{'id': o.taxon.id, 'name': o.taxon.name, 'rank': o.taxon.rank, 'kingdom': o.taxon.kingdom.name if o.taxon.kingdom else None,
                'phylum': o.taxon.phylum.name if o.taxon.phylum else None,
                'total_obs_count': o.taxon.observations_count,
                'latitude': o.location[0] if o.location else None,
                'longitude': o.location[1] if o.location else None,
                'captive': o.captive, 'quality_grade': o.quality_grade,
                'date': o.observed_on.isoformat() if o.observed_on else None, 'uri': o.uri, 'username': o.username}
               for o in user_obs if o.taxon]

    df = pd.DataFrame(df_list)

    return df


def main():
    os.makedirs(cache_dir, exist_ok=True)
    print(cache_dir)
    # count_observations('Puma concolor')
    user_df = get_user_data('adamrb2')
    user_df.to_csv(os.path.join(cache_dir, app_configs["userfilename"]))
    # print(user_df)
    # acc_df = resolve_names(user_df)
    # acc_df.to_csv(os.path.join(cache_dir, app_configs["accplantsfilename"]))


if __name__ == '__main__':
    main()
