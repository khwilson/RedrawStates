"""
Interacting with the NYT Elections data API for 2020
"""
import asyncio
import dataclasses
import importlib
import importlib.resources
from collections import defaultdict, namedtuple
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from pathlib import PosixPath
from urllib.parse import urlsplit

import aiohttp
import geopandas as gpd
import pandas as pd
import requests
import us

from .constants import CACHE_DIR

COUNTY_TIGER = "https://www2.census.gov/geo/tiger/TIGER{year}/COUNTY/tl_{year}_us_county.zip"


class KEYS(StrEnum):
    """
    Keys to access eletion results by candidate
    """

    HARRIS = "harris-k"
    TRUMP = "trump-d"
    KENNEDY = "kennedy-r"
    STEIN = "stein-j"


@dataclass(frozen=True, order=True)
class CountyResult:
    """
    A representation of a result in a particular county
    """

    state: str
    county: str
    fips: str
    harris_vote: int
    trump_vote: int
    kennedy_vote: int
    stein_vote: int


@contextmanager
def open_or_download(url: str, force: bool = False):
    path = CACHE_DIR / PosixPath(urlsplit(url).path).name

    if force or (not path.exists()):
        CACHE_DIR.mkdir(parents=True, exist_ok=True)

        with requests.get(url, stream=True) as resp:
            resp.raise_for_status()
            with open(path, "wb") as outfile:
                for chunk in resp.iter_content(8192):
                    outfile.write(chunk)

    with open(path, "rb") as infile:
        yield infile


@lru_cache
def get_fips_to_county_name(force: bool = False) -> dict[str, str]:
    """
    Returns a map from five-digit FIPS to county name
    """
    with open_or_download(COUNTY_TIGER.format(year=2023, force=force)) as infile:
        co_df = gpd.read_file(infile)

    return dict(
        zip(
            co_df["STATEFP"] + co_df["COUNTYFP"],
            co_df["NAME"],
        )
    )


def generate_ct_mapping(force: bool = False) -> tuple[dict[str, str], list[tuple[str, str]]]:
    """

    Returns:
        * Map from old county + town FIPS to new county fips
        * List of pairs (county fips, name)
    """
    with importlib.resources.open_text("redraw.resources", "ct2022tractcrosswalk.csv") as infile:
        df = pd.read_csv(infile)

    # Old county + Town FIPS
    df["town_fips_2020"] = df["town_fips_2020"].astype(str)
    df["town_fips_2022"] = df["town_fips_2022"].astype(str)
    df["Tract_fips_2022"] = df["Tract_fips_2022"].astype(str)
    county_town_to_new_county = dict(zip(df["town_fips_2020"].str[1:], df["town_fips_2022"].str[1:4]))

    # Make the names short enough to fit on screen
    cogs = [
        ("110", "Capitol"),
        ("120", "Bridgeport"),
        ("130", "Lower CT"),
        ("140", "Naugatuck"),
        ("150", "NE CT"),
        ("160", "NW Hills CT"),
        ("170", "S Central CT"),
        ("180", "SE CT"),
        ("190", "Western CT"),
    ]

    return county_town_to_new_county, cogs


def fix_state_name(state_name: str) -> str:
    """
    Convert a state name to the format the NYT API expects

    Args:
        state_name: The formal state name, e.g., "West Virginia"

    Returns:
        The converted name, e.g., "west-virginia"
    """
    return state_name.lower().strip().replace(" ", "-")


async def fetch_state(
    session: aiohttp.ClientSession,
    sem: asyncio.Semaphore,
    state_name: str,
    num_attempts: int = 3,
) -> dict:
    """
    Fetch a particular state's data from the NYT API.

    Args:
        session: An aiohttp ClientSession in which to fetch the data
        sem: A semaphore to bound the maximum number of simultaneous
             hits to the NYT API (be kind!)
        state_name: The state name spelled like "North Carolina" to pull
        num_attempts: The maximum number of retries in case something goes wrong

    Returns:
        The raw data from the NYT API
    """
    state_name = fix_state_name(state_name)
    url = f"https://static01.nyt.com/elections-assets/pages/data/2024-11-05/results-{state_name}-president.json"
    for num_attempt in range(num_attempts):
        async with sem:
            async with session.get(url) as response:
                if response.ok:
                    await asyncio.sleep(2 ** (num_attempt - 2))
                    return await response.json()
        await asyncio.sleep(2 ** (num_attempt - 2))

    raise EnvironmentError(
        f"Something went wrong after {num_attempts} to pull {state_name} data"
    )


async def fetch_all_states(
    max_connections: int = 3, num_attempts_per_state: int = 3
) -> dict[str, dict]:
    """
    Pull the data from _all_ states that vote in the US
    presidential election from the NYT API

    Args:
        max_connections: The maximum number of connections to the NYT API at a time
        num_attempts_per_state: The maximum number of pull attempts to make per state
            before erroring

    Returns:
        [state abbreviation] -> [raw data from NYT]
    """
    sem = asyncio.Semaphore(max_connections)

    tmp = namedtuple("state_tmp", ["name", "abbr"])
    states = us.STATES + [tmp("washington dc", "DC")]

    async with aiohttp.ClientSession() as session:
        data = await asyncio.gather(
            *[
                fetch_state(
                    session, sem, state.name, num_attempts=num_attempts_per_state
                )
                for state in states
            ]
        )

    return {state.abbr: datum for state, datum in zip(states, data)}


