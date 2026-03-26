from typing import TypeVar

from pydantic import BaseModel
from thefuzz import fuzz

from main.constants import (
    run_compliance_check, section3_kyc_transactions_purpose_of_br,
    section3_kyc_transactions_summary, section4_origin_of_assets_llm,
    section6_kyc_total_assets,
    section7_kyc_data_check_composition_of_total_assets,
    section7_kyc_remarks_composition_total_assets,
    section10kyc_family_situation,
    section11_2_kyc_data_check_kyc_contradiction)
from main.kyc_agent.common import map_scap_compliance, save_json
from main.kyc_agent.kyc_prompts import (
    COMPARE_TRANSACTIONS_PURPOSE_OF_BR_PROMPT,
    CONTRADICTION_CHECKS_PROMPT,
    CROSS_CHECK_PROMPT,
    FAMILY_MEMBERS_PROMPT,
    ORIGIN_OF_ASSET_PROMPT,
    REMARKS_COMP_TOTAL_ASSET_PROMPT,
    SUMMARIZE_TRANSACTIONS_PROMPT,
    TOTAL_ASSET_COMPOSITION_PROMPT,
    TOTAL_ASSET_PROMPT)
from main.kyc_agent.kyc_pydantic_schemas import (CheckTransactionSummary,
                                                  CompareRemarksWithTotalAssets,
                                                  CompletenessOriginOfAssets,
                                                  CompositionOfTotalAssets,
                                                  ContradictionChecks,
                                                  CrossChecks,
                                                  EvaluateTotalAssets,
                                                  FamilyMembersList,
                                                  PurposeOfBusinessRelationship)
from main.kyc_agent.kyc_state import KycState
from main.riskflag_detection.scap_tree import SCAPGraph
from main.riskflag_detection.siap_detection import run_eligible_trees
from main.utils.logger_config import setup_logger

logger = setup_logger(__name__)

prompt_logger = setup_logger(
    logger_name='prompt_logger',
    log_file_name='prompt_logger.log',
    log_mode='w',
    format='%(message)s'
)

T = TypeVar("T", bound=BaseModel)

# -----------------------------------------------------------------------
# Section 3: Purpose of Business Relationship
# -----------------------------------------------------------------------


