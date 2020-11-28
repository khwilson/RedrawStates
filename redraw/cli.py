"""
A CLI for manipulating NYT API election data into our format
"""
import asyncio

import click

from . import nyt, nyt2016, shared


@click.group()
def cli():
    pass


@cli.command("2016")
@click.argument("filename", type=click.Path())
@click.option(
    "--api-key",
    "-k",
    "census_api_key",
    envvar="CENSUS_API_KEY",
    help="Your Census API key",
)
def twenty_sixteen_command(filename: str, census_api_key: str):
    """
    Create the 2016 election topojson. FILENAME is the location we'll store the output.
    """
    data = nyt2016.pull_data()
    parsed = nyt2016.parse_data(data)

    tjson = shared.pull_topojson()
    gdf = shared.fix_topojson(tjson)

    # Make sure vote data and map data match
    tjson_counties = set(gdf.id)
    parsed_counties = {county.fips for county in parsed}
    assert len(tjson_counties - parsed_counties) == 0, tjson_counties - parsed_counties
    assert len(parsed_counties - tjson_counties) == 0

    # Pull populations
    pop_df = shared.pull_population(census_api_key)

    # Then merge the two together
    final = nyt2016.merge_data(parsed, gdf).merge(pop_df, on="id")
    shared.gdf_to_topojson(final, filename)


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
def twenty_twenty_command(max_connections: int, filename: str, census_api_key: str):
    """
    Pull data from the NYT API
    """
    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(
        nyt.fetch_all_states(max_connections=max_connections)
    )

    parsed = sorted(nyt.parse_data(data))

    tjson = shared.pull_topojson()
    gdf = shared.fix_topojson(tjson)

    tjson_counties = set(gdf.id)
    parsed_counties = {county.fips for county in parsed}
    assert len(tjson_counties - parsed_counties) == 0
    assert len(parsed_counties - tjson_counties) == 0

    # Pull populations
    pop_df = shared.pull_population(census_api_key)

    # Then merge the two together
    final = nyt.merge_data(parsed, gdf).merge(pop_df, on="id")
    shared.gdf_to_topojson(final, filename)


if __name__ == "__main__":
    cli()
