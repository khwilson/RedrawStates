"""
Parsing and using the MIT data::

    https://dataverse.harvard.edu/dataset.xhtml?persistentId=doi:10.7910/DVN/VOQCHQ
"""
import pandas as pd
from dataclasses import dataclass

from typing import List, Optional


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

    # NOTE: This is a bit dangerous, but the main effect is that Connecticut
    #       seems to have had about 70k write in votes in 2012 (about 2% of
    #       their total vote) which is counted at the state level and so
    #       has no FIPS attached to it.
    df = df[df["FIPS"].notna()].copy()
    df["FIPS"] = df["FIPS"].apply(lambda x: f"{int(x):05d}")
    df = df[df["year"] == year].copy()

    df["party"] = df["party"].fillna("other")

    # Fix Alaska
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

    # Fix DC
    df.loc[df["state_po"] == "DC", "county"] = "Washington"
    df.loc[df["state_po"] == "DC", "FIPS"] = "11001"

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
