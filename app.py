import ast
import base64
import asyncio
import datetime
import importlib.util
import os
import re
import shutil
from urllib.parse import urlencode

import pandas as pd
import plotly.graph_objects as go
import requests
from PIL import Image
from shiny import App, reactive, render, req, ui

from getting_inat_data.plot_observations import MAP_CLICK_JS, MAP_CONFIG, plot_observation_map
from getting_inat_data.find_species_examples import get_multiple_examples
from getting_inat_data import app_configs, cache_dir, get_rarest_observation, get_user_data, resolve_names, get_favourite_taxa

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
PHYLOGENY_DIR = os.path.join(REPO_DIR, "plants", "phylogeny")
USERS_CACHE_DIR = os.path.join(cache_dir, "users")
os.makedirs(USERS_CACHE_DIR, exist_ok=True)

USER_FILE = app_configs["userfilename"]
ACC_FILE = app_configs["accplantsfilename"]
PHYDIV_FILE = app_configs["phydivfilename"]
PHYPLOT_FILE = app_configs["phyplotfilename"]
MAXDIV_FILE = app_configs["maxdivresultsfilename"]
MAXDIV_PLOT_FILE = app_configs["maxdivphyplotfilename"]
CHEMDIV_FILE = "phytochem_diversity.csv"
CHEMCOMPOUNDS_FILE = "phytochem_compounds.csv"

# plants/ isn't a package, so load the phytochemistry module from its path.
_spec = importlib.util.spec_from_file_location(
    "phytochem_div", os.path.join(REPO_DIR, "plants", "phytochemistry", "get_div.py"))
phytochem = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(phytochem)
TOTAL_KNOWN_COMPOUNDS = int(pd.read_csv(phytochem.ALL_DIV_CSV)["GroupSize_FAD"].iloc[0])

CHART_BLUE = "#2a78d6"
TEXT_SECONDARY = "#52514e"
GRID_COLOUR = "#e9e9e6"


# --------------------------------------------------------------------------------------
# Cache helpers
# --------------------------------------------------------------------------------------

def user_cache_dir(username: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_-]", "_", username)
    path = os.path.join(USERS_CACHE_DIR, safe)
    os.makedirs(path, exist_ok=True)
    return path


def _parse_photo(value):
    # 'first_photo' is a list, which is written to csv as its string repr.
    if isinstance(value, str):
        if value.startswith("http"):  # older caches stored just the url
            return [value, None, None]
        try:
            return ast.literal_eval(value)
        except (ValueError, SyntaxError):
            return None
    return value if isinstance(value, (list, tuple)) else None


def get_resolved_names(udir: str):
    user_path, acc_path = os.path.join(udir, USER_FILE), os.path.join(udir, ACC_FILE)
    if not os.path.exists(acc_path):
        user_df = pd.read_csv(user_path, index_col=0)
        acc_df = resolve_names(user_df)

        acc_df.to_csv(acc_path)
    else:
        acc_df = pd.read_csv(acc_path, index_col=0)
    return acc_df


def load_or_import_user(username: str, refresh: bool) -> dict:
    """Blocking work: load the user's data from cache, or fetch + resolve and cache it."""
    udir = user_cache_dir(username)
    user_path, acc_path = os.path.join(udir, USER_FILE), os.path.join(udir, ACC_FILE)

    if refresh and os.path.exists(acc_path):
        os.remove(acc_path)

    from_cache = not refresh and os.path.exists(user_path)

    if from_cache:
        user_df = pd.read_csv(user_path, index_col=0)
    else:
        user_df = get_user_data(username)
        if user_df.empty:
            raise ValueError(f"No observations found for '{username}'.")
        user_df.to_csv(user_path)
        # Diversity results depend on the accepted names, so they are now stale.
        for f in (PHYDIV_FILE, PHYPLOT_FILE,
                  MAXDIV_FILE, MAXDIV_PLOT_FILE, CHEMDIV_FILE, CHEMCOMPOUNDS_FILE):
            if os.path.exists(os.path.join(udir, f)):
                os.remove(os.path.join(udir, f))

    user_df["first_photo"] = user_df["first_photo"].apply(_parse_photo)
    return {
        "username": username,
        "dir": udir,
        "user_df": user_df,
        "from_cache": from_cache,
        "updated": datetime.datetime.fromtimestamp(os.path.getmtime(user_path)),
    }


