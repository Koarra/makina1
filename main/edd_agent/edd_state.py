from typing import Dict, List, TypedDict


class EddState(TypedDict, total=False):
    file_path: str
    raw_text: str
    dict_parsed_text: Dict[str, str]
    type_of_business_relationship: str
    request_type: str
    risk_category: str
    purpose_of_business_relationship: str
    expected_nnm_or_current_aum: str
    expected_transactions: str
    activity: str
    total_wealth_composition: str
    source_of_wealth: str
    corroboration: str
    negative_news: str
    other_risk_aspects: str
    other_relevant_information: str
    final_summary: str
    raw_data: Dict[str, str]
    role_holders_to_process: List
