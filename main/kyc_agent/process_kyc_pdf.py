import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(__file__)))

import traceback
from copy import deepcopy
from glob import glob
from typing import List

from main.constants import OUTPUT_FOLDER
from main.kyc_agent.kyc_pdf_parser import LegalEntityPDFLoader, ProcessInputPDF
from main.processing.sow2json import Sow2Dict
from main.processing.total_assets import TotalAssetsExtractor
from main.processing.total_income import TotalIncomeExtractor
from main.utils.func_utils import save_json
from main.utils.logger_config import setup_logger

logger = setup_logger(__name__)


class ProcessKycPdf:
    partner_name: str
    partner_path: str
    kyc_dataset: dict
    sow_corroboration_documents: List[str]

    def __init__(self, kyc_folder_path: str):
        """Build a KYC Case."""
        self.partner_name = kyc_folder_path.split("/")[-1]
        self.case_name = kyc_folder_path.split("/")[-3]
        self.kyc_folder_path = kyc_folder_path
        client_history_paths = glob(kyc_folder_path + "/Client history/*.pdf")
        # Get the latest modified client history file, if any
        latest_client_history = (
            max(client_history_paths, key=os.path.getmtime)
            if client_history_paths
            else None
        )

        if latest_client_history:
            self.kyc_dataset = self.parse_client_history(latest_client_history)
            logger.info(f"Parsed KYC dataset:{self.kyc_dataset}")
            self.partner_path = latest_client_history
            # Get paths of corroboration documents
            self.sow_corroboration_documents = glob(
                kyc_folder_path + "/Corroboration evidence/*.pdf"
            )
        else:
            self.kyc_dataset = None
            self.partner_path = None
            self.sow_corroboration_documents = []

    def parse_client_history(self, client_history_filename: str):
        logger.info("parse client history started")
        for pdf_cls in [ProcessInputPDF, LegalEntityPDFLoader]:
            try:
                tmp_parsed = pdf_cls().parse(client_history_filename)
            except Exception as e:
                logger.info(
                    f"Encountered exception when parsing {client_history_filename} as {pdf_cls}:"
                )
                logger.info(traceback.format_exc())
                tmp_parsed = None
            if tmp_parsed:
                if pdf_cls is ProcessInputPDF:
                    tmp_parsed["client_type"] = "Natural Person"
                else:
                    tmp_parsed["client_type"] = "Legal Entity"
                save_json(
                    tmp_parsed,
                    (OUTPUT_FOLDER + "/" + self.case_name),
                    self.partner_name,
                    "kyc_history_parsed.json",
                )
                return tmp_parsed
        return None

    def get_sow_dict(self, kyc_dataset: dict):
        self.parsed_dict, self.raw_dict = Sow2Dict()(kyc_dataset)
        return self.parsed_dict, self.raw_dict

    def get_total_assets(self, kyc_dataset, raw_dict):
        self.ta_dict = TotalAssetsExtractor()(kyc_dataset, raw_dict)
        return self.ta_dict

    def get_total_income(self, kyc_dataset, raw_dict):
        (
            self.total_computed_income,
            self.full_text_res_employment,
            self.investments_classified,
            self.explicit_income,
        ) = TotalIncomeExtractor()(kyc_dataset, raw_dict)

        overlap_keys = set(self.raw_dict) & set(self.investments_classified)
        self.incomes_dict = deepcopy(self.raw_dict)

        for key in overlap_keys:
            inv = self.investments_classified.get(key, {})
            ret = inv.get("Return", None)
            if ret is not None:
                # Cast Amount to string directly
                self.incomes_dict[key]["Net Income"] = str(ret)
        return TotalIncomeExtractor()(kyc_dataset, raw_dict)