def parse_data(results: dict[str, dict]) -> list[CountyResult]:
    """
    Parse the raw data into a CSV that can be written to disk
    """
    county_fips_to_name = get_fips_to_county_name()
    output = []
    for state, data in results.items():
        if state not in ["AK", "DC", "CT", "MA", "ME", "VT", "NH", "RI"]:
            for county_data in data["races"][0]["reporting_units"]:
                if county_data["level"] != "county":
                    continue

                votes = {
                    c["nyt_id"]: c["votes"]["total"]
                    for c in county_data["candidates"]
                }

                output.append(
                    CountyResult(
                        state=state,
                        county=county_data["name"],
                        fips=county_data["fips_state"] + county_data["fips_county"],
                        harris_vote=votes.get(KEYS.HARRIS, 0),
                        trump_vote=votes.get(KEYS.TRUMP, 0),
                        kennedy_vote=votes.get(KEYS.KENNEDY, 0),
                        stein_vote=votes.get(KEYS.STEIN, 0),
                    )
                )

        elif state == "CT":
            # CT got rid of their counties in 2022 for Census purposes
            # So we have to do some surgery
            county_to_cog, cogs = generate_ct_mapping()

            counts = {
                fips: {
                    val: 0 for val in KEYS
                }
                for fips, _ in cogs
            }

            for township_data in data["races"][0]["reporting_units"]:
                if township_data["level"] != "township":
                    continue

                votes = {
                    c["nyt_id"]: c["votes"]["total"]
                    for c in township_data["candidates"]
                }

                for key in KEYS:
                    counts[county_to_cog[township_data["fips_county"] + township_data["fips_suffix"]]][key] += votes.get(key, 0)

            for fips, name in cogs:
                output.append(
                    CountyResult(
                        state="CT",
                        county=name,
                        fips=f"09{fips}",
                        harris_vote=counts[fips][KEYS.HARRIS],
                        trump_vote=counts[fips][KEYS.TRUMP],
                        kennedy_vote=counts[fips][KEYS.KENNEDY],
                        stein_vote=counts[fips][KEYS.STEIN],
                    )
                )

        elif state in ["MA", "ME", "VT", "NH", "RI"]:
            # The New England townships are very annoying
            counts = defaultdict(lambda: {val: 0 for val in KEYS})

            for township_data in data["races"][0]["reporting_units"]:
                if township_data["level"] != "township":
                    continue

                votes = {
                    c["nyt_id"]: c["votes"]["total"]
                    for c in township_data["candidates"]
                }

                for key in KEYS:
                    counts[township_data["fips_county"]][key] += votes.get(key, 0)

            state_fips = {
                "MA": 25,
                "ME": 23,
                "VT": 50,
                "NH": 33,
                "RI": 44,
            }[state]
            for fips, vals in counts.items():
                full_fips = f"{state_fips}{fips}"
                output.append(
                    CountyResult(
                        state=state,
                        county=county_fips_to_name[full_fips],  # Not sure if I actually need the name...
                        fips=full_fips,
                        harris_vote=vals[KEYS.HARRIS],
                        trump_vote=vals[KEYS.TRUMP],
                        kennedy_vote=vals[KEYS.KENNEDY],
                        stein_vote=vals[KEYS.STEIN],
                    )
                )

        else:
            # AK and DC behave differently than others
            votes = {
                c["nyt_id"]: c["votes"]["total"]
                for c in data["races"][0]["reporting_units"][0]["candidates"]
            }

            output.append(
                CountyResult(
                    state=state,
                    county="Washington" if state == "DC" else "Alaska",
                    fips="11001" if state == "DC" else "02000",
                    harris_vote=votes.get(KEYS.HARRIS, 0),
                    trump_vote=votes.get(KEYS.TRUMP, 0),
                    kennedy_vote=votes.get(KEYS.KENNEDY, 0),
                    stein_vote=votes.get(KEYS.STEIN, 0),
                )
            )
    return output


def merge_data(parsed: list[CountyResult], gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    """
    Merge together the parsed data from `parsed_data` with the GeoDataFrame
    from the Census. Note that this standardizes for the column headers the
    javascript app expects.
    """
    df = pd.DataFrame(
        [dataclasses.astuple(row) for row in parsed],
        columns=[field.name for field in dataclasses.fields(CountyResult)],
    )

    gdf = gdf.merge(df.drop(columns=["state"]), left_on="id", right_on="fips")
    gdf = gdf.rename(
        columns={"harris_vote": "dem", "trump_vote": "gop", "stein_vote": "grn", "kennedy_vote": "una"}
    )
    gdf["lib"] = 0

    return gdf
