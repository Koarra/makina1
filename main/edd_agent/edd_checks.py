import json
import re

from main.constants import (TYPE_A_B_ACCEPT, TYPE_A_B_REJECT, TYPE_C_ACCEPT,
                             TYPE_C_REJECT)
from main.edd_agent.edd_prompts import (
    ACTIVITIES_PROMPT, ANTICIPATED_TRX_PROMPT, BANKABLE_ASSETS_PROMPT,
    EDD_ASSESSMENT_PURPOSE_OF_BUSINESS_PROMPT, FINAL_SUMMARY_PROMPT,
    OTHER_ASSETS_PROMPT, PRIVATE_EQUITY_PROMPT, REAL_ESTATE_PROMPT,
    SOW_SUMMARY_PROMPT)
from main.edd_agent.edd_pydantic_schemas import (Activities, BankableAssets,
                                                  OtherAssets, PrivateEquity,
                                                  RealEstate, SowSummary,
                                                  SummarizePurposeOfBr,
                                                  SummarizeReport, TrxPattern)
from main.edd_agent.edd_state import EddState
from main.utils.func_utils import (dict_with_spaces, flatten_dict_results,
                                    prettify_name)


# 1. Type of business relationship
def type_of_business_relationship(state: EddState) -> EddState:
    edd_profiles_text = state.get("dict_parsed_text")
    name = edd_profiles_text["contractual_partner_information"]["name"]
    name = prettify_name(name)
    type_of_business_relationship = (
        "Type of Business Relationship: "
        + edd_profiles_text["type_of_business_relationship"]["type"]
        + " Account for "
        + name
        + "\n"
    )

    # Initialize a list to hold role holder information
    role_holder_lines = []
    role_holder_lines.append("List of role holders:")

    # Iterate through each role holder in the list
    for i in range(len(edd_profiles_text["role_holders_information"])):
        role_holder_name = edd_profiles_text["role_holders_information"][i]["name"]
        role_holder_role = edd_profiles_text["role_holders_information"][i]["role"]
        # Create a formatted string for each role holder
        role_holder_lines.append(f"{role_holder_name} - {role_holder_role}")

    # Join the role holder lines into a single string with line breaks
    role_holder_info = "\n".join(role_holder_lines)

    # Add the role holder information to the output
    type_of_business_relationship += "\n" + role_holder_info

    # Add the PoAs
    if edd_profiles_text["poa_list"] != None:
        poa_holders = ", ".join(edd_profiles_text["poa_list"])
        if poa_holders.strip() != "N/A":
            type_of_business_relationship += "\n" + "PoA holders: \n" + poa_holders

    # Add information for LE about corporate structure, complexity, motivation
    if edd_profiles_text["type_of_business_relationship"][
        "type_of_business_relationship"
    ] not in ["Individual", "Joint"]:
        type_of_business_relationship += (
            "\n"
            + "\n"
            + edd_profiles_text["type_of_business_relationship"][
                "structure_motivation_complexity"
            ]
        )
        if (
            edd_profiles_text["type_of_business_relationship"]["motivation_dom_co"]
            is None
        ):
            type_of_business_relationship += (
                "\n" + "Motivation for Domco Information missing"
            )
        if (
            edd_profiles_text["type_of_business_relationship"]["corporate_structure"]
            is None
        ):
            type_of_business_relationship += (
                "\n" + "Corporate structure Information missing"
            )
        if (
            edd_profiles_text["type_of_business_relationship"]["corporate_structure"]
            is None
        ):
            type_of_business_relationship += (
                "\n" + "Complex Client Structure Information missing"
            )

    return {"type_of_business_relationship": type_of_business_relationship}


# 2. Request type
def request_type(state: EddState) -> EddState:
    edd_profiles_text = state.get("dict_parsed_text")
    request_type = "Request Type " + edd_profiles_text["request_type"]
    return {"request_type": request_type}


# 3. Risk category
def risk_category(state: EddState) -> EddState:
    edd_profiles_text = state.get("dict_parsed_text")
    risk_category = edd_profiles_text["risk_category"]
    return {"risk_category": risk_category}


