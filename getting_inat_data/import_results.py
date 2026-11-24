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

app_configs = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app_configs.json")))
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
                'date': o.observed_on.isoformat() if o.observed_on else None, 'uri': o.uri,
                'first_photo': [o.photos[0].medium_url, o.photos[0].attribution, o.photos[0].license_code] if o.photos else None,
                'username': o.username}
               for o in user_obs if o.taxon]

    df = pd.DataFrame(df_list)

    return df


def get_rarest_observation(user_data, include_captive: bool = False, rank='species'):
    data = user_data[user_data['rank'] == rank]
    if not include_captive:
        data = data[~data['captive']]
    return data.sort_values('total_obs_count', ascending=True).iloc[0]

def get_favourite_taxa(user_data, include_captive: bool = True, rank='species'):
    species = user_data[user_data["rank"] == rank]
    if not include_captive:
        species = species[~species['captive']]
    if species.empty:
        return None
    counts = (
        species.groupby(["id", "name"]).size().rename("n").reset_index()
        .sort_values(["n", "name"], ascending=[False, True])  # alphabetical tie-break
        .set_index(["id", "name"])["n"]
    )
    top_id = counts.index[0][0]
    top_obs = species[species["id"] == top_id]
    with_photo = top_obs[top_obs["first_photo"].notna()]
    obs = (with_photo if not with_photo.empty else top_obs).iloc[0]
    return counts, obs

def main():
    os.makedirs(cache_dir, exist_ok=True)
    print(cache_dir)
    # count_observations('Puma concolor')
    user_df = get_user_data('adamrb2')
    user_df.to_csv(os.path.join(cache_dir, app_configs["userfilename"]))

    rarest_obs = get_rarest_observation(user_df)
    print(rarest_obs)

    fave_taxon = get_favourite_taxon(user_df)
    print(fave_taxon)
    # print(user_df)
    # acc_df = resolve_names(user_df)
    # acc_df.to_csv(os.path.join(cache_dir, app_configs["accplantsfilename"]))


if __name__ == '__main__':
    main()
