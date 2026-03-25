from typing import Any, Dict, TypedDict


class CheckResult(TypedDict, total=False):
    status: bool
    reason: str


class KycState(TypedDict, total=False):
    partner_name: str
    folder_name: str
    ou_code_mapped: str
    output_folder: str
    partner_info: Any
    kyc_total_assets: float
    percentage_of_specific_asset_fields_explaining_total_assets: float
    percentage_of_total_assets_with_known_origin: float
    kyc_dict: Dict
    edd_parsed: Dict
    pep_sensitivity_present: bool
    # Section check outputs (populated progressively by each node)
    purpose_of_business_relationships: CheckResult
    origin_of_asset: CheckResult
    total_assets: CheckResult
    remarks_on_total_assets_and_composition: CheckResult
    activity: CheckResult
    family_situation: CheckResult
    consistency_checks_pep_asm: CheckResult
    consistency_checks_within_kyc_contradiction_checks: CheckResult
    scap_flags: CheckResult
    siap_flags: CheckResult
    siap_checks: Dict
