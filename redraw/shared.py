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

TOPOJSON_URL = "https://cdn.jsdelivr.net/npm/us-atlas@3/counties-10m.json"


def pull_population(api_key: str) -> pd.DataFrame:
    """
    Pull county population data from the Census API. Also, make some clean ups
    for our data set. In particular:
        * Make Alaska one county
        * Change Shannon County, SD, to Ogala Lakota County, SD.

    Args:
        api_key: Your census API key

    Returns:
        A DataFrame with columns "id" (which is the 5-digit county FIPS as a str) and
            "population" which is the integer population.
    """
    census = Census(api_key)
    df = pd.DataFrame(census.sf1.state_county("P001001", "*", "*")).rename(
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
    df["id"] = df["id"].apply(lambda x: "46102" if x == "46113" else x)
    return df


def pull_topojson(url: str = TOPOJSON_URL, num_attempts: int = 3) -> dict:
    """
    Pull a US topojson file from `url`. Attempt it `num_attempts` times
    with exponential backoff
    """
    data = None
    for num_attempt in range(num_attempts):
        try:
            response = requests.get(url, stream=True)
            response.raise_for_status()
            break
        except requests.exceptions.HTTPError:
            time.sleep(2 ** (num_attempt - 2))
            continue

    data = response.content.decode("utf8")
    return json.loads(data)


def fix_topojson(topojson: dict):
    """
    Make some adjustments to the topojson file we pull to align to
    election data we pull from the NYT.
    """
    with tempfile.NamedTemporaryFile("wt") as outfile:
        json.dump(topojson, outfile)
        outfile.flush()
        gdf = gpd.read_file(outfile.name)

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
