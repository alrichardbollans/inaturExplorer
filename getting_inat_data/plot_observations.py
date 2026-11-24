import json
import os

import numpy as np
import pandas as pd

from getting_inat_data import app_configs

# Opens the clicked observation on iNaturalist (used when the figure is written to html).
MAP_CLICK_JS = """
var gd = document.getElementsByClassName('plotly-graph-div')[0];
gd.on('plotly_click', function(e) {
    var url = e.points[0].customdata[0];
    if (url) window.open(url, '_blank');
});
"""
MAP_CONFIG = {'modeBarButtonsToRemove': ['lasso2d', 'select2d']}

KINGDOM_COLOURS = {'Animalia': '#2a78d6', 'Fungi': '#eb6834', 'Plantae': '#1baf7a'}


def plot_observation_map(user_df: pd.DataFrame, out_html: str = None):
    """Interactive map of observations, coloured by iNaturalist quality grade."""
    import plotly.express as px

    df = user_df.dropna(subset=['latitude', 'longitude']).copy()
    df['Date'] = pd.to_datetime(df['date'], errors='coerce', utc=True).dt.strftime('%d %b %Y')

    df['kingdom'] = np.where(df['rank'] == 'kingdom', df['name'], df['kingdom'])
    df['kingdom'] = df['kingdom'].fillna('Other')
    ki = 0
    for k in df['kingdom'].unique():
        if k not in KINGDOM_COLOURS:
            # create random color in palette
            KINGDOM_COLOURS[k] = px.colors.qualitative.Plotly[ki]
            ki += 1

    fig = px.scatter_map(
        df,
        lat='latitude',
        lon='longitude',
        color='kingdom',
        color_discrete_map=KINGDOM_COLOURS,
        category_orders={'Kingdom': list(KINGDOM_COLOURS.keys())},
        hover_name='name',
        hover_data={'Date': True, 'kingdom': True, 'quality_grade': True,
                    'latitude': ':.4f', 'longitude': ':.4f'},
        labels={'kingdom': 'Kingdom', 'latitude': 'Latitude', 'longitude': 'Longitude', 'quality_grade': 'Quality Grade'},
        map_style='open-street-map',
        # map_style='positron',
        zoom=3,
        center={'lat': df['latitude'].median(), 'lon': df['longitude'].median()},
        height=650,
        custom_data=['uri']
    )
    fig.update_traces(marker={'size': 8, 'opacity': 0.85})

    # df['Link'] = df['uri'].apply(lambda x: f'<a href="{x}" target="_blank">Link</a>')


    fig.update_layout(
        title={'text': f'Observations ({len(df)}) — {df["username"].iloc[0]}',
               'x': 0.01, 'font': {'size': 18, 'color': '#0b0b0b'}},
        legend={'title': {'text': 'Kingdom'}, 'x': 0.01, 'y': 0.98,
                'bgcolor': 'rgba(252,252,251,0.9)', 'font': {'color': '#52514e'}},
        margin={'l': 0, 'r': 0, 't': 50, 'b': 0},
        paper_bgcolor='#fcfcfb',
        font={'family': 'Inter, Helvetica, Arial, sans-serif'}
    )

    if out_html:
        fig.write_html(out_html, include_plotlyjs='cdn', config=MAP_CONFIG, post_script=MAP_CLICK_JS)
    return fig


def main():

    user_df = pd.read_csv(os.path.join(app_configs["cache_dir"], app_configs["userfilename"]))
    plot_observation_map(user_df, os.path.join(app_configs["cache_dir"],'obs_map.html'))


if __name__ == '__main__':
    main()
