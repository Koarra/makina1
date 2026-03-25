"""Module defining the main data fields obtained with EddTextParser."""
from typing import List, TypedDict


class ContractualPartnerInfo(TypedDict):
    cp_nbr: str
    name: str
    domicile: str

    activity: dict
    total_wealth_composition: dict
    source_of_wealth: dict
    corroboration: dict


class RoleHolderInfo(TypedDict):
    bo_nbr: str
    name: str
    role: str

    activity: dict
    total_wealth_composition: dict
    source_of_wealth: dict
    corroboration: dict


class TypeOfBusinessRelationship(TypedDict):
    type_of_business_relationship: str
    type: str
    motivation_dom_co: bool
    corporate_structure: bool
    complex_structure: bool
    structure_motivation_complexity: str


class EDDText(TypedDict):
    valid_file: bool
    contractual_partner_information: ContractualPartnerInfo
    role_holders_information: List[RoleHolderInfo]
    poa_list: List[str]

    type_of_business_relationship: str
    request_type: str
    org_unit: str
    ref_cases: str

    risk_category: str
    purpose_of_business_relationship: str
    expected_nnm_or_current_aum: str
    transactions: str

    # Person-specific dictionaries
    activity: List[dict]
    total_wealth_composition: List[dict]
    source_of_wealth: List[dict]
    corroboration: List[dict]