def run_section_purpose_of_business_relationship(
    partner_info,
    partner_name: str,
    folder_name: str,
    ou_code_mapped: str,
    check: dict,
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

    # purpose_of_br_result = purpose_of_business_relationship(kyc_purpose_of_br_str, kyc_transactions_str, llm)
    purpose_of_br_result = run_compliance_check(
        purpose_of_business_relationship_prompt, PurposeOfBusinessRelationship
    )
    save_json(
        purpose_of_br_result.json(),
        output_folder,
        folder_name,
        section3_kyc_transactions_purpose_of_br,
    )

    prompt_logger.info({
        "folder_name": folder_name,
        "partner_name": partner_name,
        "prompt_name": "PURPOSE_OF_BR",
        "prompt": purpose_of_business_relationship_prompt,
        "prompt_result": purpose_of_br_result.json(),
    })

    if not purpose_of_br_result.sufficient_explanation:
        check["status"] = False
    statement = (
        "The purpose of BR is in line with the additional information provided by KYC."
        if purpose_of_br_result.sufficient_explanation
        else "The purpose of BR is not in line with the additional information provided by KYC."
    )
    check["reason"] += (
        f"\n\n**{partner_name}**\n{statement}\n"
        f"\n\n**Reasoning**: {purpose_of_br_result.reasoning}\n"
    )
    logger.info("check 3.1 succeeded")

    # Check 3.2: OU code mapping (skipped in KYC-only scenario)
    if ou_code_mapped is None:
        logger.info("check 3.2 skipped — no EDD case")
    else:
        if "**OU Code mapping**" not in check["reason"]:
            logger.info("check 3.2 started")
            if not ou_code_mapped:
                check["reason"] += f"\n\n**OU code mapping**: is NULL or empty or mapping did not work: {ou_code_mapped}\n"
            else:
                check["reason"] += f"\n\n**OU code mapping found**: {ou_code_mapped}\n"
            logger.info("check 3.2 succeeded")

    # Check 3.3: Transaction summary
    logger.info("check 3.3 started")
    # trx_summary = _summarise_transactions(kyc_transactions_str, llm)
    transactions_summary_prompt = SUMMARIZE_TRANSACTIONS_PROMPT.format(
        kyc_transactions=kyc_transactions_str
    )
    trx_summary = run_compliance_check(
        transactions_summary_prompt, CheckTransactionSummary
    )
    save_json(
        trx_summary.json(),
        output_folder,
        folder_name,
        section3_kyc_transactions_summary,
    )

    prompt_logger.info({
        "folder_name": folder_name,
        "partner_name": partner_name,
        "prompt_name": "TRANSACTION_SUMMARY",
        "prompt": transactions_summary_prompt,
        "prompt_result": trx_summary.json(),
    })

    trx_lines = [
        str(x).strip() for x in trx_summary.transactions_details if str(x).strip()
    ]
    trx_details = "\n".join(trx_lines) if trx_lines else "No transactions extracted."
    check["reason"] += f"\n\n**KYC transaction summary:**\n{trx_details}\n\n"


# -----------------------------------------------------------------------
# Section 4: Origin of Assets
# -----------------------------------------------------------------------


def run_section_origin_of_assets(
    partner_info,
    partner_name: str,
    folder_name: str,
    check: dict,
    output_folder: str,
    llm,
) -> None:
    logger.info("========== START SECTION 4: ORIGIN OF ASSETS ==========")
    origins = partner_info.kyc_dataset.get("origin_of_assets")
    origin_of_assets_str = str(origins) if origins else "No origins extracted."

    # oa_result = origin_of_assets_completeness(origin_of_assets, llm)
    oa_prompt = ORIGIN_OF_ASSET_PROMPT.format(origin_of_assets=origin_of_assets_str)
    oa_result = run_compliance_check(oa_prompt, CompletenessOriginOfAssets)
    save_json(
        oa_result.json(), output_folder, folder_name, section4_origin_of_assets_llm
    )

    prompt_logger.info({
        "folder_name": folder_name,
        "partner_name": partner_name,
        "prompt_name": "ORIGIN_OF_ASSETS",
        "prompt": oa_prompt,
        "prompt_result": oa_result.json(),
    })

    if oa_result.complete:
        check["reason"] += f"\n\n**{partner_name}**\nOrigin of assets description is complete.\n\n"
    else:
        check["status"] = False
        check["reason"] += f"\n\n**{partner_name}**\nOrigin of assets description is incomplete.\n\n"
        check["reason"] += f"***Reasoning**: {oa_result.reason}\n"


# -----------------------------------------------------------------------
# Section 6: Total assets
# -----------------------------------------------------------------------


def run_section_evaluate_total_assets(
    partner_info,
    partner_name: str,
    folder_name: str,
    check: dict,
    output_folder: str,
    llm,
):
    logger.info("========== START SECTION 6: TOTAL ASSETS ==========")
    kyc_total_assets = None
    percentage_of_specific_asset_fields_explaining_total_assets = None
    percentage_of_total_assets_with_known_origin = None
    if partner_info.kyc_dataset["client_type"] == "Natural Person":
        logger.info("instance is individual")

        total_assets = partner_info.kyc_dataset.get("total_assets", {})
        logger.info(f"total_assets: {total_assets}")
        total_assets_fields = total_assets
        kyc_liquidity = (
            total_assets_fields.get("Total liquid assets", [None])[0].number
            if total_assets_fields.get("Total liquid assets")
            else None
        )
        kyc_real_estate = (
            total_assets_fields.get("Total real estate assets", [None])[0].number
            if total_assets_fields.get("Total real estate assets")
            else None
        )
        kyc_non_liquid = (
            total_assets_fields.get("Total other non-liquid assets", [None])[0].number
            if total_assets_fields.get("Total other non-liquid assets")
            else None
        )

        logger.info(f"kyc_non_liquid: {kyc_non_liquid}")
        kyc_total_assets = (
            total_assets_fields.get("Total estimated assets", [None])[0].number
            if total_assets_fields.get("Total estimated assets")
            else None
        )

        logger.info(f"kyc_total_assets: {kyc_total_assets}")
        kyc_origin_of_assets = (
            str(partner_info.kyc_dataset.get("origin_of_assets"))
            if partner_info.kyc_dataset.get("origin_of_assets")
            else "No kyc origin of assets extracted."
        )
        logger.info(f"kyc_origin_of_assets: {kyc_origin_of_assets}")
        # data = evaluate_total_assets(kyc_origin_of_assets, llm)
        total_assets_prompt = TOTAL_ASSET_PROMPT.format(
            kyc_origin_of_assets=kyc_origin_of_assets
        )

        total_assets_result = run_compliance_check(
            total_assets_prompt, EvaluateTotalAssets
        )
        save_json(
            total_assets_result.json(),
            output_folder,
            folder_name,
            section6_kyc_total_assets,
        )

        prompt_logger.info({
            "folder_name": folder_name,
            "partner_name": partner_name,
            "prompt_name": "TOTAL_ASSETS",
            "prompt": total_assets_prompt,
            "prompt_result": total_assets_result.json(),
        })

        amount_kyc_origin_of_assets = total_assets_result.kyc_origin_of_assets
        logger.info(f"amount_kyc_origin_of_assets: {amount_kyc_origin_of_assets}")
        total_of_specific_asset_fields = (
            (kyc_liquidity or 0) + (kyc_real_estate or 0) + (kyc_non_liquid or 0)
        )

        logger.info(f"total_of_specific_asset_fields: {total_of_specific_asset_fields}")
        logger.info(f"kyc_total_assets: {kyc_total_assets} (type: {type(kyc_total_assets)})")
        logger.info(f"kyc_liquidity: {kyc_liquidity} (type: {type(kyc_liquidity)})")
        logger.info(f"kyc_real_estate: {kyc_real_estate} (type: {type(kyc_real_estate)})")
        logger.info(f"kyc_non_liquid: {kyc_non_liquid} (type: {type(kyc_non_liquid)})")
        logger.info(f"amount_kyc_origin_of_assets: {amount_kyc_origin_of_assets} (type: {type(amount_kyc_origin_of_assets)})")
        if not kyc_total_assets or kyc_total_assets == 0:
            percentage_of_specific_asset_fields_explaining_total_assets = 0
            percentage_of_total_assets_with_known_origin = 0
            check["status"] = False
            check["reason"] += f"\n\n**{partner_name}** \nThe total assets denominator is null or zero, cannot calculate percentages.\n\n"
            logger.info("Cannot calculate percentages - denominator is null/zero.")
        else:
            percentage_of_specific_asset_fields_explaining_total_assets = (
                total_of_specific_asset_fields / kyc_total_assets
            )

            percentage_of_total_assets_with_known_origin = (
                amount_kyc_origin_of_assets / kyc_total_assets
            )

        validation_percentage = 0.8
        if (
            percentage_of_total_assets_with_known_origin >= validation_percentage
            and percentage_of_specific_asset_fields_explaining_total_assets
            >= validation_percentage
        ):
            logger.info(
                f"successfull check: percentage of specific asset fields composing to total assets >= 0.8: {percentage_of_specific_asset_fields_explaining_total_assets}"
            )
            logger.info(
                f"successfull check: percentage of total assets with known origin >= 0.8: {percentage_of_total_assets_with_known_origin}"
            )
            check["reason"] += f"\n\n**{partner_name}**\nBoth of the below percentages is above the 80% threshold.\n\n"
        else:
            logger.info("Low percentage of total asset verification")
            check["status"] = False
            check["reason"] += f"\n\n**{partner_name}**\nAt least one of the below percentages is under the 80% threshold.\n\n"

        check["reason"] += (
            f"The sum of **liquid** ({(kyc_liquidity or 0):.2f}), **real estate** ({(kyc_real_estate or 0):.2f}), "
            f"**non-liquid** ({(kyc_non_liquid or 0):.2f}) asset fields is {total_of_specific_asset_fields:.2f}, "
            f"representing **{percentage_of_specific_asset_fields_explaining_total_assets:.2%}** of the total assets indicated in KYC ({(kyc_total_assets or 0):.2f}).\n\n"
        )
        check["reason"] += (
            f"The Origin of Assets section indicates a total assets amount of {(amount_kyc_origin_of_assets or 0):.2f}, "
            f"representing **{percentage_of_total_assets_with_known_origin:.2%}** of the total assets indicated in KYC "
            f"({(kyc_total_assets or 0):.2f}).\n"
        )
    else:
        logger.info("instance is a legal entity")
        pass
    return (
        kyc_total_assets,
        percentage_of_specific_asset_fields_explaining_total_assets,
        percentage_of_total_assets_with_known_origin,
    )


# ==========================================
# Section 7: Remarks on total asset, and asset composition
# ==========================================


def run_section_remarks_on_total_asset_and_asset_composition(
    partner_info,
    partner_name: str,
    folder_name: str,
    check: dict,
    output_folder: str,
    llm,
    kyc_total_assets,
    percentage_of_specific_asset_fields_explaining_total_assets,
    percentage_of_total_assets_with_known_origin,
) -> None:
    logger.info(
        "========== START SECTION 7: Premarks on total assets and assets composition =========="
    )

    if partner_info.kyc_dataset["client_type"] == "Natural Person":
        logger.info("instance is individual")
        kyc_total_assets_str = (
            str(
                partner_info.kyc_dataset.get("total_assets", {})
                .get("Total estimated assets", [None])[0]
                .number
            )
            if partner_info.kyc_dataset.get("total_assets", {}).get(
                "Total estimated assets"
            )
            else "No kyc total assets text extracted"
        )
        kyc_total_remarks_str = (
            str(
                partner_info.kyc_dataset.get("total_assets", {}).get(
                    "remarks_total_assets"
                )
            )
            if partner_info.kyc_dataset.get("total_assets", {}).get(
                "remarks_total_assets"
            )
            else "No kyc total assets remarks text extracted"
        )

        logger.info(f"kyc_total_assets_str:{kyc_total_assets_str}")
        logger.info(f"kyc_total_remarks_str: {kyc_total_remarks_str}")
        check_composition_of_total_assets_prompt = (
            TOTAL_ASSET_COMPOSITION_PROMPT.format(
                kyc_total_remarks=kyc_total_remarks_str
            )
        )

        data_check_composition_of_ta = run_compliance_check(
            check_composition_of_total_assets_prompt, CompositionOfTotalAssets
        )
        save_json(
            data_check_composition_of_ta.json(),
            output_folder,
            folder_name,
            section7_kyc_data_check_composition_of_total_assets,
        )
        logger.info("intermediate data saved: data check composition of total assets")

        prompt_logger.info({
            "folder_name": folder_name,
            "partner_name": partner_name,
            "prompt_name": "DATA_CHECK_COMPOSITION",
            "prompt": check_composition_of_total_assets_prompt,
            "prompt_result": data_check_composition_of_ta.json(),
        })

        data_kyc_remarks_comp_total_assets_prompt = (
            REMARKS_COMP_TOTAL_ASSET_PROMPT.format(
                kyc_total_remarks=kyc_total_remarks_str,
                kyc_total_assets=kyc_total_assets_str,
            )
        )

        data_kyc_remarks_comp_total_assets = run_compliance_check(
            data_kyc_remarks_comp_total_assets_prompt, CompareRemarksWithTotalAssets
        )
        save_json(
            data_kyc_remarks_comp_total_assets.json(),
            output_folder,
            folder_name,
            section7_kyc_remarks_composition_total_assets,
        )
        logger.info(
            "Intermediate data saved: data kyc remarks composition of total assets"
        )

        prompt_logger.info({
            "folder_name": folder_name,
            "partner_name": partner_name,
            "prompt_name": "DATA_KYC_REMARKS",
            "prompt": data_kyc_remarks_comp_total_assets_prompt,
            "prompt_result": data_kyc_remarks_comp_total_assets.json(),
        })

        remarks_sufficiency_checks = (
            data_kyc_remarks_comp_total_assets.sufficient_explanation
        )
        remarks_sufficiency_checks_reasoning = (
            data_kyc_remarks_comp_total_assets.reasoning
        )
        logger.info(f"remarks_sufficiency_checks: {remarks_sufficiency_checks}")
        logger.info(
            f"remarks_sufficiency_checks: {remarks_sufficiency_checks_reasoning}"
        )
        total_assets_remarks = data_check_composition_of_ta.total_assets_remarks

        # logger.info(f"total_assets_remarks: {total_assets_remarks}")
        # logger.info(f"data_check_composition_of_ta: {data_check_composition_of_ta}")

        if not kyc_total_assets or kyc_total_assets == 0:
            percentage_total_remarks_vs_total_assets = 0
            check["status"] = False
            check["reason"] += f"\n\n**{partner_name}** \nThe total assets denominator is null or zero, cannot calculate percentages.\n\n"
            logger.info("Cannot calculate percentages - denominator is null/zero.")
        else:
            percentage_total_remarks_vs_total_assets = (
                total_assets_remarks / kyc_total_assets
            )
        percentage_validation = 0.8

        check["reason"] += f"\n\n**{partner_name}** **7.1**: The amount mentioned in the remarks on total assets is {(total_assets_remarks or 0):.2f}, representing **{percentage_total_remarks_vs_total_assets:.2%}** of the total assets indicated in the KYC ({(kyc_total_assets or 0):.2f})."
        followup = f"The remarks on total assets {'do not ' if not remarks_sufficiency_checks else ''}fully explain or support the total assets section."
        check["reason"] += f"\n**7.2**: {followup}\n"

        if percentage_total_remarks_vs_total_assets >= percentage_validation:
            logger.info(
                f"successfull check: percentage of specific asset fields composing to total assets >= 0.8: {percentage_of_specific_asset_fields_explaining_total_assets}"
            )
            logger.info(
                f"successfull check: percentage of total assets with known origin >= 0.8: {percentage_of_total_assets_with_known_origin}"
            )
        else:
            logger.info("Low percentage of total asset verification")
            check["status"] = False

        if not remarks_sufficiency_checks:
            check["status"] = False

        check["reason"] += f"***Reasoning**: {remarks_sufficiency_checks_reasoning}\n"
    else:
        logger.info("instance is a legal entity")
        pass


# ==========================================
# Section 8: Activity
# ==========================================


def run_section_activity(
    partner_info,
    partner_name: str,
    check: dict,
) -> None:
    logger.info(
        "========== START SECTION 8:  Activity -> WIP as we need to add LLM check =========="
    )

    if partner_info.kyc_dataset["client_type"] == "Legal Entity":
        activities = partner_info.kyc_dataset.get("corporate_activity")
        logger.info("instance is legal entity, fetching corporate_activity")
    else:
        activities = partner_info.kyc_dataset.get("activities")
        logger.info("instance is individual, fetching activities")
    logger.info(f"activities extracted: {activities}")

    is_valid = activities is not None and len(activities) > 0
    logger.info(f"activities_is_valid: {is_valid}")
    if is_valid:
        logger.info(f"activity field(s) defined for partner: {partner_name}")
        check["reason"] += f"\n\n**{partner_name}**: Activity field(s) defined. \n"
    else:
        logger.info(f"activity field(s) NOT defined for partner: {partner_name}")
        check["status"] = False
        check["reason"] += f"\n\n**{partner_name}**:  Activity field(s) not defined. \n"
    logger.info("SECTION 8 completed")


# ==========================================
# Section 10: Family situation
# ==========================================


def run_section_family_situation(
    partner_info,
    partner_name: str,
    folder_name: str,
    check: dict,
    output_folder: str,
    llm,
):
    logger.info("========== START SECTION 10: family situation ==========")
    if partner_info.kyc_dataset["client_type"] == "Natural Person":
        logger.info("instance is individual")
        family_situation_entries = partner_info.kyc_dataset.get(
            "family_situation_entries", []
        )
        family_situation_remarks = (
            partner_info.kyc_dataset.get("family_situation_remarks") or ""
        )
        logger.info(f"family_situation_entries extracted: {family_situation_entries}")
        logger.info(f"family_situation_remarks extracted: {family_situation_entries}")

        family_situation_collapsed = "\n".join(
            [
                ", ".join([f"{k}: {v}" for k, v in entry.items()])
                for entry in family_situation_entries
            ]
        )
        family_situation_collapsed += family_situation_remarks
        family_situation_collapsed = family_situation_collapsed.strip()
        logger.info(
            f"family_situation_collapsed length: {len(family_situation_collapsed)}"
        )

        extract_family_members_prompt = FAMILY_MEMBERS_PROMPT.format(
            client_notes=str(partner_info.kyc_dataset)
        )

        extracted_family_result = run_compliance_check(
            extract_family_members_prompt, FamilyMembersList
        )
        extracted_family = extracted_family_result.family_members

        logger.info(f"extracted_family members: {extracted_family}")

        prompt_logger.info({
            "folder_name": folder_name,
            "partner_name": partner_name,
            "prompt_name": "EXTRACTED_FAMILY_MEMBERS",
            "prompt": extract_family_members_prompt,
            "prompt_result": extracted_family_result.json(),
        })

        formatted_family = [
            f"- Name: {x.name}, Relation: {x.relation}, SoW Relevant: {x.source_of_wealth_relevant}, Politically Exposed: {x.politically_exposed}"
            for x in extracted_family
        ]
        family_links = "\n" + "\n".join(formatted_family)

        tmp = f"Extracted family members with potential links to SOW/PEP: {family_links if len(family_links.strip()) > 0 else 'none.'}"
        headline = None
        check_ok = True

        if len(family_situation_collapsed) > 0:
            logger.info(
                "family situation section is not empty, proceeding with relevant checks"
            )
            relevant_extracted_family = [
                (x, fuzz.WRatio(x, family_situation_collapsed))
                for x in extracted_family
                if x.source_of_wealth_relevant == "yes"
                or x.politically_exposed == "yes"
            ]
            logger.info(
                f"relevant_extracted_family (SoW/PEP relevant): {relevant_extracted_family}"
            )

            cross_checking_needed = [
                x for x, ratio in relevant_extracted_family if ratio < 80
            ]
            logger.info("cross_checking_needed")
            explicit_mentions = ", ".join(
                [x.name for x, ratio in relevant_extracted_family if ratio >= 80]
            )

            llm_cross_checks = ", ".join([x.name for x in cross_checking_needed])

            tmp += f"\n\nPersons explicitly mentioned in the family situation section: {explicit_mentions if len(explicit_mentions.strip()) > 0 else 'none'}."
            tmp += f"\n\nPersons needing an LLM cross check to confirm explicit mention in the family situation section: {llm_cross_checks if len(llm_cross_checks.strip()) > 0 else 'none'}.\n"
            check_ok = True
            for x in cross_checking_needed:
                cross_check_prompt = CROSS_CHECK_PROMPT.format(
                    family_situation=family_situation_collapsed, name=x.name
                )

                llm_response = run_compliance_check(cross_check_prompt, CrossChecks)

                save_json(
                    llm_response,
                    output_folder,
                    folder_name,
                    section10kyc_family_situation,
                )
                tmp += f"- {x.name}: Mentioned: {llm_response.answer}, Reasoning: {llm_response.reasoning}\n"
                if llm_response.answer != "Yes":
                    check["status"] = False
                    check_ok = False

                    prompt_logger.info({
                        "folder_name": folder_name,
                        "partner_name": partner_name,
                        "prompt_name": "FAMILY_CROSS_CHECK",
                        "prompt": cross_check_prompt,
                        "prompt_result": llm_response.json(),
                    })

            else:
                if len(extracted_family) > 0:
                    check_ok = False
                    check["status"] = False
                    headline = "the family section is empty, which is not permitted as SoW-related or PEP-relevant persons have been identified."
                else:
                    check_ok = True
                    headline = "the family section is empty, which is permitted as no SoW-related or PEP-relevant persons have been identified."

        if headline is not None:
            check["reason"] += f"\n\n**{partner_name}**: {headline}\n"
        elif check_ok:
            check["reason"] += f"\n\n**{partner_name}**: the family section mentions all SoW-relevant and/or politically exposed persons, if any.\n"
        else:
            check["reason"] += f"\n\n**{partner_name}**: the family section needs attention.\n"

        if not (headline and check_ok):
            tmp += "\n"
            check["reason"] += tmp
    else:
        logger.info("instance is legal entity, family situation is not applicable")
        check["reason"] += f"\n\n**{partner_name}**: N/A (legal entity).\n"


# ==========================================
# Section 11.1: PEP/ASM Check
# ==========================================


def run_section_pep_asm_consistency(
    edd_parsed: dict, check: dict, pep_sensitivity_present: bool
):
    if edd_parsed is None:
        logger.info("Section 11.1 skipped because no EDD case")
        check["reason"] = "\n**Check could not be fully run — EDD information is missing.**\n"
        return

    if len(check["reason"].strip()) > 0:
        return

    logger.info(
        "========== START SECTION 11.1: Consistency checks within the KYC: role holders and ASM numbers =========="
    )

    # Role Holders sufficiency check
    quality_check_role_holders = "N/A (no DomCo, OpCo, trust, or foundation)."

    # DomCo
    if "Domiciliary Company" in edd_parsed["type_of_business_relationship"]["type"]:
        if (
            edd_parsed["poa_list"] is not None
            and len(edd_parsed["role_holders_information"]) > 1
        ):
            quality_check_role_holders = "contains at least one BO and one PoA."
        else:
            quality_check_role_holders = (
                " missing information about at least one BO and one PoA."
            )
            check["status"] = False

    # Trust
    if "Trust" in edd_parsed["type_of_business_relationship"]["type"]:
        if edd_parsed["poa_list"] is not None and (
            role in edd_parsed["type_of_business_relationship"]
            for role in ["trustee", "settlor", "Beneficiary"]
        ):
            quality_check_role_holders = (
                "contains at least one trustee, settlor, beneficiary and one PoA."
            )
        else:
            quality_check_role_holders = " missing information about at least one trustee, settlor, beneficiary and one PoA."
            check["status"] = False

    # Foundation
    if "Foundation" in edd_parsed["type_of_business_relationship"]["type"]:
        if edd_parsed["poa_list"] is not None and (
            role in edd_parsed["type_of_business_relationship"]
            for role in ["founder", "beneficiary"]
        ):
            quality_check_role_holders = (
                "contains at least one founder, beneficiary and one PoA."
            )
            check["status"] = False
        else:
            quality_check_role_holders = " missing information about at least one founder, beneficiary and one PoA."
            check["status"] = False

    # OpCo
    if "Operating Company" in edd_parsed["type_of_business_relationship"]["type"]:
        if edd_parsed["poa_list"] is not None and (
            "controlling person" in edd_parsed["type_of_business_relationship"]
        ):
            quality_check_role_holders = (
                "contains at least one controlling person and one PoA."
            )
        else:
            quality_check_role_holders = " missing information about at least one controlling person and one PoA."
            check["status"] = False

    # PEP Quality Check
    quality_check_pep = "N/A (no PEP mention, no sensitivity documents attached)."
    if "PEP" in edd_parsed["risk_category"] or pep_sensitivity_present:
        if "ASM" in edd_parsed["risk_category"]:
            quality_check_pep = "PEP ASM number documented."
        else:
            quality_check_pep = "PEP ASM number not documented."

    check["reason"] += f"\n\n**Role holders sufficiency check**: {quality_check_role_holders}"
    check["reason"] += f"\n\n\n**ASM Number presence check**: {quality_check_pep}"


# ==========================================
# Section 11.2: Consistency Checks within the KYC: contradictory information check 1 vs rest
# ==========================================


def run_section_consistency_checks_within_kyc(
    partner_info,
    partner_name: str,
    folder_name: str,
    check: dict,
    output_folder: str,
    # kyc_dict: dict,
    llm,
):
    logger.info(
        "========== START SECTION 11.2: Consistency checks within the KYC: contradictory information checks  =========="
    )
    results_contradiction = {}
    excluded_keys = {"client_type"}
    kyc_dict = {
        k: v
        for k, v in partner_info.kyc_dataset.items()
        if k not in excluded_keys and v is not None and v != "" and v != []
    }
    logger.info("kyc_dict", kyc_dict)
    logger.info(f"Starting contradiction checks for partner: {partner_name}")
    logger.info(f"Number of fields to check: {len(kyc_dict)}")

    for field_name, field_value in kyc_dict.items():
        logger.info(f"Running contradiction check for field: {field_name}")
        other_fields = {k: v for k, v in kyc_dict.items() if k != field_name}
        # TODO HERE
        contradiction_checks_prompt = CONTRADICTION_CHECKS_PROMPT.format(
            text1=field_value, dic_others=other_fields
        )

        response_llm_contradiction_checks = run_compliance_check(
            contradiction_checks_prompt, ContradictionChecks
        )

        logger.info(
            f"Contradiction check result for {field_name}: {response_llm_contradiction_checks}"
        )

        results_contradiction[f"{field_name}_vs_rest"] = (
            response_llm_contradiction_checks
        )

        prompt_logger.info({
            "folder_name": folder_name,
            "partner_name": partner_name,
            "prompt_name": "CONTRADICTION_CHECKS",
            "prompt": contradiction_checks_prompt,
        })

    is_contradiction = any(
        result.contradictory is True and result.confidence_level > 0.8
        for result in results_contradiction.values()
    )
    logger.info(f"Overall contradiction detected: {is_contradiction}")

    check["status"] &= not is_contradiction
    check["reason"] += f"\n\n**{partner_name}**"
    check["reason"] += "\n**KYC contradiction check**:"

    for field_name, result in results_contradiction.items():
        logger.info(
            f"Field: {field_name} | Contradictory: {result.contradictory} | "
            f"Confidence: {result.confidence_level:.2%} | Reasoning: {result.reasoning}"
        )
        check["reason"] += (
            f"\n\n**{field_name.replace('_', ' ').capitalize()}** - "
            + (
                "contradictions present.**\n"
                if result.contradictory is True
                else "no contradictions identified.**\n"
            )
            + f"**Confidence level**: {result.confidence_level:.2%}\n"
            + f"***Reasoning**: {result.reasoning}\n"
        )
    save_json(
        {k: v.dict() for k, v in results_contradiction.items()},
        output_folder,
        folder_name,
        section11_2_kyc_data_check_kyc_contradiction,
    )
    raw_data = {"consistency_checks_within_kyc_contradiction_checks": {}}
    raw_data["consistency_checks_within_kyc_contradiction_checks"][partner_name] = [
        {"check": field_name, "contradictions_present": result.contradictory}
        for field_name, result in results_contradiction.items()
    ]
    logger.info("Intermediate data saved: kyc contradiction checks")


def run_siap_check(partner_info, partner_name: str, siap_checks: dict):
    logger.info("START SECTION 14: SIAP flag checks")

    if partner_info.kyc_dataset["client_type"] != "Natural Person":
        # kyc_checks_output["siap_flags"]["raw_data"].update({partner_name: [{}, [], "N/A (legal entity)"]})
        return

    siap_results = run_eligible_trees(
        partner_info.kyc_dataset
    )  # last node contains the ordered sources of wealth

    siap_checks.update({partner_name: siap_results})


# ==========================================
# Section 13: SCAP flag checks
# ==========================================


def run_section_scap_flag_checks(
    partner_info,
    partner_name: str,
    check: dict,
    edd_parsed: dict,
) -> None:
    logger.info("========== START SECTION 13: SCAP flag checks ==========")

    if partner_info.kyc_dataset["client_type"] != "Natural Person":
        # kyc_checks_output["scap_flags"]["raw_data"].update({partner_name: [{}, [], "N/A (legal entity)"]})
        return

    # Extract client notes and activities to pass to SCAPGraph
    partner_info.get_sow_dict(partner_info.kyc_dataset)
    partner_info.get_total_income(partner_info.kyc_dataset, partner_info.raw_dict)

    client_notes = partner_info.kyc_dataset.get("total_assets", {}).get(
        "remarks_total_assets", ""
    )

    dict_activities = partner_info.incomes_dict

    # Initialize SCAPGraph
    graph = SCAPGraph()

    # Invoke the SCAPGraph to compute SCAP flags
    scap_state = graph.invoke(client_notes, dict_activities)

    # Extract SCAP1 and SCAP2 flags
    scap1_flag = scap_state.get("scap1_flag", "Missing Information")
    scap2_flag = scap_state.get("scap2_flag", "Missing Information")

    # Extract domicile country (for SCAP1)
    domicile_country = scap_state.get(
        "domicile_country", ["Unknown"]
    )  # Defaults to a list with "Unknown"
    if isinstance(domicile_country, list):  # Check if it's a list
        domicile_country = ", ".join(
            domicile_country
        )  # Convert the list to a comma-separated string

    # Extract the list of SCAP countries (for SCAP2)
    scap1_compliance = map_scap_compliance(scap1_flag)
    scap2_compliance = map_scap_compliance(scap2_flag)

    # Map scap1_flag to "Active" or "Not Active"
    # Update kyc_checks_output with SCAP1 results
    check["reason"] += f"\n\n**{partner_name}**\n"
    check["reason"] += f"SCAP1 Compliance: {scap1_compliance}\n"
    check["reason"] += f"Domicile Country: {domicile_country}\n"
    # Add multiple blank lines between SCAP1 and SCAP2 sections
    check["reason"] += "\n\n\n"  # Add three blank lines

    # Map scap1_flag to "Active" or "Not Active"
    # Update check with SCAP2 results
    check["reason"] += f"SCAP2 Compliance: {scap2_compliance}\n"

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
                for inner_dict in activities
                if isinstance(inner_dict, dict)
            ]

    # Add filtered activity and countries to SCAP2 section
    if filtered_data:
        for activity_data in filtered_data:
            activity = activity_data.get("activity", "Unknown Activity")
            activity_countries = ", ".join(
                activity_data.get("countries", [])
            )  # Join countries into a comma-separated string

            # Add "Activity" and "Countries" close together with no extra blank lines
            check["reason"] += f"Activity: {activity}\nCountries: {activity_countries}\n"
    check["reason"] += "\n\n"  # Add three blank lines

    # Check if SCAP flags are reported in EDD and flag discrepancies
    if edd_parsed:
        scap_mapping = {
            "SCAP 1": "SCAP-1",
            "SCAP 2": "SCAP-2",
        }

        for scap_key, edd_key in scap_mapping.items():
            scap_flag = scap1_flag if scap_key == "SCAP 1" else scap2_flag
            if "SCAP" in scap_flag and edd_key not in edd_parsed.get("risk_category", []):
                check["status"] = False
                check["reason"] += f"* {scap_key} is not reported in EDD risk category.\n"

    # Handle missing information for SCAP flags
    if "Missing Information" in (scap1_flag, scap2_flag):
        check["status"] = False
        check["reason"] += "We are missing information about wealth-creating activity to deduce SCAP relevance.\n"

    # If no SCAP flags are detected
    if "SCAP" not in scap1_flag and "SCAP" not in scap2_flag:
        check["reason"] += "No SCAP flags detected.\n"

    logger.info("========== END SECTION 13: SCAP flag checks ==========")