def download_photo(url: str, udir: str) -> str:
    # e.g. .../photos/684641471/medium.jpg -> photo_684641471_medium.jpg
    photo_id, fname = url.split("?")[0].rstrip("/").split("/")[-2:]
    path = os.path.join(udir, f"photo_{photo_id}_{fname}")
    if not os.path.exists(path):
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        with open(path, "wb") as f:
            f.write(resp.content)
    return path


def load_or_compute_phytochem(udir: str, acc_df: pd.DataFrame) -> dict:
    """Blocking work: known compounds + FAD measures for the user's plants, cached per user."""
    div_path, cmpd_path = os.path.join(udir, CHEMDIV_FILE), os.path.join(udir, CHEMCOMPOUNDS_FILE)
    if os.path.exists(div_path) and os.path.exists(cmpd_path):
        measures = pd.read_csv(div_path, index_col=0)
        compounds = pd.read_csv(cmpd_path, index_col=0)
    else:
        compounds = phytochem.get_user_compounds(acc_df)
        measures = (phytochem.get_user_diversity_data(acc_df, out_path=div_path, compound_data=compounds)
                    if not compounds.empty else pd.DataFrame())
        measures.to_csv(div_path)
        keep = ["accepted_species", "accepted_family", "example_compound_name",
                phytochem.COMPOUND_ID_COL, "NPclassif_pathway_results_0"]
        compounds = compounds[keep]
        compounds.to_csv(cmpd_path)
    return {"dir": udir, "measures": measures.iloc[0] if not measures.empty else None, "compounds": compounds, "acc_df": acc_df}


def compact_number(value: float) -> str:
    """e.g. 10762593 -> '10.8M', so large values fit in a value box."""
    for threshold, suffix in ((1e9, "B"), (1e6, "M"), (1e4, "k")):
        if abs(value) >= threshold:
            return f"{value / threshold:.1f}{suffix}"
    return f"{value:,.0f}"


def plotly_iframe(fig, height: int, post_script: str = None, config: dict = None):
    """Embed a plotly figure as a standalone page in an iframe (keeps plotly's JS isolated)."""
    html = fig.to_html(full_html=True, include_plotlyjs="cdn", config=config or {"displayModeBar": False},
                       post_script=post_script)
    html = html.replace("<head>", "<head><style>body { margin: 0; }</style>", 1)
    return ui.tags.iframe(srcdoc=html, scrolling="no", style=f"width: 100%; height: {height}px; border: none;")


def pathway_bar_chart(compounds: pd.DataFrame):
    """Unique compounds per NPClassifier pathway, as a horizontal bar chart."""
    counts = (
        compounds.drop_duplicates(phytochem.COMPOUND_ID_COL)["NPclassif_pathway_results_0"]
        .fillna("Unclassified").value_counts()
    )
    # Plotly draws the first row at the bottom: "Unclassified" last, then largest at the top.
    counts = pd.concat([counts.reindex(["Unclassified"]).dropna().astype(int),
                        counts.drop("Unclassified", errors="ignore").sort_values()])
    height = 36 * len(counts) + 60
    fig = go.Figure(go.Bar(
        x=counts.values, y=counts.index, orientation="h", width=0.55,
        marker={"color": CHART_BLUE, "cornerradius": 4},
        text=[f"{v:,}" for v in counts.values], textposition="outside", cliponaxis=False,
        textfont={"color": TEXT_SECONDARY},
        hovertemplate="<b>%{y}</b><br>%{x:,} unique compounds<extra></extra>",
    ))
    fig.update_layout(
        height=height, margin={"l": 0, "r": 50, "t": 10, "b": 30},
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"family": "Inter, Helvetica, Arial, sans-serif", "color": TEXT_SECONDARY, "size": 13},
        xaxis={"title": "Unique compounds", "gridcolor": GRID_COLOUR, "zeroline": False},
        yaxis={"ticksuffix": "  "},
        hoverlabel={"bgcolor": "white", "font": {"color": "#0b0b0b"}},
    )
    return plotly_iframe(fig, height)


