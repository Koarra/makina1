from typing import TypedDict, List, Optional, Dict

class PEPAgentState(TypedDict):
    # Raw Data
    pep_ar: str
    pep_profile: str

    exposure_description: str
    sow_description: str
    aum_description: str

    one_liner_background: str

    review_status: str
    review_status_confidence: Optional[float]
    review_status_alternatives: Optional[Dict[str, float]]

    connection_type: str
    connection_type_confidence: Optional[float]
    connection_type_alternatives: Optional[Dict[str, float]]

    loans_debts: List[str]

    risk_flags: List[str]
    conditions: List[str]

    frontend_comments: str
    frontend_comments_confidence: Optional[float]
    frontend_comments_alternatives: Optional[Dict[str, float]]
