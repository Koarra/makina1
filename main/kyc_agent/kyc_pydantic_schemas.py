from typing import List

from pydantic import BaseModel, Field


class SubscriptableBaseModel(BaseModel):
    def __getitem__(self, item):
        return getattr(
            self, item
        )  # see https://github.com/pydantic/pydantic/discussions/3463#discussioncomment-1720734


class PurposeOfBusinessRelationship(SubscriptableBaseModel):
    sufficient_explanation: bool = Field(
        description="Whether the details provided in kyc purpose of br justify "
        "the transaction value present in kyc transactions"
    )
    reasoning: str = Field(description="The reason behind the explanation robustness")


class TransactionDetail(SubscriptableBaseModel):
    amount: float = Field(description="Transaction amount")
    date: str = Field(description="Transaction date in YYYY-MM-DD format")
    currency: str = Field(description="Transaction currency code (e.g., USD, EUR)")


class CheckTransactionSummary(SubscriptableBaseModel):
    transactions_exist: bool = Field(
        description="True if any transactions are found, otherwise False"
    )
    transactions_details: List[TransactionDetail] = Field(
        description="A list of summarized transactions with amount, date, and currency"
    )


class CompletenessOriginOfAssets(SubscriptableBaseModel):
    complete: bool = Field(
        description="Whether the origin of assets is complete or not"
    )
    reason: str = Field(description="The reason behind the completion status")


class EvaluateTotalAssets(SubscriptableBaseModel):
    kyc_origin_of_assets: float = Field(
        description="The total value of kyc_origin_of_asset"
    )


class CompareRemarksWithTotalAssets(SubscriptableBaseModel):
    sufficient_explanation: str = Field(
        description="Remarks justify the value of Total Assets"
    )
    reasoning: str = Field(
        description="A reasoning describing and justifying the sufficient explanation"
    )


class CrossChecks(SubscriptableBaseModel):
    reasoning: str = Field(
        description="Reasoning used to justify if the person is mentionned in the snippet"
    )
    answer: str = Field(description="Answer if the person is mentionned in the snippet")


class FamilyMember(SubscriptableBaseModel):
    name: str = Field(description="The name of the person")
    relation: str = Field(description="the relation type to the client")
    source_of_wealth_relevant: str = Field(
        description="whether this person contributes or has contributed to the client's wealth, e.g. through a donation, inheritance, etc."
    )
    politically_exposed: str = Field(
        description="whether this person is marked as PEP (politically exposed person) in the notes"
    )


class FamilyMembersList(SubscriptableBaseModel):
    family_members: List[FamilyMember] = Field(description="The list of family members")


class ContradictionChecks(BaseModel):
    contradictory: bool = Field(
        description="Contradiction between details in field_value and other_fields"
    )
    reasoning: str = Field(description="Reasoning of the contradictory")
    confidence_level: float = Field(description="Confidence level of the contradictory")


class CompositionOfTotalAssets(SubscriptableBaseModel):
    total_assets_remarks: float = Field(
        description="The total value of kyc_origin_of_asset"
    )
