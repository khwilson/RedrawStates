"""
A file for shared utilities
"""
import json
import subprocess
import tempfile
import time
from pathlib import Path

import geopandas as gpd
import pandas as pd
import requests
import us
from census import Census


def pull_population(api_key: str, year: int = 2020) -> pd.DataFrame:
    """
    Pull county population data from the Census API. Also, make some clean ups
    for our data set. In particular:
        * Make Alaska one county
        * Change Shannon County, SD, to Ogala Lakota County, SD.

    Args:
        api_key: Your census API key
        year: The decennial Census year you're using. Must be in [1990, 2022)

    Returns:
        A DataFrame with columns "id" (which is the 5-digit county FIPS as a str) and
            "population" which is the integer population.
    """
    decennial_year = ((year - 2) // 10) * 10
    if decennial_year not in [1990, 2000, 2010]:
        raise ValueError(f'Year must be in [1992, 2022), not {year}')

    census = Census(api_key)
    df = pd.DataFrame(census.sf1.state_county("P001001", "*", "*", year=decennial_year)).rename(
        columns={"P001001": "population"}
    )
    df["population"] = df["population"].astype(int)

    # Fix Alaska
    just_alaska = df[df["state"] == "02"]
    just_alaska = pd.DataFrame(
        {
            "state": ["02"],
            "county": ["000"],
            "population": [just_alaska["population"].sum()],
        }
    )
    df = pd.concat([df[df["state"] != "02"], just_alaska])

    df["id"] = df["state"] + df["county"]
    df = df.drop(columns=["state", "county"])

    # Finally, Shannon County South Dakota got renamed in 2015. Fix this.
    if year >= 2015:
        df["id"] = df["id"].apply(lambda x: "46102" if x == "46113" else x)

    return df


def get_county_boundaries(year: int) -> gpd.GeoDataFrame:
    # For now, we take the year to be 2011 or later because TIGER totally
    # rearranged its files in 2011, making this function a lot harder to accomplish.
    year = max(year, 2011)
    gdf = gpd.read_file(f'https://www2.census.gov/geo/tiger/TIGER{year}/COUNTY/tl_{year}_us_county.zip')
    gdf = gdf[['GEOID', 'NAME', 'geometry']].rename(columns={'GEOID': 'id', 'NAME': 'name'})
    gdf['name'] = gdf['name'].apply(lambda x: x.decode('latin1') if type(x) == bytes else x)
    return gdf


def flatten_counties(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Make some adjustments to the topojson file we pull to align to
    election data we pull from the NYT.
    """
    fips_to_state = {
        state.fips: state.abbr for state in us.STATES + [us.states.lookup("DC")]
    }
    gdf["state"] = gdf["id"].apply(lambda x: x[:2]).map(fips_to_state)

    # Merge all of Alaska
    just_alaska = gdf[gdf["state"] == "AK"].copy()
    just_alaska["merger"] = 0
    just_alaska = (
        just_alaska.dissolve(by="merger").reset_index().drop(columns=["merger"])
    )
    just_alaska["id"] = "02000"
    just_alaska["name"] = "Alaska"

    final_gdf = pd.concat([gdf[gdf["state"] != "AK"], just_alaska])

    # Drop Kalawao County, HI, as it causes issues
    final_gdf = final_gdf[final_gdf["id"] != "15005"].copy()

    # Drop counties with high FIPS codes
    max_fips = max(int(state.fips) for state in us.STATES)  # Should be Wyoming
    final_gdf = final_gdf[
        final_gdf["id"].apply(lambda x: int(x[:2]) <= max_fips)
    ].copy()

    return final_gdf


def gdf_to_topojson(gdf: gpd.GeoDataFrame, filename: str):
    """
    Write gdf to a topojson at filename.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        tmpdir = Path(tmpdir)
        gdf.to_file(tmpdir / "tmp.json", driver="GeoJSON")
        proc = subprocess.run(
            ["geo2topo", f"counties={str(tmpdir / 'tmp.json')}"],
            capture_output=True,
            check=True,
        )

    output = proc.stdout
    with open(filename, "wb") as outfile:
        outfile.write(output)