# -----------------------------------------------------------------------
# Nodes section
# -----------------------------------------------------------------------


def node_section3_purpose_of_br(state: KycState, llm) -> KycState:
    run_section_purpose_of_business_relationship(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        folder_name=state["folder_name"],
        ou_code_mapped=state["ou_code_mapped"],
        check=state["purpose_of_business_relationships"],
        output_folder=state["output_folder"],
        llm=llm,
    )
    return {**state, "purpose_of_business_relationships": state["purpose_of_business_relationships"]}


def node_section4_origin_of_assets(state: KycState, llm) -> KycState:
    run_section_origin_of_assets(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        folder_name=state["folder_name"],
        check=state["origin_of_asset"],
        output_folder=state["output_folder"],
        llm=llm,
    )
    return {**state, "origin_of_asset": state["origin_of_asset"]}


def node_section6_total_assets(state: KycState, llm) -> KycState:
    (
        kyc_total_assets,
        percentage_of_specific_asset_fields_explaining_total_assets,
        percentage_of_total_assets_with_known_origin,
    ) = run_section_evaluate_total_assets(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        folder_name=state["folder_name"],
        check=state["total_assets"],
        output_folder=state["output_folder"],
        llm=llm,
    )
    return {
        **state,
        "total_assets": state["total_assets"],
        "kyc_total_assets": kyc_total_assets,
        "percentage_of_specific_asset_fields_explaining_total_assets": percentage_of_specific_asset_fields_explaining_total_assets,
        "percentage_of_total_assets_with_known_origin": percentage_of_total_assets_with_known_origin,
    }


