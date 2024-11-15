"""
Interacting with the NYT Elections data API for 2020
"""

import asyncio
import dataclasses
from dataclasses import dataclass
from enum import Enum
from typing import Dict, List

import aiohttp
import geopandas as gpd
import pandas as pd
import us


class KEYS(str, Enum):
    """
    Keys to access eletion results by candidate
    """

    BIDEN = "bidenj"
    TRUMP = "trumpd"
    JORGENSEN = "jorgensenj"

    def __str__(self) -> str:
        return str.__str__(self)


@dataclass(frozen=True, order=True)
class CountyResult:
    """
    A representation of a result in a particular county
    """

    state: str
    county: str
    fips: str
    biden_vote: int
    trump_vote: int
    jorgensen_vote: int


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
    url = f"https://static01.nyt.com/elections-assets/2020/data/api/2020-11-03/race-page/{state_name}/president.json"
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
) -> Dict[str, dict]:
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
    states = us.STATES + [us.states.DC]
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


def parse_data(results: Dict[str, dict]) -> List[CountyResult]:
    """
    Parse the raw data into a CSV that can be written to disk
    """
    output = []
    for state, data in results.items():
        if state not in ["AK", "DC"]:
            for county_data in data["data"]["races"][0]["counties"]:
                output.append(
                    CountyResult(
                        state=state,
                        county=county_data["name"],
                        fips=county_data["fips"][-5:],
                        biden_vote=county_data["results"].get(KEYS.BIDEN, 0),
                        trump_vote=county_data["results"].get(KEYS.TRUMP, 0),
                        jorgensen_vote=county_data["results"].get(KEYS.JORGENSEN, 0),
                    )
                )
        else:
            # AK and DC behave slightly differently
            county = "Alaska" if state == "AK" else "Washington"
            deep_data = data["data"]["races"][0]["counties"]
            output.append(
                CountyResult(
                    state=state,
                    county=county,
                    fips="02000" if state == "AK" else "11001",
                    biden_vote=sum(
                        county_data["results"].get(KEYS.BIDEN, 0)
                        for county_data in deep_data
                    ),
                    trump_vote=sum(
                        county_data["results"].get(KEYS.TRUMP, 0)
                        for county_data in deep_data
                    ),
                    jorgensen_vote=sum(
                        county_data["results"].get(KEYS.JORGENSEN, 0)
                        for county_data in deep_data
                    ),
                )
            )
    return output


def merge_data(parsed: List[CountyResult], gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
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
        columns={"biden_vote": "dem", "trump_vote": "gop", "jorgensen_vote": "lib"}
    )
    gdf["grn"] = 0
    gdf["una"] = 0

    return gdf
