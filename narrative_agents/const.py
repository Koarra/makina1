from typing import Dict, Any
import os

AZURE_ENDPOINT = os.environ.get(
    "AZURE_ENDPOINT",
    "https://neu.domino.risklab-new.azpriv-cloud.ubs.net/aice-openai",
)

LLM_MODEL = os.environ.get(
    "LLM_MODEL",
    "gpt4",
)

AZURE_DEPLOYMENT = os.environ.get(
    "LLM_MODEL",
    "gpt-4o-mini",
)

API_VERSION = os.environ.get("API_VERSION", "2025-04-01-preview")

PARSE_INPUT_NODE_NAME: str = "parse_input"
REVIEW_TYPE_NODE: str = "review_type"
BACKGROUND_NODE: str = "background_extraction"
CONNECTION_TYPE_NODE: str = "connection_type"
EXPOSURE_DESCRIPTION_NODE: str = "exposure_extraction"
SOW_DESCRIPTION_NODE: str = "sow_extraction"
AUM_DESCRIPTION_NODE: str = "aum_extraction"
LOAN_DEBT_NODE: str = "loan_debt_extraction"
RISKFLAG_DETECTION_NODE: str = "riskflag_detection"
CONDITIONS_DESCRIPTION_NODE: str = "conditions_description"
FRONTEND_COMMENTS_NODE: str = "frontend_comments"
OUTPUT_NODE: str = "output_node"

IN_DEPTH_STATUS: str = "In Depth"
STANDARD_STATUS: str = "Standard"

DIRECT_CONNECTION: str = "Direct"
INDIRECT_CONNECTION: str = "INDIRECT"

LLM_CONFIG: Dict[str, Any] = {
    "model": LLM_MODEL,
    "azure_deployment": AZURE_DEPLOYMENT,
    "api_version": API_VERSION,
    "azure_endpoint": AZURE_ENDPOINT,
    "temperature": 0,
}

SYSTEM_PROMPT: str = ""
INPUT_AR_PROMPT: str = "Using this information:\n{pep_ar}\n"
INPUT_PROFILE_PROMPT: str = "Using this information:\n{pep_profile}\n"
EXTRACT_REVIEW_TYPE_PROMPT: str = "Is this an in-depth or standard check review? Answer only with 'Standard Check' or 'In-Depth'."
EXTRACT_CONNECTION_TYPE_PROMPT: str = "Is the exposure direct or in-direct? Answer only with 'Direct' or 'In-Direct'."
EXTRACT_BACKGROUND_PROMPT: str = "Describe the background of the person in a single line without mentioning the sources of wealth."
EXPOSURE_DESCRIPTION_PROMPT: str = "Describe the exposure in a single line."
SOW_DESCRIPTION_PROMPT: str = "Summarize the SoW / SoF of PEP / CP / BO."
AUM_DESCRIPTION_PROMPT: str = "Summarize the AuM/Turnover/Transactional Commentary in a clear way."
LOANS_DEBTS_PROMPT: str = "Summarize the loans and debts. If no loans and debts are mentioned, just reply with 'No Loans/Debts'."
RISKFLAGS_PROMPT: str = "Extract the riskflags mentioned. If no riskflags are mentioned, just reply with 'No Riskflags'."
CONDITIONS_PROMPT: str = "List the conditions mentioned. If there are no conditions, just reply with 'No Conditions'."
FRONTEND_COMMENTS_PROMPT: str = "Based on the recommendations of the front-end, is the recommendation to maintain or terminate the relationship? If maintain, then reply with 'Maintain'. If any recommendation is to terminate, then reply with 'Terminate'."
