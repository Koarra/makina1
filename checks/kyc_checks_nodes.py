from constants import COMPARE_TRANSACTIONS_PURPOSE_OF_BR_PROMPT, SUMMARIZE_TRANSACTIONS_PROMPT
from models import PurposeOfBusinessRelationship, CheckTransactionSummary
from kyc_agent.checks import purpose_of_business_relationship, run_compliance_check, summarise_transactions
from utils.func_utils import save_json
from utils.logger_config import setup_logger

logger = setup_logger(__name__)


def run_section_purpose_of_business_relationship(
    partner_info,
    partner_name: str, 
    folder_name: str,
    ou_code_mapped: str,
    kyc_checks_output: dict,
    output_folder: str,
    llm,
) -> None:
    """Section 3: Purpose of the Business Relationship (checks 3.1, 3.2, 3.3)."""

    logger.info(
        "========== START SECTION 3: Purpose of the Business Relationship (checks 3.1, 3.2, 3.3). =========="
    )

    kyc_transactions = partner_info.kyc_dataset["transactions"]
    kyc_purpose_of_br = partner_info.kyc_dataset["purpose_of_br"]
    kyc_transactions_str = (
        str(kyc_transactions) if kyc_transactions else "No kyc transactions extracted"
    )

    kyc_purpose_of_br_str = (
        str(kyc_purpose_of_br)
        if kyc_purpose_of_br
        else "No kyc purpose of br text extracted"
    )

    # Check 3.1: BR vs transactions
    logger.info("check 3.1 started")
    purpose_of_business_relationship_prompt = (
        COMPARE_TRANSACTIONS_PURPOSE_OF_BR_PROMPT.format(
            kyc_purpose_of_br=kyc_purpose_of_br_str,
            kyc_transactions=kyc_transactions_str,
        )
    )

    purpose_of_br_result = purpose_of_business_relationship(kyc_purpose_of_br_str, kyc_transactions_str, llm)
    purpose_of_br_result = run_compliance_check(
        purpose_of_business_relationship_prompt, PurposeOfBusinessRelationship
    )

    save_json(
        purpose_of_br_result.json(),
        output_folder,
        folder_name,
        sections_kyc_transactions_purpose_of_br,
    )

    if not purpose_of_br_result.sufficient_explanation:
        kyc_checks_output["purpose_of_business_relationships"]["status"] = False
        statement = (
            "The purpose of BR is in line with the additional information provided by KYC."
            if purpose_of_br_result.sufficient_explanation
            else "The purpose of BR is not in line with the additional information provided by KYC."
        )
        kyc_checks_output["purpose_of_business_relationships"]["reason"] = (
            f"\n\n**{partner_name}**\n{statement}\n"
            f"\n**Reasoning**: {purpose_of_br_result.reasoning}\n"
        )
        logger.info("check 3.1 succeeded")

    # Check 3.2: OU code mapping
    if (
        "**OU code mapping**"
        not in kyc_checks_output["purpose_of_business_relationships"]["reason"]
    ):
        logger.info("check 3.2 started")
        if not ou_code_mapped:
            kyc_checks_output["purpose_of_business_relationships"][
                "reason"
            ] += f"\n**OU code mapping**: is NULL or empty or mapping did not work: {ou_code_mapped}\n"
        else:
            kyc_checks_output["purpose_of_business_relationships"][
                "reason"
            ] += f"\n**OU code mapping found**: {ou_code_mapped}\n"
        logger.info("check 3.2 succeeded")

    # Check 3.3: Transaction summary
    logger.info("check 3.3 started")
    trx_summary = summarise_transactions(kyc_transactions_str, llm)
    transactions_summary_prompt = SUMMARIZE_TRANSACTIONS_PROMPT.format(
        kyc_transactions=kyc_transactions_str
    )

    trx_summary = run_compliance_check(
        transactions_summary_prompt, CheckTransactionSummary
    )


