"""Module for parsing EDD text files."""
import json
import os
import traceback

from utils.logger_config import setup_logger

logger = setup_logger(__name__)

from typing import List

from main.constants import INVALID_CASE_KEYWORDS
from main.edd_agent.edd_text import EDDText
from main.utils.func_utils import extract_chunk


class EddTextParser:
    """Class for parsing EDD text files."""

    def __init__(self, text: str):
        """Construct the EddTextParser class and store the parsed results in edd_profiles_text.

        Args:
            text: str
                The text contents of the EDD file to be parsed.
        """

        self.edd_profiles_text: EDDText = {}
        self.text = text
        self.edd_info_parsing()

    def edd_info_parsing(self):
        """Parse the contents of the EDD text file."""

        self.edd_profiles_text["valid_file"] = True

        if not file_validity_checker(self.text):
            self.edd_profiles_text["valid_file"] = False
            return

        self.parse_role_holders()
        self.parse_type_of_br()
        self.parse_request_type()
        self.parse_risk_category()
        self.parse_purpose_of_br()
        self.parse_expected_nnm_or_current_aum()
        self.parse_transactions()
        self.parse_activities()
        self.parse_total_wealth_and_composition_of_wealth()
        self.parse_sow()
        self.parse_corroboration()

    def parse_role_holders(self):
        """Parse the role holders information from the EDD text file."""

        self.edd_profiles_text["contractual_partner_information"] = {}

        start_sentence = "Contractual Partner Information"
        stop_sentence = "7."

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        information_chunk = result[0]
        name, end = extract_chunk(information_chunk, "Name: ", "- Domicile:")
        domicile, _ = extract_chunk(information_chunk[end:], "- Domicile:", "\n")
        info_id, _ = extract_chunk(information_chunk, "BR - CP: ", "- Name")

        self.edd_profiles_text["contractual_partner_information"][
            "cp_nbr"
        ] = info_id.strip()
        self.edd_profiles_text["contractual_partner_information"]["name"] = name.strip()
        self.edd_profiles_text["contractual_partner_information"][
            "domicile"
        ] = domicile.strip()

        # Role holders
        self.edd_profiles_text["role_holders_information"] = []

        # Beneficial Owners
        start_sentence = "Beneficial Owner Information"
        stop_sentence = "7."

        bos = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        for role_holder in bos:
            role_holder_info = {}
            lines = role_holder.split("\n\n")
            role_holder_info["name"] = (
                lines[0]
                .replace(", Attention: This BO is not present in CAMB for this CP!", "")
                .split("-")[3]
                .split(":")[1]
                .strip()
            )
            role_holder_info["role"] = lines[1].split(":")[1].strip()
            role_holder_info["bo_nbr"] = extract_chunk(lines[0], "BR - BO: ", "- Name")[
                0
            ].strip()
            self.edd_profiles_text["role_holders_information"].append(role_holder_info)

        # PoAs
        start_sentence = "7. Power of Attorney Information"
        stop_sentence = "8. Related Parties Information"

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        if len(result) > 0:
            self.edd_profiles_text["poa_list"] = result[0].split("\n")
        else:
            self.edd_profiles_text["poa_list"] = None

    def parse_type_of_br(self):
        """Parse the type of business relationship portion of the EDD text file."""

        self.edd_profiles_text["type_of_business_relationship"] = {}

        start_sentence = "1. Type of business relationship:"
        stop_sentence = "2. Request type:"

        info = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )[0].split("\n\n")

        info_type_business = info[0].split("-")
        info_le = info[1:]
        self.edd_profiles_text["type_of_business_relationship"][
            "type_of_business_relationship"
        ] = info_type_business[0].strip()
        self.edd_profiles_text["type_of_business_relationship"]["type"] = (
            info_type_business[1].split(":")[1].strip()
        )

        # Legal Entity part
        self.edd_profiles_text["type_of_business_relationship"][
            "motivation_dom_co"
        ] = True
        self.edd_profiles_text["type_of_business_relationship"][
            "corporate_structure"
        ] = True
        self.edd_profiles_text["type_of_business_relationship"][
            "complex_structure"
        ] = True

        if self.edd_profiles_text["type_of_business_relationship"][
            "type_of_business_relationship"
        ] not in ["Individual", "Joint"]:
            info_le = "\n".join(info_le)
            self.edd_profiles_text["type_of_business_relationship"][
                "structure_motivation_complexity"
            ] = info_le
            if (
                "Motivation for holding a domiciliary company"
                not in self.edd_profiles_text["type_of_business_relationship"][
                    "structure_motivation_complexity"
                ]
            ):
                self.edd_profiles_text["type_of_business_relationship"][
                    "motivation_dom_co"
                ] = None
            if (
                "Remarks about ownership and group structure"
                not in self.edd_profiles_text["type_of_business_relationship"][
                    "structure_motivation_complexity"
                ]
            ):
                self.edd_profiles_text["type_of_business_relationship"][
                    "corporate_structure"
                ] = None
            if (
                "Complex Client Structure"
                not in self.edd_profiles_text["type_of_business_relationship"][
                    "structure_motivation_complexity"
                ]
            ):
                self.edd_profiles_text["type_of_business_relationship"][
                    "complex_structure"
                ] = None

    def parse_request_type(self):
        """Parse the request type, organisational unit, and reference case portions from the EDD text file."""

        start_sentence = "2. Request type:"
        stop_sentence = "3. Risk category:"

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )[0].split("\n\n")

        self.edd_profiles_text["request_type"] = result[0]
        self.edd_profiles_text["org_unit"] = None
        self.edd_profiles_text["ref_cases"] = None
        try:
            if "Organisational Unit" in result[1]:
                self.edd_profiles_text["org_unit"] = result[1].split("\n")[1].strip()
            if "Reference Cases" in result[2]:
                self.edd_profiles_text["ref_cases"] = result[2]
        except Exception as e:
            logger.info(
                "Parsing error for organisational unit and/or reference cases, trace below."
            )
            logger.info(traceback.print_exception(e))

    def parse_risk_category(self):
        """Parse the risk category portion of the EDD text file."""

        start_sentence = "3. Risk category:"
        stop_sentence = "4. Purpose of business relationship:"

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        self.edd_profiles_text["risk_category"] = result[0]

    def parse_purpose_of_br(self):
        """Parse the purpose of business relationship portion of the EDD text file."""

        start_sentence = "4. Purpose of business relationship:"
        stop_sentence = "5. Expected NNM/ Current AuM:"

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        self.edd_profiles_text["purpose_of_business_relationship"] = result[0]

    def parse_expected_nnm_or_current_aum(self):
        """Parse the expected net new money / current assets under management portion of the EDD text file."""

        start_sentence = "5. Expected NNM/ Current AuM:"
        stop_sentence = "6. Anticipated transaction pattern / Transactions:"

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        self.edd_profiles_text["expected_nnm_or_current_aum"] = result[0]

    def parse_transactions(self):
        """Parse the anticipated transaction pattern / transactions portion of the EDD text file."""

        start_sentence = "6. Anticipated transaction pattern / Transactions:"
        stop_sentence = "7. Power of Attorney Information:"

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        self.edd_profiles_text["transactions"] = result[0]

    def parse_activities(self):
        """Parse the activity portion of the EDD text file."""

        start_sentences = ["7. Activity:", "7. Corporate business activity:"]
        stop_sentences = [
            "8. Total Wealth and Composition of Wealth:",
            "8. Key financial information:",
        ]

        result = extract_between_specific_sentences(
            self.text, start_sentences, stop_sentences
        )

        processed_results = []
        for r in result:
            tag = "activity" if "7. Activity:" in r else "corporate_business_activity"
            res = "\n".join(r.split("\n")[1:]).strip()
            processed_results.append((tag, res))

        self.edd_profiles_text["activity"] = []

        tag, res = processed_results[0]
        self.edd_profiles_text["contractual_partner_information"][tag] = res

        for i in range(1, len(processed_results)):
            tag, res = processed_results[i]
            self.edd_profiles_text["role_holders_information"][i - 1][tag] = res

    def parse_total_wealth_and_composition_of_wealth(self):
        """Parse the total wealth and composition of wealth portion of the EDD text file."""

        start_sentences = [
            "8. Total Wealth and Composition of Wealth:",
            "8. Key financial information:",
        ]
        stop_sentence = "9. Origin of assets and corroboration:"

        result = extract_between_specific_sentences(
            self.text, start_sentences, stop_sentence
        )

        processed_results = []
        for r in result:
            tag = (
                "total_wealth_composition"
                if "8. Total" in r
                else "key_financial_information"
            )
            res = "\n".join(r.split("\n")[1:]).strip()
            processed_results.append((tag, res))

        tag, res = processed_results[0]
        self.edd_profiles_text["contractual_partner_information"][tag] = res

        for i in range(1, len(processed_results)):
            tag, res = processed_results[i]
            self.edd_profiles_text["role_holders_information"][i - 1][tag] = res

    def parse_sow(self):
        """Parse the source of wealth portion of the EDD text file."""

        start_sentence = "9. Origin of assets and corroboration:"
        stop_sentence = "===="

        result = extract_between_specific_sentences(
            self.text, start_sentence, stop_sentence
        )

        self.edd_profiles_text["contractual_partner_information"][
            "source_of_wealth"
        ] = result[0]

        for i in range(1, len(result)):
            self.edd_profiles_text["role_holders_information"][i - 1][
                "source_of_wealth"
            ] = result[i]

    def extract_corroboration_string(self, corroboration_chunks: list[str]):
        start_chunk = "Corroboration or Evidence:"

        result = []
        for chunk in corroboration_chunks:
            start_idx = chunk.find(start_chunk)
            result.append(chunk[start_idx:])

        corroboration_string = "\n".join(
            x for x in result if x.strip().startswith("Corroboration or Evidence:")
        )

        return corroboration_string

    def parse_corroboration(self):
        """Parse the corroboration and evidence portion of the EDD text file."""

        corroboration_chunks = self.edd_profiles_text[
            "contractual_partner_information"
        ]["source_of_wealth"].split("\n\n")

        self.edd_profiles_text["contractual_partner_information"]["corroboration"] = (
            self.extract_corroboration_string(corroboration_chunks)
        )

        for idx, role_holder in enumerate(
            self.edd_profiles_text["role_holders_information"]
        ):
            corroboration_chunks = role_holder["source_of_wealth"].split("\n\n")

            self.edd_profiles_text["role_holders_information"][idx]["corroboration"] = (
                self.extract_corroboration_string(corroboration_chunks)
            )

    def save_results(self, output_folder: str, case_number: str, filename: str):
        """Save the resulting EDD case dictionary in the specified location.

        Args:
            output_folder: str
                The parent folder in which to save the results.

            case_number: str
                The EDD case number.

            filename: str
                The desired filename for the result.
        """
        output_dir = os.path.join(output_folder, case_number)
        os.makedirs(output_dir, exist_ok=True)
        save_path = os.path.join(output_dir, filename)
        logger.info("Saving edd_profiles_text ...")
        with open(save_path, "w") as f:
            json.dump(self.edd_profiles_text, f, indent=2)
        logger.info(f"Saved parsed data to: {save_path}")
        return save_path


