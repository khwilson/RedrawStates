"""
Pulling 2016 election data
"""

import dataclasses
import json
import time
from dataclasses import dataclass
from enum import Enum
from typing import List

import geopandas as gpd
import pandas as pd
import requests

URL = "https://www.nytimes.com/elections/2016/results/president"


class KEYS(str, Enum):
    """
    Keys to access eletion results by candidate
    """

    CLINTON = "clintonh"
    TRUMP = "trumpd"
    STEIN = "steinj"
    JOHNSON = "johnsong"
    MCMULLIN = "mcmulline"

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
    clinton_vote: int
    trump_vote: int
    stein_vote: int
    johnson_vote: int
    mcmullin_vote: int


def pull_data(url: str = URL, num_attempts: int = 3) -> list:
    """
    Pull data from the NYT 2016 election coverage.

    Args:
        url: The url of the election coverage
        num_attempts: The number of HTTP retries

    Return:
        The raw dictionary of their election coverage
    """
    data = None
    for num_attempt in range(num_attempts):

        try:
            response = requests.get(url)
            response.raise_for_status()
            data = response.content.decode("utf8")
            break
        except requests.exceptions.HTTPError:
            time.sleep(2 ** (num_attempt - 2))
            continue

    if not data:
        raise ValueError(f"Could not pull {url}")

    for line in data.split("\n"):
        line = line.strip()
        if line.startswith("eln_races = "):
            line = line[len("eln_races = ") : -1]
            parsed = json.loads(line)
            break

    return parsed


def parse_data(results: list) -> List[CountyResult]:
    """
    Convert the raw json of the election results into an
    easier to manipulate format.

    Args:
        results: The output of `pull_data`

    Return:
        The collection of results by county in the data
    """
    output = []
    for state_data in results:
        state = state_data["state_id"]
        county_data = state_data["counties"]
        for county in county_data:
            name = county["name"] if state != "DC" else "Washington"
            output.append(
                CountyResult(
                    state=state,
                    county=name,
                    fips=county["fips"],
                    clinton_vote=county["results"].get(str(KEYS.CLINTON), 0),
                    trump_vote=county["results"].get(str(KEYS.TRUMP), 0),
                    stein_vote=county["results"].get(str(KEYS.STEIN), 0),
                    johnson_vote=county["results"].get(str(KEYS.JOHNSON), 0),
                    mcmullin_vote=county["results"].get(str(KEYS.MCMULLIN), 0),
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
        columns={
            "clinton_vote": "dem",
            "trump_vote": "gop",
            "stein_vote": "grn",
            "johnson_vote": "lib",
            "mcmullin_vote": "una",
        }
    )
    return gdf