# 4. Purpose of business relationship
def purpose_of_business_relationship(state: EddState, run_compliance_check) -> EddState:
    edd_profiles_text = state.get("dict_parsed_text")
    purpose_of_business = edd_profiles_text["purpose_of_business_relationship"]
    parsed = purpose_of_business.split("\n")
    bulletized_purpose_of_br = []
    for line in parsed:
        tmp = line.split("- Details:")
        title = tmp[0].strip()
        detail = tmp[1].strip()
        summary = ""
        if detail != "N/A":
            prompt = EDD_ASSESSMENT_PURPOSE_OF_BUSINESS_PROMPT.format(
                purpose_of_business_txt=detail
            )
            result = run_compliance_check(prompt, SummarizePurposeOfBr)
            summary = (
                "**Summary**: "
                + result.summary.replace(
                    "Purpose of business relationship:", ""
                ).strip()
            )
        bulletized_purpose_of_br.append(f"**{title}**\n{summary}\n\n")
    return {"purpose_of_business_relationship": "\n".join(bulletized_purpose_of_br)}


# 5. Expected NNM/ Current AuM
def expected_nnm_or_current_aum(state: EddState) -> EddState:
    edd_profiles_text = state.get("dict_parsed_text")
    return {
        "expected_nnm_or_current_aum": edd_profiles_text["expected_nnm_or_current_aum"]
    }


# 6. Transactions (partly out of scope)
def expected_transactions(state: EddState, run_compliance_check) -> EddState:
    """
    Type A/B: Summarize the anticipated transaction pattern from the purpose of BR.
    Type C: Transactions from the EDD text file.
    """
    tmp = state["dict_parsed_text"]["transactions"]
    if state["request_type"] != "C":
        tmp = run_compliance_check(
            ANTICIPATED_TRX_PROMPT.format(
                client_history=str(
                    state["dict_parsed_text"]["purpose_of_business_relationship"]
                )
            ),
            TrxPattern,
        ).anticipated_pattern
    return {"expected_transactions": tmp}


# 7. Activity
def activity(state: EddState, run_compliance_check) -> EddState:
    activities_results = ""
    init_raw_data = {}
    additional_data = {}
    for role_holder in state["role_holders_to_process"]:
        if (
            "activity" not in role_holder
        ) or (
            "Operating Company" in state["dict_parsed_text"]["type_of_business_relationship"]["type"]
            and role_holder["name"] != state["dict_parsed_text"]["contractual_partner_information"]["name"]
        ):
            continue
        entity = role_holder["name"]
        response = run_compliance_check(
            ACTIVITIES_PROMPT.format(
                entity=entity, text_to_provide=role_holder["activity"]
            ),
            Activities,
        )
        cleaned_content = (
            str(response["activities"]).replace("'", "**").replace("_", " ")
        )
        activities_results += f"**{entity.title()}**\n\n"
        activities_results += flatten_dict_results(response["activities"])
        # Now parse the JSON
        try:
            data = json.loads(cleaned_content)
        except json.JSONDecodeError as e:
            data = {}
        additional_data[entity.title()] = data
    init_raw_data["activity"] = additional_data
    return {"activity": activities_results, "raw_data": init_raw_data}


# 8. Total Wealth and Composition of Wealth --> with llm total_wealth_composition
def total_wealth_composition(state: EddState, run_compliance_check) -> EddState:
    total_wealth_results = ""
    additional_data = {}
    for role_holder in state["role_holders_to_process"]:
        if (
            "total_wealth_composition" not in role_holder
        ) or (
            "Operating Company" in state["dict_parsed_text"]["type_of_business_relationship"]["type"]
            and role_holder["name"] != state["dict_parsed_text"]["contractual_partner_information"]["name"]
        ):
            continue

        total_wealth_results += f'**{prettify_name(role_holder["name"])}**\n\n'

        start_idx = role_holder["total_wealth_composition"].find("Total assets:")
        end_idx = role_holder["total_wealth_composition"].find("\n", start_idx)

        total_wealth_results += (
            role_holder["total_wealth_composition"][start_idx:end_idx] + "\n\n"
        )

        total_wealth_results += "Bankable assets:\n\n"
        # llm_bankable_assets = llm.with_structured_output(bankable_assets)
        result_bankable_assets = run_compliance_check(
            BANKABLE_ASSETS_PROMPT.format(
                remarks_on_total_assets=role_holder["total_wealth_composition"]
            ),
            BankableAssets,
        )
        total_wealth_results += flatten_dict_results(
            result_bankable_assets.get("assets", [])
        )

        total_wealth_results += "Real estate assets:\n\n"
        # llm_real_estate = llm.with_structured_output(real_estate)
        result_real_estate = run_compliance_check(
            REAL_ESTATE_PROMPT.format(
                remarks_on_total_assets=role_holder["total_wealth_composition"]
            ),
            RealEstate,
        )
        total_wealth_results += flatten_dict_results(
            result_real_estate.get("assets", [])
        )

        total_wealth_results += "Private equity assets:\n\n"
        # llm_private_equity = llm.with_structured_output(private_equity)
        result_private_equity = run_compliance_check(
            PRIVATE_EQUITY_PROMPT.format(
                remarks_on_total_assets=role_holder["total_wealth_composition"]
            ),
            PrivateEquity,
        )
        total_wealth_results += flatten_dict_results(
            result_private_equity.get("assets", [])
        )

        total_wealth_results += "Other assets:\n\n"
        # llm_other_assets = llm.with_structured_output(other_assets)
        result_other_assets = run_compliance_check(
            OTHER_ASSETS_PROMPT.format(
                remarks_on_total_assets=role_holder["total_wealth_composition"]
            ),
            OtherAssets,
        )
        total_wealth_results += flatten_dict_results(
            result_other_assets.get("assets", [])
        )

        additional_data[prettify_name(role_holder["name"])] = {
            "bankable_assets": result_bankable_assets,
            "real_estate": result_real_estate,
            "private_equity": result_private_equity,
            "other_assets": result_other_assets,
        }
    raw_data = state.get("raw_data")
    raw_data["total_wealth_composition"] = additional_data
    return {"total_wealth_composition": total_wealth_results, "raw_data": raw_data}