def node_section7_remarks_total_assets(state: KycState, llm) -> KycState:
    run_section_remarks_on_total_asset_and_asset_composition(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        folder_name=state["folder_name"],
        check=state["remarks_on_total_assets_and_composition"],
        output_folder=state["output_folder"],
        kyc_total_assets=state.get("kyc_total_assets"),
        percentage_of_specific_asset_fields_explaining_total_assets=state.get(
            "percentage_of_specific_asset_fields_explaining_total_assets"
        ),
        percentage_of_total_assets_with_known_origin=state.get(
            "percentage_of_total_assets_with_known_origin"
        ),
        llm=llm,
    )
    return {**state, "remarks_on_total_assets_and_composition": state["remarks_on_total_assets_and_composition"]}


def node_section8_activity(state: KycState, llm) -> KycState:
    run_section_activity(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        check=state["activity"],
    )
    return {**state, "activity": state["activity"]}


def node_section10_family_situation(state: KycState, llm) -> KycState:
    run_section_family_situation(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        folder_name=state["folder_name"],
        check=state["family_situation"],
        output_folder=state["output_folder"],
        llm=llm,
    )
    return {**state, "family_situation": state["family_situation"]}


def node_section11_1_consistency_checks_pep_asm(state: KycState) -> KycState:
    run_section_pep_asm_consistency(
        edd_parsed=state["edd_parsed"],
        check=state["consistency_checks_pep_asm"],
        pep_sensitivity_present=state["pep_sensitivity_present"],
    )
    return {**state, "consistency_checks_pep_asm": state["consistency_checks_pep_asm"]}


