from typing import List, Literal, TypedDict

from pydantic import BaseModel, Field


class ActivitiesDetails(TypedDict):
    year_joined: str
    year_left: str
    job_position: str
    company: str
    salary: str
    industry: str


class Activities(TypedDict):
    activities: List[ActivitiesDetails]


class BankableAssetsDetails(TypedDict):
    asset_description: str
    amount: str
    currency: str
    type: str
    bank: str
    location: str


class BankableAssets(TypedDict):
    assets: List[BankableAssetsDetails]


class RealEstateAssets(TypedDict):
    asset_description: str
    value: str
    currency: str
    type: str
    location: str


class RealEstate(TypedDict):
    assets: List[RealEstateAssets]


class PrivateEquityAssets(TypedDict):
    asset_description: str
    value: str
    currency: str
    company_name: str
    percentage_ownership: str


class PrivateEquity(TypedDict):
    assets: List[PrivateEquityAssets]


class OtherAssetsDetails(TypedDict):
    asset_description: str
    value: str
    currency: str


class OtherAssets(TypedDict):
    assets: List[OtherAssetsDetails]


class SowSummary(TypedDict):
    sow_description: str
    sow_plausibility: Literal[
        "SoW is considered plausible.", "SoW is not considered plausible."
    ]


class SummarizeReport(BaseModel):
    request_type: str = Field(description="Categories: A, B, C")
    decision: str = Field(description="Decisions: reject, accept")
    justification: str


class SummarizePurposeOfBr(BaseModel):
    summary: str = Field(description="Summary of the text")


class TrxPattern(BaseModel):
    anticipated_pattern: str