def extract_between_specific_sentences(
    file_text: str, start_sentences: str | List[str], stop_sentences: str | List[str]
) -> List[str]:
    """Return a list of all substrings between the start and stop sentences within a given text.

    Args:
        file_text: str
            The text to process.

        start_sentences: str | List[str]
            The starting sentence - N.B. this will not be included in the resulting substring.

        stop_sentence: str | List[str]
            The ending sentence - N.B. this will not be included in the resulting substring.
    """
    lines = file_text.split("\n")
    extract = False
    extracted_sections = []
    current_section = []

    if isinstance(start_sentences, str):
        start_sentences = [start_sentences]

    if isinstance(stop_sentences, str):
        stop_sentences = [stop_sentences]

    for line in lines:
        if extract:
            # Check if the stop sentence is in the line
            if any(stop_sentence in line for stop_sentence in stop_sentences):
                extracted_sections.append("\n".join(current_section).strip())
                current_section = []  # Reset the current section
                extract = False  # Stop extracting after finding the stop sentence
            else:
                # Filter out lines containing '==='
                if "===" not in line:
                    current_section.append(line.strip())
        if any(start_sentence in line for start_sentence in start_sentences):
            extract = True  # Start extracting after finding the start sentence
            if any(
                x in start_sentences[0]
                for x in ["7. Activity", "7. Corporate", "8. Total", "8. Key"]
            ):
                current_section.append(line.strip())

    # If extraction was still ongoing at the end of the text (ie. multiple sections with same
    # start_sentence and stop_sentence, eg. Beneficial owners)
    if current_section:
        extracted_sections.append("\n".join(current_section).strip())

    return extracted_sections


def file_validity_checker(file_text: str):
    """Simple keyword search in the EDD text file.

    Args:
        file_text: str
            The contents of the EDD text file.
    """
    for keyword in INVALID_CASE_KEYWORDS:
        if keyword in file_text:
            return False

    return True
