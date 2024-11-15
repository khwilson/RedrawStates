"""
Parsing and using the MIT data::

    https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/VOQCHQ
"""

import dataclasses
from dataclasses import dataclass
from typing import List, Optional

import geopandas as gpd
import pandas as pd


@dataclass(frozen=True, order=True)
class CountyResult:
    """
    A representation of a result in a particular county
    """

    state: str
    county: str
    fips: str
    dem_vote: int
    gop_vote: int
    green_vote: Optional[int]
    other_vote: Optional[int]


def read_data(filename: str, year: int) -> pd.DataFrame:
    df = pd.read_csv(filename)

    # Drop all rows without a FIPS code
    #
    # NOTE: This is a bit dangerous, but the main effect is that Connecticut
    #       seems to have had about 70k write in votes in 2012 (about 2% of
    #       their total vote) which is counted at the state level and so
    #       has no FIPS attached to it.
    df = df[df["FIPS"].notna()].copy()
    df["FIPS"] = df["FIPS"].apply(lambda x: f"{int(x):05d}")
    df = df[df["year"] == year].copy()

    df["party"] = df["party"].fillna("other")

    # Merge all of Alaska's election districts (which do not really align
    # with their counties) into just the whole state.
    ak_only = df[df["state_po"] == "AK"]
    ak_only = (
        ak_only.groupby(
            ["year", "state", "state_po", "office", "party", "candidate", "version"]
        )["candidatevotes"]
        .sum()
        .reset_index()
    )
    ak_only["county"] = "Alaska"
    ak_only["FIPS"] = "02000"
    ak_only["totalvotes"] = ak_only.groupby("county")["candidatevotes"].transform("sum")

    df = pd.concat([df[df["state_po"] != "AK"], ak_only])

    # Keep our conventions for the name of DC's "county" (Washington) and
    # its FIPS code (which is its actual FIPS code)
    df.loc[df["state_po"] == "DC", "county"] = "Washington"
    df.loc[df["state_po"] == "DC", "FIPS"] = "11001"

    # Kansas City, Missouri, spans parts of four counties. The MIT data reports
    # the results for KCMO separately (with FIPS 36000). We follow what appears to be
    # the New York Times' convention and simply add these votes to Jackson County's
    # total (FIPS 29095)
    kcmo_only = df[df["FIPS"].isin(["36000", "29095"])]
    kcmo_only = (
        kcmo_only.groupby(
            ["year", "state", "state_po", "office", "party", "candidate", "version"]
        )["candidatevotes"]
        .sum()
        .reset_index()
    )
    kcmo_only["county"] = "Jackson"
    kcmo_only["FIPS"] = "29095"
    kcmo_only["totalvotes"] = kcmo_only.groupby("county")["candidatevotes"].transform(
        "sum"
    )

    df = pd.concat([df[~df["FIPS"].isin(["36000", "29095"])], kcmo_only])

    # Broomfield County, Colorado, came into being in 2001. However, the Census
    # doesn't have easily parsed cartographic boundaries for the years 2001-2009.
    # As such, we just merge Broomfield (FIPS 08014) into Boulder (FIPS 08013)
    # for the years 2004 and 2008
    if year == 2004 or year == 2008:
        brco_only = df[df["FIPS"].isin(["08013", "08014"])]
        brco_only = (
            brco_only.groupby(
                ["year", "state", "state_po", "office", "party", "candidate", "version"]
            )["candidatevotes"]
            .sum()
            .reset_index()
        )
        brco_only["county"] = "Boulder"
        brco_only["FIPS"] = "08013"
        brco_only["totalvotes"] = brco_only.groupby("county")[
            "candidatevotes"
        ].transform("sum")

        df = pd.concat([df[~df["FIPS"].isin(["08013", "08014"])], brco_only])

    return df


def parse_data(df: pd.DataFrame) -> List[CountyResult]:
    # Pivot the data and if greens are not present add them
    df = (
        df[["state_po", "county", "FIPS", "party", "candidatevotes"]]
        .pivot_table(
            index=["state_po", "county", "FIPS"],
            columns="party",
            values="candidatevotes",
            aggfunc="sum",
        )
        .fillna(0)
        .astype(int)
        .reset_index()
    )

    if "green" not in df.columns:
        df["green"] = 0

    output = []
    for _, row in df.iterrows():
        output.append(
            CountyResult(
                state=row["state_po"],
                county=row["county"],
                fips=row["FIPS"],
                dem_vote=row["democrat"],
                gop_vote=row["republican"],
                green_vote=row["green"],
                other_vote=row["other"],
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
            "dem_vote": "dem",
            "gop_vote": "gop",
            "green_vote": "grn",
            "other_vote": "oth",
        }
    )
    gdf["una"] = 0

    return gdf