# Section 13: SCAP flag checks
def run_section_scap_flag_checks(
    partner_info,
    partner_name: str,
    kyc_checks_output: dict,
    old_parsed: dict,
) -> None:
    logger.info("========== START SECTION 13: SCAP flag checks ==========")

    if kyc_checks_output["scap_flags"]["raw_data"].update(
        {partner_name: ({}, {}, "N/A (legal entity)")}
    ):
        return

    # Extract client notes and activities to pass to SCAPGraph
    partner_info.get_kbw_dict(partner_info.kyc_dataset)
    partner_info.get_total_income(partner_info.kyc_dataset, partner_info.raw_dict)

    client_notes = partner_info.kyc_dataset.get("total_assets", {}).get(
        "remarks_total_assets", ""
    )

    dict_activities = partner_info.incomes_dict

    # Initialize SCAPGraph
    graph = SCAPGraph()

    # Create the SCAPGraph to compute SCAP flag
    scap_state = graph.invoke(client_notes, dict_activities)

    # Extract SCAP1 and SCAP2 flags
    scap1_flag = scap_state.get("scap_flag", "Missing Information")
    scap2_flag = scap_state.get("scap2_flag", "Missing Information")

    # Extract domicile country (for SCAP1)
    domicile_country = scap_state.get("domicile_country", ["Unknown"])
    if isinstance(domicile_country, list):  # check if it's a list
        domicile_country = ", ".join(
            domicile_country  # convert the list to a comma-separated string
        )

    # Extract the list of SCAP countries (for SCAP2)
    scap1_compliance = map_scap_compliance(scap1_flag)
    scap2_compliance = map_scap_compliance(scap2_flag)

    # map scap1_flag to "Active" or "not active"
    kyc_checks_output["scap_flags"]["reason"] += f"\n**{partner_name}**\n"
    kyc_checks_output["scap_flags"][
        "reason"
    ] += f"SCAP1 Compliance: {scap1_compliance}\n"
    kyc_checks_output["scap_flags"][
        "reason"
    ] += f"Domicile Country: {domicile_country}\n"
    # add multiple blank lines between SCAP1 and SCAP2 sections
    kyc_checks_output["scap_flags"]["reason"] += "\n\n\n"  # add three blank lines

    # map scap2_flag to "Active" or "not active"
    kyc_checks_output["scap_flags"][
        "reason"
    ] += f"SCAP2 Compliance: {scap2_compliance}\n"

    # Extract activity and countries from scap2_details
    keys_to_extract = ["activity", "countries"]
    filtered_data = []

    for i, v in scap_state.items():
        if i == "scap2_details":
            if isinstance(v, dict):
                activities = v.get("activities", [])
            elif isinstance(v, list):
                activities = [
                    item
                    for d in v
                    for item in d.get("activities", [])
                    if isinstance(d, dict)
                ]
            else:
                raise TypeError(
                    f"'scap2_details' is expected to be a dictionary or list, but got {type(v)}"
                )

    filtered_data = [
        {key: inner_dict[key] for key in keys_to_extract if key in inner_dict}
        for inner_dict in filtered_data
        if isinstance(inner_dict, dict)
    ]

    # add filtered activity and countries to SCAP2 section
    if filtered_data:
        for activity_data in filtered_data:
            activity = activity_data.get("activity", "Unknown Activity")
            activity_countries = ", ".join(
                activity_data.get("countries", [])
            )  # join countries into a comma-separated string

        # add "Activity" and "Countries" close together with no extra blank lines
        kyc_checks_output["scap_flags"][
            "reason"
        ] += f"\nActivity: {activity_countries}\n"

    # Check if SCAP flags are reported in EOD and flag discrepancies
    if old_parsed is None:
        kyc_checks_output["scap_flags"]["status"] = False
        kyc_checks_output["scap_flags"]["reason"] += (
            "\n**Check could not be fully run — EDD information is missing.**\n"
        )
    else:
        scap_mapping = {
            "SCAP 1": "SCAP-1",
            "SCAP 2": "SCAP-2",
        }

        for scap_key, eod_key in scap_mapping.items():
            scap_flag = scap1_flag if scap_key == "SCAP 1" else scap2_flag
            if "SCAP" in scap_flag and eod_key not in eod_parsed.get("risk_category", []):
                kyc_checks_output["misc_output"]["status"] = False
                kyc_checks_output["scap_flags"][
                    "reason"
                ] += f"* {scap_key} is not reported in EOD risk category.\n"

    # handle missing information for SCAP flags
    if "Missing Information" in (scap1_flag, scap2_flag):
        kyc_checks_output["scap_flags"]["status"] = False
        kyc_checks_output["scap_flags"][
            "reason"
        ] += "We are missing information about wealth-creating activity to deduce SCAP relevance.\n"

    # if no SCAP flags are detected
    if "SCAP" not in scap1_flag and "SCAP" not in scap2_flag:
        kyc_checks_output["scap_flags"]["reason"] += "No SCAP flags detected.\n"

    logger.info("========== END SECTION 13: SCAP flag checks ==========")