def node_section11_2_consistency_checks_within_kyc(state: KycState, llm) -> KycState:
    run_section_consistency_checks_within_kyc(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        folder_name=state["folder_name"],
        check=state["consistency_checks_within_kyc_contradiction_checks"],
        output_folder=state["output_folder"],
        llm=llm,
    )
    return {**state, "consistency_checks_within_kyc_contradiction_checks": state["consistency_checks_within_kyc_contradiction_checks"]}


def node_section13_scap_flag_checks(state: KycState) -> KycState:
    run_section_scap_flag_checks(
        partner_info=state["partner_info"],
        partner_name=state["partner_name"],
        check=state["scap_flags"],
        edd_parsed=state["edd_parsed"],
    )
    return {**state, "scap_flags": state["scap_flags"]}


def node_section14_siap_checks(state: KycState) -> KycState:
    run_siap_check(
        state["partner_info"], state["partner_name"], state["siap_checks"]
    )
    return {**state, "siap_checks": state["siap_checks"]}


# --- Template for adding new sections ---
# --- Template for adding new sections ---

# def node_section6_total_assets(state: KycState, llm) -> KycState:
#     """LangGraph node: Section 6 – Total Assets."""
#     run_section_evaluate_total_assets(
#         partner_info=state["partner_info"],
#         partner_name=state["partner_name"],
#         folder_name=state["folder_name"],
#         kyc_checks_output=state["kyc_checks_output"],
#         output_folder=state["output_folder"],
#         llm=llm,
#     )
#     return {
#         **state,
#         "total_assets": state["kyc_checks_output"]["total_assets"],
#     }