# 9. Source of Wealth --> with llm
def source_of_wealth(state: EddState, run_compliance_check) -> EddState:
    sow_results = ""
    for role_holder in state["role_holders_to_process"]:
        if (
            "Operating Company" in state["dict_parsed_text"]["type_of_business_relationship"]["type"]
            and role_holder["name"] != state["dict_parsed_text"]["contractual_partner_information"]["name"]
        ):
            continue
        sow_results += f'**{prettify_name(role_holder["name"])}**\n\n'
        result = run_compliance_check(
            SOW_SUMMARY_PROMPT.format(client_history=role_holder["source_of_wealth"]),
            SowSummary,
        )
        dict_result = dict_with_spaces(result)
        sow_results += "\n\n".join(
            [dict_result["sow description"], dict_result["sow plausibility"]]
        )
        sow_results += "\n\n"
    return {"source_of_wealth": sow_results}


# 10. Corroboration
def corroboration(state: EddState) -> EddState:
    corroboration = "\n\n\n".join(
        f'**{x["name"]}**\n\n{x["corroboration"]}' if len(x["corroboration"].strip()) > 0 else "Corroboration details not available"
        for x in state["role_holders_to_process"]
    )
    bold_corroboration = corroboration.replace(
        "Corroboration or Evidence:", "**Corroboration or Evidence**:"
    ).replace("Details:", "**Details**:")

    return {"corroboration": bold_corroboration}


# 11. Negative news (out of scope)
def negative_news(state: EddState) -> EddState:
    return {"negative_news": "\nCurrently out of scope.\n"}


# 12. Other risk aspects (out of scope)
def other_risk_aspects(state: EddState) -> EddState:
    return {"other_risk_aspects": "\nCurrently out of scope.\n"}


# 13. Other relevant information (out of scope)
def other_relevant_information(state: EddState) -> EddState:
    return {"other_relevant_information": "\nCurrently out of scope.\n"}


# 14. Final conclusion
def final_summary(state: EddState, run_compliance_check) -> EddState:
    result_attributes = {
        "type_of_business_relationship",
        "request_type",
        "risk_category",
        "purpose_of_business_relationship",
        "expected_nnm_or_current_aum",
        "expected_transactions",
        "activity",
        "total_wealth_composition",
        "source_of_wealth",
        "corroboration",
        "negative_news",
        "other_risk_aspects",
        "other_relevant_information",
    }
    dataset_to_summarize = {k: state[k] for k in result_attributes if k in state}
    # llm_final_summary = llm.with_structured_output(summarize_report)
    result = run_compliance_check(
        FINAL_SUMMARY_PROMPT.format(client_history=str(dataset_to_summarize)),
        SummarizeReport,
    )
    dict_result = dict_with_spaces(dict(result))
    if dict_result["request type"] in ["A", "B"]:
        if dict_result["decision"] == "accept":
            final_summary = TYPE_A_B_ACCEPT
        if dict_result["decision"] == "reject":
            final_summary = TYPE_A_B_REJECT.format(
                justification=dict_result["justification"]
            )
    if dict_result["request type"] == "C":
        if dict_result["decision"] == "accept":
            final_summary = TYPE_C_ACCEPT
        if dict_result["decision"] == "reject":
            final_summary = TYPE_C_REJECT.format(
                justification=dict_result["justification"]
            )

    return {"final_summary": final_summary}