def image_data_uri(path: str) -> str:
    mime = "image/png" if path.lower().endswith(".png") else "image/jpeg"
    with open(path, "rb") as f:
        return f"data:{mime};base64,{base64.b64encode(f.read()).decode()}"


def make_display_copy(plot_path: str, max_px: int = 1600) -> str:
    raise DeprecationWarning('No longer used.')
    """The R plot is 4800px / several MB; send a smaller copy to the browser."""
    display_path = plot_path.replace(".png", "_display.png")
    if not os.path.exists(display_path) or os.path.getmtime(display_path) < os.path.getmtime(plot_path):
        with Image.open(plot_path) as im:
            im.thumbnail((max_px, max_px))
            im.save(display_path, optimize=True)
    return display_path


async def run_r_script(script: str, udir: str):
    if shutil.which("Rscript") is None:
        raise RuntimeError("Rscript was not found on the PATH.")
    proc = await asyncio.create_subprocess_exec(
        "Rscript", script, udir,
        cwd=PHYLOGENY_DIR,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.STDOUT,
    )
    try:
        stdout, _ = await proc.communicate()
    except asyncio.CancelledError:
        proc.kill()
        raise
    if proc.returncode != 0:
        tail = "\n".join(stdout.decode(errors="replace").strip().splitlines()[-10:])
        raise RuntimeError(f"{script} failed:\n{tail}")


# --------------------------------------------------------------------------------------
# UI
# --------------------------------------------------------------------------------------

def spinner(message: str):
    return ui.div(
        ui.div(class_="spinner-border text-success", role="status", style="width: 3rem; height: 3rem;"),
        ui.p(message, class_="mt-3 text-muted"),
        class_="text-center my-5",
    )


app_ui = ui.page_fluid(
    ui.tags.head(
        ui.tags.style("""
            .results-book > .nav {
                gap: .5rem;
                margin-bottom: 1rem;
            }
            .results-book > .nav > .nav-item:last-child {
                margin-inline-start: auto;
            }
            .results-book > .nav .nav-link[data-value="plants"] {
                color: var(--bs-success-text-emphasis);
                background: var(--bs-success-bg-subtle);
            }
            .results-book > .nav .nav-link[data-value="plants"]:is(:hover, .active) {
                color: white;
                background: var(--bs-success);
            }
            .results-book > .tab-content, .maximiser-browser {
                perspective: 1400px;
            }
            @media (prefers-reduced-motion: no-preference) {
                .results-book > .tab-content > .tab-pane.active {
                    animation: turn-results-page 450ms ease-out;
                }
                .results-book > .tab-content > [data-value="plants"] {
                    --page-start-angle: 45deg;
                    transform-origin: left center;
                }
                .results-book > .tab-content > [data-value="observations"] {
                    --page-start-angle: -45deg;
                    transform-origin: right center;
                }
                .maximiser-page {
                    --page-start-angle: 45deg;
                    transform-origin: left center;
                    animation: turn-results-page 450ms ease-out;
                }
            }
            @keyframes turn-results-page {
                from {
                    opacity: .45;
                    transform: rotateY(var(--page-start-angle));
                }
                to {
                    opacity: 1;
                    transform: rotateY(0deg);
                }
            }
        """),
    ),
    ui.div(
        ui.h1("inaturExplorer", class_="display-4"),
        ui.p(
            "Explore the biodiversity in your iNaturalist observations.",
            class_="lead text-muted"),
        ui.p(
            "Map your sightings, see where your plants fit on the tree of life, and discover their recorded compounds.",
            class_="lead text-muted"),
        class_="text-center mt-5 mb-4",
    ),
    ui.div(
        ui.card(
            ui.input_text("username", "iNaturalist username", placeholder="e.g. adamrb2", width="100%"),
            ui.input_checkbox("refresh", "Re-download from iNaturalist (ignore cache)", value=False),
            ui.input_task_button("import_btn", "Import", label_busy="Importing...", class_="btn-success w-100"),
        ),
        class_="mx-auto",
        style="max-width: 420px;",
    ),
    ui.div(
        ui.output_ui("main_content"),
        class_="mx-auto mt-4 mb-5",
        style="max-width: 1000px;",
    ),
    title="inaturExplorer",
)


