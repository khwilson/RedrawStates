"""
A CLI for manipulating NYT API election data into our format
"""
import asyncio
import os
import pickle
from pathlib import Path

import click
from dotenv import load_dotenv

from . import mit, nyt, nyt2016, shared

load_dotenv()

CACHE_DIR = Path(os.environ.get("REDRAW_CACHE_DIR", ".redraw_cache"))


@click.group()
def cli():
    pass


@cli.command("mit")
@click.argument("year", type=int)
@click.argument("input_filename", type=click.Path())
@click.argument("output_filename", type=click.Path())
@click.option(
    "--api-key",
    "-k",
    "census_api_key",
    envvar="CENSUS_API_KEY",
    help="Your Census API key",
)
def mit_command(
    year: int, input_filename: str, output_filename: str, census_api_key: str
):
    click.echo("Reading and parsing data...")
    data = mit.read_data(input_filename, year)
    parsed = mit.parse_data(data)

    click.echo("Getting county boundaries from Census...")
    tjson = shared.get_county_boundaries(year)

    click.echo("Flattening counties...")
    gdf = shared.flatten_counties(tjson)

    tjson_counties = set(gdf.id)
    parsed_counties = {county.fips for county in parsed}
    assert (
        len(tjson_counties - parsed_counties) == 0
    ), f"{tjson_counties - parsed_counties}"
    assert (
        len(parsed_counties - tjson_counties) == 0
    ), f"{parsed_counties - tjson_counties}"

    # Pull populations
    click.echo("Getting populations from Census...")
    pop_df = shared.pull_population(census_api_key, year=year)

    # Then merge the two together
    click.echo("Merging data and geographies...")
    final = mit.merge_data(parsed, gdf).merge(pop_df, on="id")

    click.echo("Topojsonifying...")
    shared.gdf_to_topojson(final, output_filename)

    click.echo("Done.")


@cli.command("2016")
@click.argument("filename", type=click.Path())
@click.option(
    "--api-key",
    "-k",
    "census_api_key",
    envvar="CENSUS_API_KEY",
    help="Your Census API key",
)
@click.option(
    "--force", "-f", "force", is_flag=True, help="Force redownloading NYT data"
)
def twenty_sixteen_command(filename: str, census_api_key: str, force: bool = False):
    """
    Create the 2016 election topojson. FILENAME is the location we'll store the output.
    """
    CACHE_DIR.mkdir(exist_ok=True)
    results_cache_file = CACHE_DIR / "nyt2016.pkl"

    click.echo("Pulling data from NYT...")
    if force or not results_cache_file.exists():
        data = nyt2016.pull_data()
        parsed = nyt2016.parse_data(data)
        with open(results_cache_file, "wb") as outfile:
            pickle.dump(parsed, outfile)
    else:
        with open(results_cache_file, "rb") as infile:
            parsed = pickle.load(infile)

    click.echo("Getting county boundaries from Census...")
    tjson = shared.get_county_boundaries(2016)

    click.echo("Flattening counties...")
    gdf = shared.flatten_counties(tjson)

    # Make sure vote data and map data match
    tjson_counties = set(gdf.id)
    parsed_counties = {county.fips for county in parsed}
    assert len(tjson_counties - parsed_counties) == 0, tjson_counties - parsed_counties
    assert len(parsed_counties - tjson_counties) == 0

    # Pull populations
    click.echo("Getting populations from Census...")
    pop_df = shared.pull_population(census_api_key)

    # Then merge the two together
    click.echo("Merging data...")
    final = nyt2016.merge_data(parsed, gdf).merge(pop_df, on="id")

    click.echo("Simplifying and writing...")
    shared.gdf_to_topojson(final, filename)

    click.echo("Done.")


@cli.command("2020")
@click.argument("filename", type=click.Path())
@click.option(
    "--api-key",
    "-k",
    "census_api_key",
    envvar="CENSUS_API_KEY",
    help="Your Census API key",
)
@click.option(
    "--max-connections",
    "-m",
    "max_connections",
    default=3,
    help="The maximum number of connections to open to the NYT API",
)
@click.option(
    "--force", "-f", "force", is_flag=True, help="Force redownloading NYT data"
)
def twenty_twenty_command(
    max_connections: int, filename: str, census_api_key: str, force: bool = False
):
    """
    Pull data from the NYT API
    """
    CACHE_DIR.mkdir(exist_ok=True)
    results_cache_file = CACHE_DIR / "nyt2020.pkl"

    click.echo("Pulling data from NYT...")
    if force or not results_cache_file.exists():
        loop = asyncio.get_event_loop()
        data = loop.run_until_complete(
            nyt.fetch_all_states(max_connections=max_connections)
        )

        click.echo("Parsing data...")
        parsed = sorted(nyt.parse_data(data))

        with open(results_cache_file, "wb") as outfile:
            pickle.dump(parsed, outfile)
    else:
        with open(results_cache_file, "rb") as infile:
            parsed = pickle.load(infile)

    click.echo("Getting county boundaries from Census...")
    tjson = shared.get_county_boundaries(2019)

    click.echo("Flattening counties...")
    gdf = shared.flatten_counties(tjson)

    tjson_counties = set(gdf.id)
    parsed_counties = {county.fips for county in parsed}
    assert len(tjson_counties - parsed_counties) == 0
    assert len(parsed_counties - tjson_counties) == 0

    # Pull populations
    click.echo("Getting populations from Census...")
    pop_df = shared.pull_population(census_api_key)

    # Then merge the two together
    click.echo("Merging data and geographies...")
    final = nyt.merge_data(parsed, gdf).merge(pop_df, on="id")

    click.echo("Topojsonifying...")
    shared.gdf_to_topojson(final, filename)

    click.echo("Done.")


if __name__ == "__main__":
    cli()
