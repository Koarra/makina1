import json
import os
from glob import glob

from constants import (DICT_KYC_CHECKS_NAME_DISPLAY, OU_CODE_DATA_PATH,
                       OUT_OF_SCOPE_CHECKS, OUTPUT_FOLDER)
from edd_agent.edd_assessment_agent_output import EddAssessmentAgentOutput
from edd_agent.edd_text_parser import EddTextParser
from kyc_agent.common import resolve_ou_mapping, serialise_kyc_dataset
from kyc_agent.kyc_agent_output import KycAgentOutput
from kyc_agent.process_kyc_pdf import ProcessKycPdf
from output_writer import OutputWriter
from utils.func_utils import save_json
from utils.fuzzy_match import match_and_save_partners
from utils.logger_config import setup_logger

logger = setup_logger(__name__)


class AgentOrchestrator:
    """Runs the EDD assessment and KYC quality checks for a given EDD case."""

    def __init__(self, edd_case_path: str):
        """
        Args:
            edd_case_path: Path to the EDD case folder to be processed.
        """
        logger.info("=" * 60)
        logger.info("Initializing EDD Analysis")
        logger.info("=" * 60)

        self.case_number = edd_case_path.split("/")[-1]
        logger.info(f"Case number: {self.case_number}")

        self.partner_folders = glob(edd_case_path + "/Partners/*")
        self.pep_documents_present = (
            len(glob(edd_case_path + "/Sensitivity Attachments/PEP/*")) > 0
        )

        if not self.partner_folders:
            logger.warning("No partner folders found")
        else:
            logger.info(f"Found {len(self.partner_folders)} partner folders")

        # --- Parse EDD text (optional) ---
        dd_files = glob(edd_case_path + "/DD-*.txt")
        if dd_files:
            self.edd_case_path = dd_files[0]
            logger.info(f"EDD case path: {self.edd_case_path}")
            with open(self.edd_case_path, "r", encoding="ISO-8859-1") as f:
                self.edd_raw_text = f.read()
                self.edd_case = EddTextParser(self.edd_raw_text).edd_profiles_text
        else:
            logger.warning(f"No DD-*.txt file found in {edd_case_path} — EDD analysis will be skipped")
            self.edd_case_path = None
            self.edd_raw_text = None
            self.edd_case = None

        # --- Process KYC PDFs ---
        self.kyc_cases = [
            ProcessKycPdf(partner_folder) for partner_folder in self.partner_folders
        ]

        logger.info("Starting analysis pipeline")
        self.run_analysis()
        self.write_results()

    def _init_check_fields(self) -> dict:
        """Initialise individual KycState check fields with status, reason and display_name."""
        check_name_to_state_key = {
            "percentage_total_assets_explained": "total_assets",
        }
        check_fields = {}
        for check_name in DICT_KYC_CHECKS_NAME_DISPLAY:
            state_key = check_name_to_state_key.get(check_name, check_name)
            check_fields[state_key] = {"status": True, "reason": ""}
            if check_name in OUT_OF_SCOPE_CHECKS:
                check_fields[state_key]["reason"] = "Out of scope currently."
        check_fields["siap_checks"] = {}
        return check_fields

    def _build_kyc_checks_output(self, final_kyc_state: dict) -> dict:
        """Reconstruct the legacy kyc_checks_output dict from flattened state for OutputWriter."""
        check_name_to_state_key = {
            "percentage_total_assets_explained": "total_assets",
        }
        result = {}
        for check_name in DICT_KYC_CHECKS_NAME_DISPLAY:
            state_key = check_name_to_state_key.get(check_name, check_name)
            result[check_name] = final_kyc_state.get(state_key, {})
        if "siap_flags" in result:
            result["siap_flags"] = {
                **result.get("siap_flags", {}),
                "raw_data": final_kyc_state.get("siap_checks", {}),
            }
        return result

    def _run_edd_analysis(self):
        """Run the EDD assessment agent and store the result in self.edd_result."""
        save_json(
            self.edd_case, OUTPUT_FOLDER, self.case_number, "edd_text_parser.json"
        )
        logger.info("Intermediate data saved for edd_txt_parser")

        role_holders_to_process = []
        self.cp_is_not_bo = False
        if all(
            x["bo_nbr"] != self.edd_case["contractual_partner_information"]["cp_nbr"]
            for x in self.edd_case["role_holders_information"]
        ):
            self.cp_is_not_bo = True
            role_holders_to_process.append(
                self.edd_case["contractual_partner_information"]
            )

        role_holders_to_process.extend(self.edd_case["role_holders_information"])

        logger.info("Starting EddAssessmentOutput")
        initial_edd_state = {
            "file_path": self.edd_case_path,
            "raw_text": self.edd_raw_text,
            "dict_parsed_text": self.edd_case,
            "role_holders_to_process": role_holders_to_process,
        }
        edd_agent = EddAssessmentAgentOutput().agent
        self.edd_result = edd_agent.invoke(initial_edd_state)

        save_json(
            self.edd_result,
            OUTPUT_FOLDER,
            self.case_number,
            "edd_assessment_agent_output.json",
        )
        logger.info("Intermediate data saved for edd result")

    def _run_kyc_analysis(self):
        """Run the KYC checks agent for each partner and store results in self.kyc_results."""
        import copy

        logger.info("Starting KYC checks output processing")

        # Extract partner names — from EDD if available, else from KYC folders
        if self.edd_case:
            edd_partner_names = [
                partner["name"] for partner in self.edd_case["role_holders_information"]
            ]
            if self.cp_is_not_bo:
                edd_partner_names.insert(
                    0, self.edd_case["contractual_partner_information"]["name"]
                )
            ou_code_mapped = resolve_ou_mapping(
                self.edd_case, ou_code_data_path=OU_CODE_DATA_PATH
            )
        else:
            logger.info("No EDD case — deriving partner names from KYC folders")
            edd_partner_names = [case.partner_name for case in self.kyc_cases]
            ou_code_mapped = None

        # OpCo scenario: only process the contractual partner
        if self.edd_case and "Operating Company" in self.edd_case["type_of_business_relationship"]["type"]:
            cp_name = self.edd_case["contractual_partner_information"]["name"]
            edd_partner_names = [name for name in edd_partner_names if name == cp_name]
            logger.info(f"OpCo scenario: limiting KYC to contractual partner only ({cp_name})")

        # Fuzzy match KYC partners to EDD partners
        self.partner_mappings = match_and_save_partners(
            self.kyc_cases,
            edd_partner_names,
            threshold=0.8,
            output_path=os.path.join(
                OUTPUT_FOLDER, self.case_number, "partner_name_mapping.json"
            ),
            verbose=True,
        )

        # Filter out KYC cases with empty datasets
        client_histories_parsed = [
            item for item in self.kyc_cases if item.kyc_dataset is not None
        ]
        logger.info(f"Valid KYC histories: {len(client_histories_parsed)}")

        # Initialise individual check fields (shared/accumulated across all partners)
        current_check_fields = self._init_check_fields()

        # Build the KYC LangGraph agent (once, shared across all partners)
        kyc_agent = KycAgentOutput().agent

        self.kyc_results = {}
        for partner_name_edd in edd_partner_names:
            logger.info(f"Running KYC checks for partner: {partner_name_edd}")

            # Find the matching KYC partner_info
            kyc_folder = next(
                (
                    r["kyc_partner_name"]
                    for r in self.partner_mappings["mappings"]
                    if r["matched_edd_name"] == partner_name_edd
                ),
                None,
            )

            partner_info = next(
                (
                    info
                    for info in client_histories_parsed
                    if info.partner_name == kyc_folder
                ),
                None,
            )

            if not kyc_folder or not partner_info:
                logger.warning(
                    f"Could not resolve partner info for: {partner_name_edd}"
                )
                continue

            folder_name = os.path.join(
                self.case_number,
                os.path.basename(partner_info.kyc_folder_path),
            )

            # Serialise KYC dataset to disk
            serialise_kyc_dataset(partner_info, OUTPUT_FOLDER, folder_name)

            # Build initial KYC state
            initial_kyc_state = {
                "partner_name": partner_info.partner_name,
                "folder_name": folder_name,
                "ou_code_mapped": ou_code_mapped,
                "output_folder": OUTPUT_FOLDER,
                "partner_info": partner_info,
                **current_check_fields,
                "edd_parsed": self.edd_case,  # patch for KYC QC 11.1
                "pep_sensitivity_present": self.pep_documents_present,  # patch for KYC QC 11.1
            }

            # Run the LangGraph KYC pipeline
            final_kyc_state = kyc_agent.invoke(initial_kyc_state)

            # Carry forward accumulated check fields for next partner
            current_check_fields = {
                k: final_kyc_state[k]
                for k in current_check_fields
                if k in final_kyc_state
            }

            # Reconstruct legacy dict format for OutputWriter
            self.kyc_results[partner_name_edd] = copy.deepcopy(
                self._build_kyc_checks_output(final_kyc_state)
            )

            # Attach raw contradiction checks data
            contradiction_path = os.path.join(
                OUTPUT_FOLDER,
                folder_name,
                "section11_2_kyc_data_check_kyc_contradiction.json",
            )

            if os.path.exists(contradiction_path):
                with open(contradiction_path) as f:
                    self.kyc_results[partner_name_edd][
                        "consistency_checks_within_kyc_contradiction_checks"
                    ]["raw_checks"] = json.load(f)

            save_json(
                self.kyc_results[partner_name_edd],
                OUTPUT_FOLDER,
                folder_name,
                "kyc_checks_output.json",
            )
            logger.info(f"KYC checks completed for: {partner_name_edd}")

    def run_analysis(self):
        """Run EDD and/or KYC analysis depending on available inputs."""
        self.cp_is_not_bo = False

        has_edd = bool(self.edd_case)
        has_kyc = bool([item for item in self.kyc_cases if item.kyc_dataset is not None])

        if has_edd and has_kyc:
            scenario = "EDD + KYC"
        elif has_edd:
            scenario = "EDD only"
        elif has_kyc:
            scenario = "KYC only"
        else:
            scenario = "nothing to process"

        logger.info("=" * 60)
        logger.info(f"Run scenario: {scenario}")
        logger.info("=" * 60)

        if has_edd:
            self._run_edd_analysis()
        else:
            logger.info("Skipping EDD analysis — no DD-*.txt file found")
            self.edd_result = {}

        if has_kyc:
            self._run_kyc_analysis()
        else:
            logger.info("Skipping KYC analysis — no partner folders found")
            self.kyc_results = {}
            self.partner_mappings = None

        logger.info("=" * 60)
        logger.info(f"Analysis complete — scenario: {scenario}")
        logger.info("=" * 60)

    def write_results(self):
        """Write the results into a formatted Word report."""
        logger.info("Writing final results")
        self.writer = OutputWriter()
        self.writer.create_output_folder()
        self.writer.write_word_doc(
            self.edd_result,
            self.kyc_results,
            self.case_number,
            self.partner_mappings,
            self.edd_case,
        )