# --------------------------------------------------------------------------------------
# Server
# --------------------------------------------------------------------------------------

def server(input, output, session):
    # ---- Import -----------------------------------------------------------------------

    @ui.bind_task_button(button_id="import_btn")
    @reactive.extended_task
    async def import_task(username: str, refresh: bool):
        # Run in a thread so the UI (spinner) stays responsive.
        return await asyncio.to_thread(load_or_import_user, username, refresh)

    @reactive.effect
    @reactive.event(input.import_btn)
    def _start_import():
        username = input.username().strip()
        if not username:
            ui.notification_show("Please enter a username.", type="warning")
            return
        div_task.cancel()
        chem_task.cancel()
        import_task(username, input.refresh())

    @reactive.calc
    def imported() -> dict:
        return import_task.result()

    @reactive.calc
    def rarest_obs():
        df = imported()["user_df"]
        if df["captive"].all():
            return None
        return get_rarest_observation(df)

    @reactive.calc
    def most_observed():
        """Species the user has recorded most often, as (counts, representative observation)."""
        df = imported()["user_df"]
        return get_favourite_taxa(df)

    @render.ui
    def main_content():
        status = import_task.status()
        if status == "initial":
            return None
        if status == "running":
            return spinner("Importing observations, this may take a moment...")
        if status == "error":
            try:
                import_task.result()
            except Exception as e:
                return ui.div(f"Import failed: {e}", class_="alert alert-danger")

        data = imported()
        source = "Loaded from cache" if data["from_cache"] else "Downloaded"
        return ui.TagList(
            ui.p(
                f"{source}: {len(data['user_df'])} observations for {data['username']} "
                f"(last updated {data['updated']:%Y-%m-%d %H:%M}).",
                class_="text-muted text-center",
            ),
            ui.div(
                ui.navset_pill(
                    ui.nav_panel(
                        "Observations",
                        ui.layout_columns(
                            ui.card(
                                ui.card_header(ui.h4("Rarest observed species", class_="m-0")),
                                ui.output_ui("rarest_section"),
                            ),
                            ui.card(
                                ui.card_header(ui.h4("Most observed species", class_="m-0")),
                                ui.output_ui("most_observed_section"),
                            ),
                            col_widths=(6, 6),
                        ),
                        ui.card(
                            ui.card_header(ui.h4("Where you've observed", class_="m-0")),
                            ui.output_ui("observation_map"),
                            ui.p("Click a point to open the observation on iNaturalist.", class_="small text-muted m-0"),
                        ),
                        value="observations",
                    ),
                    ui.nav_panel(
                        ui.span("Let’s explore plant diversity! ", ui.span("→", aria_hidden="true")),
                        ui.card(
                            ui.card_header(ui.h4("Vascular plant diversity", class_="m-0")),
                            ui.div(
                                ui.input_task_button(
                                    "analyse_btn", "Analyse Plant Diversity",
                                    label_busy="Analysing...", class_="btn-success",
                                ),
                                class_="text-center",
                            ),
                            ui.output_ui("diversity_section"),
                        ),
                        ui.card(
                            ui.card_header(ui.h4("Known phytochemical diversity", class_="m-0")),
                            ui.div(
                                ui.input_task_button(
                                    "analyse_chem_btn", "Analyse Phytochemical Diversity",
                                    label_busy="Analysing...", class_="btn-success",
                                ),
                                class_="text-center",
                            ),
                            ui.output_ui("phytochem_section"),
                        ),
                        value="plants",
                    ),
                    selected="observations",
                ),
                class_="results-book",
            ),
        )

    # ---- Species highlights ---------------------------------------------------------

    def species_highlight(obs, *stats):
        """Photo + summary for a single observation, with extra stat lines underneath."""
        photo = obs["first_photo"]
        image = ui.p("No photo available.", class_="text-muted")
        if photo and photo[0]:
            try:
                path = download_photo(photo[0], imported()["dir"])
                # licence = f" ({photo[2]})" if photo[2] else ""
                image = ui.div(
                    ui.img(src=image_data_uri(path), class_="img-fluid rounded", style="max-height: 400px;"),
                    ui.p(f"{photo[1]}", class_="small text-muted mt-1"),
                )
            except requests.RequestException:
                pass
        return species_profile(
            obs["name"], obs["uri"], image,
            ui.p(f"Kingdom: {obs['kingdom'] or '—'} · Phylum: {obs['phylum'] or '—'}"),
            *stats,
        )

    def species_profile(name, url, image, *stats):
        return ui.TagList(
            image,
            ui.h3(ui.em(name), class_="mt-2"),
            *stats,
            ui.a("View on iNaturalist", href=url, target="_blank", class_="btn btn-outline-success btn-sm"),
        )

    @render.ui
    def rarest_section():
        obs = rarest_obs()
        if obs is None:
            return ui.p("No wild observations found.")
        return species_highlight(
            obs,
            ui.p(ui.strong(f"{int(obs['total_obs_count']):,}"), " observations on iNaturalist"),
            ui.p(f"Observed on: {obs['date'][:10] if obs['date'] else 'unknown'}"),
        )

    @render.ui
    def most_observed_section():
        result = most_observed()
        if result is None:
            return ui.p("No species-level observations found.")
        counts, obs = result
        runners_up = [ui.tags.li(ui.em(name), f" — {n}") for (_, name), n in counts.iloc[1:5].items()]
        n_tied = int((counts == counts.iloc[0]).sum()) - 1
        tied = f" (tied with {n_tied} other species)" if n_tied else ""
        return species_highlight(
            obs,
            ui.p(ui.strong(f"{counts.iloc[0]}"), f" of your observations{tied}"),
            ui.p(ui.strong(f"{int(obs['total_obs_count']):,}"), " observations on iNaturalist"),
            ui.div(ui.p("Runners up:", class_="mb-1"), ui.tags.ul(*runners_up), class_="small")
            if runners_up else None,
        )

    # ---- Map --------------------------------------------------------------------------

    @render.ui
    def observation_map():
        df = imported()["user_df"]
        if df[["latitude", "longitude"]].dropna().empty:
            return ui.p("None of your observations have a location.", class_="text-muted")
        fig = plot_observation_map(df)
        fig.update_layout(title=None, margin={"l": 0, "r": 0, "t": 0, "b": 0}, height=600)
        return plotly_iframe(fig, 600, post_script=MAP_CLICK_JS, config=MAP_CONFIG)

    # ---- Plant diversity --------------------------------------------------------------

    maximiser_index = reactive.value(0)

    @ui.bind_task_button(button_id="analyse_btn")
    @reactive.extended_task
    async def div_task(udir: str):
        acc_df = get_resolved_names(udir)
        div_path, plot_path = os.path.join(udir, PHYDIV_FILE), os.path.join(udir, PHYPLOT_FILE)
        maxdiv_path = os.path.join(udir, MAXDIV_FILE)
        maxdiv_plot_path = os.path.join(udir, MAXDIV_PLOT_FILE)
        jobs = []
        if not all(os.path.exists(path) for path in (div_path, maxdiv_path, maxdiv_plot_path)):
            jobs.append(run_r_script("get_div.R", udir))
        if not os.path.exists(plot_path):
            jobs.append(run_r_script("plot_tree.R", udir))
        await asyncio.gather(*jobs)  # both scripts run concurrently
        measures = pd.read_csv(div_path, index_col=0)["diversity_measures"]
        maximisers = pd.read_csv(maxdiv_path, index_col=0)
        species_names = maximisers["tip"].str.replace("_", " ").unique().tolist()
        try:
            maximiser_examples = await asyncio.to_thread(get_multiple_examples, species_names)
        except requests.RequestException:
            maximiser_examples = pd.DataFrame()
        return {
            "dir": udir, "measures": measures, "plot": plot_path, "acc_df": acc_df,
            "maximisers": maximisers, "maximiser_examples": maximiser_examples,
            "maxdiv_plot": maxdiv_plot_path,
        }

    @reactive.effect
    @reactive.event(input.analyse_btn)
    def _start_analysis():
        maximiser_index.set(0)
        div_task(imported()["dir"])

    @render.ui
    def diversity_section():
        status = div_task.status()
        if status == "running":
            return spinner("Calculating phylogenetic diversity and drawing the tree (this can take a minute)...")
        if status == "error":
            try:
                div_task.result()
            except Exception as e:
                return ui.div(ui.pre(f"Analysis failed: {e}"), class_="alert alert-danger mt-3")
        if status != "success" or div_task.result()["dir"] != imported()["dir"]:
            return ui.p(
                "Place your vascular plant observations on the tree of life and measure "
                "how much evolutionary history they cover.",
                class_="text-muted text-center mt-3",
            )

        m = div_task.result()["measures"]
        acc_df = div_task.result()["acc_df"]
        count = len(div_task.result()["maximisers"])
        return ui.TagList(
            ui.layout_columns(
                ui.value_box("Faith's phylogenetic diversity", f"{m['user_div']:,.0f}",
                             ui.p("Total branch length spanned by your observed species")),
                ui.value_box("Share of all vascular plant phylogenetic diversity", f"{m['proportion']:.3%}",
                             ui.p(f"of {m['total_div']:,.0f} in the full tree")),
                ui.value_box("Species on the tree", f"{int(m['user_tips']):,}",
                             ui.p(f"of {int(m['total_tips']):,} tips · "
                                  f"{acc_df['accepted_species'].nunique():,} species matched")),
                ui.value_box("Families observed", f"{acc_df['accepted_family'].nunique():,}",
                             ui.p(f"from {len(acc_df):,} plant observations")),
                col_widths=(3, 3, 3, 3),
                class_="mt-3",
            ),
            ui.layout_columns(
                ui.div(
                    ui.h5("Your species on the vascular plant tree"),
                    ui.output_image("tree_plot", height="auto"),
                    ui.p("Red branches trace the lineages of the species you have observed. CITE TREE",
                         class_="small text-muted"),
                ),
                ui.div(
                    ui.h5("Observed species"),
                    ui.output_data_frame("species_table"),
                ),
                col_widths=(7, 5),
            ),
            ui.h5("Which species will most increase your observed diversity?", class_="mt-4"),
            ui.layout_columns(
                ui.div(
                    ui.output_image("maxdiv_plot", height="auto"),
                    ui.p("Blue marks the diversity maximisers on the tree.", class_="small text-muted"),
                ),
                ui.card(
                    ui.output_ui("maximiser_species"),
                    ui.card_footer(
                        ui.input_action_button("next_maximiser", "Next species →", class_="btn-success"),
                        class_="text-end",
                    ) if count > 1 else None,
                    class_="maximiser-browser",
                ),
                col_widths=(7, 5),
            ) if count else ui.p("There are no additional species to add from this tree."),
        )

    @render.image(delete_file=False)
    def tree_plot():
        return {"src": div_task.result()["plot"], "style": "width: 100%; height: auto;"}

    @render.image(delete_file=False)
    def maxdiv_plot():
        return {
            "src": div_task.result()["maxdiv_plot"],
            "alt": "Vascular plant tree with observed lineages in red and diversity maximisers in blue",
            "style": "width: 100%; height: auto;",
        }

    @reactive.effect
    @reactive.event(input.next_maximiser)
    def _next_maximiser():
        count = len(div_task.result()["maximisers"])
        if count > 1:
            maximiser_index.set((maximiser_index() + 1) % count)

    @render.ui
    def maximiser_species():
        result = div_task.result()
        maximisers = result["maximisers"]
        req(not maximisers.empty)
        index = maximiser_index()
        row = maximisers.iloc[index]
        name = row["tip"].replace("_", " ")
        examples = result["maximiser_examples"]
        matches = examples.loc[examples["name"] == name] if not examples.empty else examples
        obs = matches.iloc[0] if not matches.empty else {
            "name": name,
            "first_photo": None,
            "kingdom": "Plantae",
            "phylum": None,
            "uri": "https://www.inaturalist.org/observations?" + urlencode({"taxon_name": name}),
        }
        return ui.div(
            species_highlight(
                obs,
                ui.p(ui.strong(f"+{row['gain']:,.2f}"), " branch length if you add this species"),
                ui.p(f"Species {index + 1} of {len(maximisers)}", class_="small text-muted")
                if len(maximisers) > 1 else None,
            ),
            class_="maximiser-page",
        )

    @render.data_frame
    def species_table():
        acc_df = div_task.result()["acc_df"]
        table = (
            acc_df.groupby(["accepted_family", "accepted_species"], as_index=False)
            .size()
            .rename(columns={"accepted_family": "Family", "accepted_species": "Species", "size": "Observations"})
            .sort_values(["Family", "Species"])
        )
        return render.DataGrid(table, filters=True, height="550px")

    # ---- Phytochemical diversity ------------------------------------------------------

    @ui.bind_task_button(button_id="analyse_chem_btn")
    @reactive.extended_task
    async def chem_task(udir: str):
        acc_df = get_resolved_names(udir)
        return await asyncio.to_thread(load_or_compute_phytochem, udir, acc_df)

    @reactive.effect
    @reactive.event(input.analyse_chem_btn)
    def _start_chem_analysis():
        chem_task(imported()["dir"])

    @render.ui
    def phytochem_section():
        status = chem_task.status()
        if status == "running":
            return spinner("Looking up known compounds and calculating functional diversity...")
        if status == "error":
            try:
                chem_task.result()
            except Exception as e:
                return ui.div(ui.pre(f"Analysis failed: {e}"), class_="alert alert-danger mt-3")
        if status != "success" or chem_task.result()["dir"] != imported()["dir"]:
            return ui.p(
                "Find the compounds recorded from the plants you have observed, and how chemically "
                "varied they are.",
                class_="text-muted text-center mt-3",
            )

        result = chem_task.result()
        m, compounds = result["measures"], result["compounds"]
        n_species = chem_task.result()["acc_df"]["accepted_species"].nunique()
        n_with = compounds["accepted_species"].nunique()
        if m is None:
            return ui.p("None of your observed plant species have recorded compounds.",
                        class_="text-muted text-center mt-3")
        return ui.TagList(
            ui.layout_columns(
                ui.value_box("Unique compounds", f"{int(m['GroupSize_FAD']):,}",
                             ui.p(f"{int(m['GroupSize_FAD']) / TOTAL_KNOWN_COMPOUNDS:.1%} of "
                                  f"{TOTAL_KNOWN_COMPOUNDS:,} known from vascular plants")),
                ui.value_box("Functional attribute diversity (FAD)", compact_number(m["FAD"]),
                             ui.p(f"{m['FAD_proportion']:.3%} of the FAD of all vascular plants")),
                ui.value_box("Modified FAD (MFAD)", f"{m['MFAD']:,.0f}",
                             ui.p("FAD per compound")),
                ui.value_box("Average pairwise distance", f"{m['APWD']:.3f}",
                             ui.p("0 = identical, 1 = completely dissimilar")),
                col_widths=(3, 3, 3, 3),
                class_="mt-3",
            ),
            ui.p(f"{n_with} of your {n_species} observed vascular plant species have recorded compounds. "
                 "FAD sums the structural dissimilarity between every pair of compounds, so it grows with "
                 "both the number and the variety of compounds.",
                 class_="small text-muted"),
            ui.layout_columns(
                ui.div(
                    ui.h5("Unique compounds by biosynthetic pathway"),
                    pathway_bar_chart(compounds),
                    ui.p("Pathways from NPClassifier (first assigned pathway per compound).",
                         class_="small text-muted"),
                ),
                ui.div(
                    ui.h5("Species with the most known compounds"),
                    ui.output_data_frame("compound_species_table"),
                ),
                col_widths=(7, 5),
            ),
        )

    @render.data_frame
    def compound_species_table():
        compounds = chem_task.result()["compounds"]
        table = (
            compounds.groupby(["accepted_species", "accepted_family"], as_index=False)
            .size()
            .rename(columns={"accepted_species": "Species", "accepted_family": "Family", "size": "Known compounds"})
            .sort_values("Known compounds", ascending=False)
        )
        return render.DataGrid(table, filters=True, height="450px")


app = App(app_ui, server)
