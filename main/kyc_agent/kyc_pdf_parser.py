import math
import re
from dataclasses import asdict, is_dataclass

import pdfplumber

from main.utils.number_parser import NumberParser


class BasePDFLoader:

    CLIENT_NAMES = ["Client:", "Kunde:", "Cliente:"]

    TRANSACTIONS = {"Transactions", "Transazioni", "Transaktionen"}

    TRANSACTION_KEYWORDS = {
        "EN": [
            "Type of transaction",
            "Date/Periodicity",
            "Volume",
            "CCY",
            "Outgoing/Incomingtransactions",
            "Name of counterparty",
            "Last modification",
        ],
        "FR": [
            "Type detransaction",
            "Date/Périodicité",
            "Volume",
            "MONN",
            "Transactionsentrantes/sortantes",
            "Nom de la contrepartie",
            "Dernière modification:",
        ],
        "IT": [
            "Tipo di transazione",
            "Data/Periodicità",
            "Volume",
            "MON",
            "Transazioni inentrata/uscita",
            "Nome della controparte",
            "ultima modifica:",
        ],
        "DE": [
            "Transaktionsart",
            "Datum/Periodizität",
            "Volumen",
            "WHRG",
            "Eingehende/AusgehendeTransaktionen",
            "Name der Gegenpartei",
            "Letzte Änderung:",
        ],
    }

    # Purpose of business relationship
    PURPOSE_BR_START = [
        "Purpose of the business relationship:",
        "Zweck der Geschäftsbeziehung:",
        "But de la relation d'affaires:",
        "Scopo della relazione d'affari:",
    ]
    PURPOSE_BR_END = [
        "Archived purpose of the business relationship",
        "Archivierter Zweck der Geschäftsbeziehung",
        "But de la relation d'affaires archivé",
        "Scopo della relazione d'affari archiviato",
    ]

    # Last modifications name
    LAST_MODIFICATION = [
        "Last modification:",
        "Letzte Änderung:",
        "Dernière modification:",
        "ultima modifica:",
    ]

    COLUMN_NAMES_TRANSACTIONS = [
        "transaction_type",
        "transaction_periodicity",
        "transaction_volume",
        "transaction_currency",
        "incoming_or_outgoing",
        "transaction_counterparty",
    ]

    def load(self, pdf_path):
        with pdfplumber.open(pdf_path) as pdf:
            text = "\n".join([page.extract_text(layout=True) for page in pdf.pages])
            char_metadata = []
            for page in pdf.pages:
                cell_ordering = "".join([c["text"] for c in page.chars])
                client_kw = None
                for kw in self.CLIENT_NAMES:
                    if kw in cell_ordering:
                        client_kw = kw
                        break

                page_marker_start = cell_ordering.rindex(client_kw)

                char_metadata.extend(
                    page.chars[:page_marker_start]
                )  # We don't care about page marker metadata (fix for multi-page table parsing)

            return text, char_metadata

    def parse(self, path) -> dict:
        pass

    def is_valid_document(self, path) -> bool:
        pass

    def manually_parse_table(
        self,
        char_metadata: list[dict],
        table_keywords: dict[list],
        column_names_kyc: list[str],
        is_trx: bool = False,
    ):
        """Parse a table given its column keywords, the resulting column names, and character metadata obtained from pdfplumber.

        Args:
            char_metadata: list[dict]
                the character metadata of the whole client history document (without the ending page markers)

            table_keywords: list[str]
                the keywords in FR,EN,DE,IT to be considered

            column_names_kyc: list[str]
                the column names of the resulting table

        For your reference, this is how the coordinate system works for character bounding boxes:

        ^ y-axis
        |
        y1 • ......
        |  . [  ] .
        |  . [  ] .
        y0 • ......
        |
        ---•-----•---> x-axis
             x0   x1

        """

        cell_ordering = "".join([c["text"] for c in char_metadata])

        # Step 1. Identify the exact table column keywords
        keywords = self._identify_column_keywords(
            cell_ordering, char_metadata, table_keywords
        )

        if keywords is None:  # Could not find all the table keywords -> cannot parse
            return []

        # Step 2. Identify the columns' starting indices in the metadata array,
        # as well as their x0-coordinates - which will be used to determine each character's
        # column index later on
        column_names = keywords[1:-1] if not is_trx else keywords[:-1]
        column_indices, column_x0, start_idx, end_idx = self._identify_column_limits(
            cell_ordering, char_metadata, keywords, column_names
        )

        filtered_metadata = char_metadata[
            column_indices[-1] + len(column_names[-1]) : end_idx
        ]

        if is_trx:
            offset = column_indices[-1] + len(column_names[-1])
            table_chunk = cell_ordering[offset:end_idx]
            row_starts = {"Incoming", "Outgoing"}

            tmp = []
            for x in row_starts:
                tmp.extend([m.start() for m in re.finditer(x, table_chunk)])

            tmp.sort()

            row_start_idx = [0]
            purpose_kws = {
                "Purpose and details of transaction",
                "Zweck und Details der Transaktion",
                "But et détails de la transaction",
                "Scopo e dettagli della transazione:",
            }
            purpose_kw = "Purpose and details of transaction"
            for kw in purpose_kws:
                if kw in table_chunk:
                    purpose_kw = kw
                    break
            for idx in tmp[1:]:
                row_y0 = filtered_metadata[idx]["y0"]
                _ = idx - 1
                while math.isclose(filtered_metadata[_]["y0"], row_y0, rel_tol=9e-3):
                    _ -= 1
                row_start_idx.append(_ + 1)

            row_end_idx = [m.start() for m in re.finditer(purpose_kw, table_chunk)]

            if len(row_end_idx) < len(row_start_idx):
                return []

            purposes = [
                table_chunk[
                    row_end_idx[i]
                    + len(purpose_kw) : (
                        row_start_idx[i + 1] if i < len(row_start_idx) - 1 else end_idx
                    )
                ]
                for i in range(len(row_start_idx))
            ]

            filtered_metadata = []

            for start, end in zip(row_start_idx, row_end_idx):
                filtered_metadata.extend(char_metadata[offset + start : offset + end])

        # Step 3. Start the proper table parsing
        column_chars = self._parse_table(filtered_metadata, column_names, column_x0)

        parsed_table = self._process_rows_into_table(column_chars, column_names_kyc)

        if len(parsed_table) == 1 and all(
            len(v.strip()) == 0 for _, v in parsed_table[0].items()
        ):
            return []

        if is_trx:
            for idx, purpose in enumerate(purposes):
                parsed_table[idx].update({"transaction_details": purpose})

        return parsed_table

    def _find_column_index(self, column_x0, x1):
        num_columns = len(column_x0)
        for i in range(num_columns):
            if x1 >= column_x0[i] and (
                x1 <= column_x0[i + 1] if i < num_columns - 1 else True
            ):
                return i

        return 0

    def _identify_column_keywords(self, cell_ordering, char_metadata, table_keywords):
        for _, kw in table_keywords.items():
            if all(k in cell_ordering for k in kw):
                return kw

        return None

    def _identify_column_limits(
        self, cell_ordering, char_metadata, keywords, column_names
    ):
        starting_chunk = "".join(keywords[:-1])
        ending_chunk = keywords[-1]

        start_idx = cell_ordering.find(starting_chunk)

        column_indices = [cell_ordering.find(column_names[0], start_idx)]

        for idx, column_name in enumerate(column_names):
            if idx == 0:
                continue
            column_indices.append(
                cell_ordering.find(column_name, column_indices[idx - 1])
            )

        column_x0 = [char_metadata[idx]["x0"] for idx in column_indices]

        end_idx = cell_ordering.find(ending_chunk, column_indices[-1])

        return column_indices, column_x0, start_idx, end_idx

    def _parse_table(self, filtered_metadata, column_names, column_x0):
        current_column_idx = 0
        current_row_idx = 0
        num_columns = len(column_names)
        column_chars = [[[] for _ in range(num_columns)]]

        if len(filtered_metadata) == 0:
            return column_chars

        last_x1 = filtered_metadata[0]["x1"]
        last_y1 = filtered_metadata[0]["y1"]
        last_y0 = filtered_metadata[0]["y0"]
        overlap_possible = False

        for c in filtered_metadata:

            x1 = c["x1"]
            y0 = c["y0"]
            y1 = c["y1"]

            if current_column_idx < num_columns - 1:
                if (
                    x1 >= column_x0[current_column_idx]
                    and x1 <= column_x0[current_column_idx + 1]
                ):
                    if (
                        x1 < last_x1
                    ):  # Bug fix 1: new line in current cell -> append a space, as this is not automatic
                        column_chars[current_row_idx][current_column_idx].append(" ")
                        overlap_possible = True
                        # don't update the index
                    elif overlap_possible and not (
                        y0 > last_y1 or (y1 < last_y0 and x1 < last_x1)
                    ):
                        # The current line hasn't jumped back up, so we are not updating the column index yet
                        pass
                    else:
                        overlap_possible = False

                        new_column_idx = self._find_column_index(column_x0, x1)

                        if new_column_idx < current_column_idx:
                            current_row_idx += 1
                            overlap_possible = False
                            column_chars.append([[] for _ in range(num_columns)])

                        current_column_idx = new_column_idx

            else:
                if x1 >= column_x0[current_column_idx]:
                    pass
                    # don't update the indices
                else:  # new **table** row
                    current_column_idx = self._find_column_index(column_x0, x1)

                    current_row_idx += 1
                    overlap_possible = False
                    column_chars.append([[] for _ in range(num_columns)])

            column_chars[current_row_idx][current_column_idx].append(c["text"])
            last_x1 = x1
            last_y1 = y1
            last_y0 = y0

        return column_chars

    def _process_rows_into_table(self, column_chars, column_names_kyc):
        processed_rows = [
            ["".join(cell_chars) for cell_chars in row] for row in column_chars
        ]

        tmp_rows = []
        eliminated_rows = 0

        for idx, row in enumerate(processed_rows):
            nonzero_columns = [ci for ci, cell in enumerate(row) if len(cell) > 0]
            if len(nonzero_columns) == 1:
                ci = nonzero_columns[0]
                tmp_rows[idx - eliminated_rows - 1][ci] += " " + row[ci]
                eliminated_rows += 1
            else:
                tmp_rows.append(row)

        parsed_table = [
            {
                column_name_kyc: column_text
                for column_name_kyc, column_text in zip(column_names_kyc, row)
            }
            for row in tmp_rows
        ]

        return parsed_table

    def split_and_trim(self, string):
        parts = string.split(":")
        if len(parts) > 1:
            return parts[1].strip()
        return None


class ProcessInputPDF(BasePDFLoader):

    natural_person_strings = ["Name:", "Nome:", "Nom:"]

    required_substring_sets = [
        {"Name:", "Domicile:", "Client history"},
        {"Name:", "Domizil:", "Kundengeschichte"},
        {"Name:", "Domizil:", "Nota informativa sul cliente"},
        {"Nome:", "Domicilio:", "Nota informativa sul cliente"},
        {"Nom:", "Domicile:", "Historique du client"},
    ]

    ACTIVITIES = ["Tätigkeit", "Activity", "Activité", "Attività"]
    ACTIVITY_KEYWORDS = {
        "EN": [
            "Activity",
            "Job status",
            "Function",
            "Employer/Company",
            "Activity",
            "Insider",
            "sector",
            "Licensed/registered entity",
            "Last modification",
        ],
        "DE": [
            "Tätigkeit",
            "Berufsstatus",
            "Funktion",
            "Arbeitgeber/Firma",
            "Tätigkeit",
            "Insider",
            "Branche",
            "Licensed/registered entity",
            "Letzte Änderung",
        ],
        "FR": [
            "Activité",
            "Statut prof.",
            "Fonction",
            "Employeur/Société",
            "Activité",
            "Insider",
            "Secteur",
            "Licensed/registered entity",
            "Dernière modification",
        ],
        "IT": [
            "Attività",
            "Stato prof.",
            "Funzione",
            "Datore di lavoro /Ditta",
            "Attività",
            "Insider",
            "settore",
            "Licensed/registered entity",
            "ultima modifica",
        ],
    }

    FAMILY_SITUATION = [
        "Familiensituation",
        "Family situation",
        "situation familiale",
        "situazione familiare",
    ]

    FAMILY_SITUATION_KEYWORDS = {
        "EN": [
            "Family situation",
            "Description",
            "Name, first name",
            "Marital status",
            "Date of birth",
            "Nationality",
            "Insider",
            "Remarks",
            "Last modification",
        ],
        "DE": [
            "Familiensituation",
            "Beschreibung",
            "Name, Vorname",
            "Zivilstand",
            "Geburtsdatum",
            "Nationalität",
            "Insider",
            "Bemerkungen",
            "Letzte Änderung",
        ],
        "FR": [
            "situation familiale",
            "Description",
            "Nom, prénom",
            "État civil",
            "Date de naiss.",
            "Nationalité",
            "Insider",
            "Remarques",
            "Dernière modification",
        ],
        "IT": [
            "situazione familiare",
            "Descrizione",
            "Cognome, nome",
            "Stato civile",
            "Data dinascita",
            "Nazionalità",
            "Insider",
            "Osservazioni",
            "ultima modifica",
        ],
    }

    FAMILY_SITUATION_REMARKS = {
        "EN": ["Details on family situation", "Transactions", "Client:"],
        "DE": ["Details Familiensituation", "Transaktionen", "Kunde:"],
        "FR": ["Détails sur la situation familiale", "Transactions", "Client:"],
        "IT": ["Dettagli sulla situazione familiare", "Transazioni", "Cliente:"],
    }

    COLUMN_NAMES_FAMILY = [
        "relationship_type",
        "name",
        "marital_status",
        "date_of_birth",
        "nationality",
        "insider",
        "remarks",
    ]

    COLUMN_NAMES_KYC = [
        "job_status",
        "function",
        "employer",
        "activity",
        "insider",
        "sector",
        "licensed_or_registered_entity",
    ]

    def process_client_history(self, string_client_history: str, char_metadata: list):
        client = {}
        client["origin_of_assets"] = []
        client["activities"] = []
        client["total_assets"] = {}
        client["total_assets"]["Total estimated assets"] = None
        client["total_assets"]["Total liquid assets"] = None
        client["total_assets"]["Total real estate assets"] = None
        client["total_assets"]["Total other non-liquid assets"] = None
        client["total_assets"]["remarks_total_assets"] = None
        client["family_situation_entries"] = []
        client["family_situation_remarks"] = None
        client["transactions"] = []
        client["purpose_of_br"] = []

        # Loop through the lines of the extracted client history to get the relevant fields
        lines = string_client_history.split("\n")
        for i, line in enumerate(lines):
            if (
                any(element in line for element in ["Name:", "Nom:", "Nome:"])
                and "name" not in client
            ):
                temp_name = self.split_and_trim(line)
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].strip()
                        for element in [
                            "Bankbeziehung:",
                            "Banking relationship:",
                            "Relation bancaire:",
                            "Relazione bancaria:",
                        ]
                    ):
                        break
                    temp_name += " " + lines[j].strip()
                client["name"] = temp_name

            if (
                any(
                    element in line
                    for element in ["Domicile:", "Domizil:", "Domicilio:"]
                )
                and "domicile" not in client
            ):
                client["domicile"] = self.split_and_trim(line)

            if any(element in line for element in self.PURPOSE_BR_START):
                purpose = line.split(":")[1].strip()
                temp_purpose_details = []
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].strip()
                        for element in (
                            self.PURPOSE_BR_START
                            + self.PURPOSE_BR_END
                            + self.LAST_MODIFICATION
                        )
                    ):
                        break
                    temp_purpose_details.append(lines[j].strip())
                purpose_of_br = {
                    "purpose": purpose,
                    "details": "\n".join(temp_purpose_details),
                }
                client["purpose_of_br"].append(purpose_of_br)

            if any(
                element in line
                for element in [
                    "Herkunft der Vermögenswerte",
                    "Origin of assets",
                    "Origine des valeurs patrimoniales",
                    "Provenienza dei valori patrimoniali",
                ]
            ):
                j = 1
                init_new_origin = ""
                for j in range(i, len(lines)):
                    init_new_origin += lines[j].strip() + " "
                    if any(
                        element in lines[j].replace(" ", "")
                        for element in [
                            "HerkunftDetails",
                            "OriginDetails",
                            "OrigineDétails",
                            "ProvenienzeaDettagli",
                        ]
                    ):
                        init_new_origin = ""
                    if any(
                        element in lines[j].replace(" ", "")
                        for element in [
                            "BestätigungoderNachweisDetails",
                            "CorroborationorevidenceDetails",
                            "ConfirmationoupreuveDetails",
                            "ConfermacomprovaDettagli",
                        ]
                    ):
                        break
                client["origin_of_assets"].append(init_new_origin)

            if any(
                element in line
                for element in [
                    "Bemerkungen zum Total Vermögenswerte und der Vermögenszusammensetzung",
                    "Remarks on total assets and asset composition",
                    "Remarques concernant le total des actifs et la composition du patrimoine",
                    "Osservazioni sul totale dei valori patrimoniali e sulla loro composizione",
                ]
            ):
                init_remarks = ""
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].strip()
                        for element in ["Tätigkeit", "Activity", "Activité", "Attività"]
                    ):
                        client["total_assets"]["remarks_total_assets"] = init_remarks
                        break
                    init_remarks += lines[j].strip() + " "

            if any(
                element in line
                for element in [
                    "Gesamtvermögen / Zusammensetzung",
                    "Total assets / Composition",
                    "Fortune totale / Composition",
                    "Patrimonio complessivo / Composizione",
                ]
            ):
                iso_currency = ""
                total_amounts = [None] * 4
                visited = 0
                for j in range(i + 1, len(lines)):
                    if "KYC" in lines[j].strip():
                        parts = lines[j].split("KYC")
                        pattern = r"\b[A-Z]{3}\b"
                        matches = re.findall(pattern, parts[1])
                        iso_currency = matches[0]
                    if "Total" in lines[j].strip():
                        str_clean = (
                            lines[j]
                            .strip()
                            .replace("\u2019", "")
                            .replace("\u2018", "")
                            .replace(".00", "")
                            .replace("n.a.", "")
                            .replace(",", "")
                        )

                        array_numbers = re.findall(r"\d+", str_clean)

                        if array_numbers:
                            str_number = sorted(array_numbers, key=len)[-1]
                        else:
                            str_number = array_numbers
                        str_amount_currency = str(str_number) + " " + iso_currency

                        parser = NumberParser()
                        amount = parser(str_amount_currency)
                        total_amounts[visited] = amount
                        visited += 1
                    if visited == 4 or any(
                        element in lines[j].strip()
                        for element in [
                            "Bemerkungen zum Total Vermögenswerte und der Vermögenszusammensetzung",
                            "Remarks on total assets and asset composition",
                            "Remarques concernant le total des actifs et la composition du patrimoine",
                            "Osservazioni sul totale dei valori patrimoniali e sulla loro composizione",
                        ]
                    ):
                        break

                client["total_assets"]["Total estimated assets"] = total_amounts[0]
                client["total_assets"]["Total liquid assets"] = total_amounts[1]
                client["total_assets"]["Total real estate assets"] = total_amounts[2]
                client["total_assets"]["Total other non-liquid assets"] = total_amounts[
                    3
                ]

            if any(
                element in line
                for element in ["Tätigkeit", "Activity", "Activité", "Attività"]
            ):
                activity = ""
                for j in range(i + 1, len(lines)):
                    activity += lines[j].strip() + " "
                    if any(
                        element in lines[j].strip()
                        for element in [
                            "Familiensituation",
                            "Family situation",
                            "Situation familiale",
                            "Situazione familiare",
                        ]
                    ):
                        client["activities"] = activity
                        break

        if any(x in string_client_history for x in self.ACTIVITIES):

            parsed_activity_table = self.manually_parse_table(
                char_metadata=char_metadata,
                table_keywords=self.ACTIVITY_KEYWORDS,
                column_names_kyc=self.COLUMN_NAMES_KYC,
            )

            client["activities"] = parsed_activity_table

        if any(x in string_client_history for x in self.FAMILY_SITUATION):

            parsed_family_situation_table = self.manually_parse_table(
                char_metadata=char_metadata,
                table_keywords=self.FAMILY_SITUATION_KEYWORDS,
                column_names_kyc=self.COLUMN_NAMES_FAMILY,
            )

            if len(parsed_family_situation_table) == 1 and all(
                len(v.strip()) == 0 for _, v in parsed_family_situation_table[0].items()
            ):
                parsed_family_situation_table = []

            client["family_situation_entries"] = parsed_family_situation_table

            remarks = ""
            for k, v in self.FAMILY_SITUATION_REMARKS.items():
                start = v[0]
                end = v[1]
                ignore_kw = v[2]
                start_idx = string_client_history.find(start)
                end_idx = string_client_history.find(end, start_idx)
                alt_end_idx = string_client_history.find(ignore_kw, start_idx)

                if start_idx > -1 and (end_idx > start_idx or alt_end_idx > start_idx):
                    good_end_idx = end_idx if end_idx > start_idx else alt_end_idx

                    remarks = string_client_history[
                        start_idx + len(start) : good_end_idx
                    ]
                    remarks = (
                        remarks.replace("     .", "").replace("      ", "").strip()
                    )  # weird remnants

                    if good_end_idx == end_idx:
                        footer_idx = remarks.rfind(ignore_kw)
                        if footer_idx > -1:
                            after_idx = remarks.find("\n", footer_idx)
                            if after_idx > -1:
                                tmp = (
                                    remarks[:footer_idx] + remarks[after_idx:]
                                ).strip()
                                remarks = tmp
                            else:
                                remarks = remarks[:footer_idx].strip()

            client["family_situation_remarks"] = remarks

        if any(x in string_client_history for x in self.TRANSACTIONS):
            try:
                parsed_trx_table = self.manually_parse_table(
                    char_metadata=char_metadata,
                    table_keywords=self.TRANSACTION_KEYWORDS,
                    column_names_kyc=self.COLUMN_NAMES_TRANSACTIONS,
                    is_trx=True,
                )

                client["transactions"] = parsed_trx_table
            except:
                pass

        return client

    def is_valid_document(self, client_history: str):
        return any(
            client_history.strip().startswith(_) for _ in self.natural_person_strings
        )

    # Subfunction to check for required substrings
    def check_substrings(self, text, substring_sets):
        if not text:
            raise Exception(
                "No text was extracted from PDF - please check text from client history is selectable."
            )

        for substrings in substring_sets:
            if all(substring in text for substring in substrings):
                return True

        # If none of the sets are fully matched, raise an error
        raise Exception(
            "This PDF file is not in expected client history format. Please check the PDF text is actually selectable and that it is a Client History file."
        )

    def parse(self, pdf_path):
        string_client_history, char_metadata = self.load(pdf_path)

        if self.is_valid_document(string_client_history):

            # Check the PDF of client history contains extractable text and is natural person
            if self.check_substrings(
                string_client_history, self.required_substring_sets
            ):
                print("PDF succesfully read.")

            processed_client_history = self.process_client_history(
                string_client_history, char_metadata
            )

            self.client = processed_client_history
            return processed_client_history


class LegalEntityPDFLoader(BasePDFLoader):
    # Legal entity name
    LEGAL_ENTITY = [
        "Legal entity:",
        "Juristische Person:",
        "Persona giuridica:",
        "Personne morale:",
    ]

    # Banking relation name
    BANKING_RELATIONS = [
        "Bankbeziehung:",
        "Banking relationship:",
        "Relation bancaire:",
        "Relazione bancaria:",
    ]

    # Domicile name
    DOMCILES = ["Domicile:", "Domizil:", "Domicilio:"]

    # Motivation for LegalEntity
    MOTIVATION_TITLE = [
        "Motivation for holding a domiciliary company",
        "Motivation für die Verwendung einer Sitzgesellschaft",
        "Motivation pour l'utilisation d'une société de domicile",
        "Motivazione per l'utilizzo di una società di sede",
    ]
    MOTIVATION_END = [
        "Archived motivation for holding a domiciliary company",
        "Archivierte Motivation für die Verwendung einer Sitzgesellschaft",
        "Motivation archivée pour l'utilisation d'une société de domicile",
        "Motivazione archiviate per l'utilizzo di una società di sede",
    ]

    # Financial info
    FINANCIAL_TITLE = [
        "Key financial information",
        "Finanzkennzahlen",
        "Indicateurs financiers",
        "Indici finanziari",
    ]
    REMARKS_FINANCIALS = [
        "Remarks about key financial information",
        "Bemerkungen zu den Finanzkennzahlen",
        "Remarques relatives aux indicateurs financiers",
        "Osservazioni sugli indici finanziari",
    ]

    KEYWORDS_FINANCIALS = {
        "EN": [
            "Key financial information",
            "Financial year",
            "Report currency",
            "Number ofemployees",
            "Turnover p.a.",
            "Earnings before tax (EBT)",
            "Earnings after tax (EAT)",
            "Last modification",
        ],
        "DE": [
            "Finanzkennzahlen",
            "Geschäftsjahr",
            "Report-Währung",
            "Anzahl Mitarbeiter",
            "Umsatz p.a.",
            "Ergebnis vor Steuern(EBT)",
            "Ergebnis nach Steuern(EAT)",
            "Letzte Änderung",
        ],
        "FR": [
            "Indicateurs financiers",
            "Exercice",
            "Monnaie dereport",
            "Nombre decollaborateurs",
            "Chiffred'affaires p.a.",
            "Résultat avant impôt (EBT)",
            "Résultat après impôt(EAT)",
            "Dernière modification",
        ],
        "IT": [
            "Indici finanziari",
            "Esercizio",
            "Moneta dirapporto",
            "Numero dicollaboratori",
            "Cifra d'affarip.a.",
            "Utile al lordo delle imposte(EBT)",
            "Utile al netto delleimpose (EAT)",
            "Ultima modifica",
        ],
    }

    COLUMN_NAMES_KYC = [
        "financial_year",
        "report_currency",
        "number_of_employees",
        "annual_turnover",
        "earnings_before_tax",
        "earnings_after_tax",
    ]

    # Origin of Assets
    ORIGIN_OF_ASSETS_TITLE = [
        "Herkunft der Vermögenswerte",
        "Origin of assets",
        "Origine des valeurs patrimoniales",
        "Provenienza dei valori patrimoniali",
    ]
    ORIGIN_OF_ASSETS_START = [
        "HerkunftDetails",
        "OriginDetails",
        "OrigineDétails",
        "ProvenienzeaDettagli",
    ]
    ORIGIN_OF_ASSETS_END = [
        "BestätigungoderNachweisDetails",
        "CorroborationorevidenceDetails",
        "ConfirmationoupreuveDetails",
        "ConfermacomprovaDettagli",
    ]

    # Corporate Activity
    CORPORATE_ACTIVITY_TITLE = [
        "Corporate activity",
        "Geschäftstätigkeit des Unternehmens",
        "Activité commerciale de l'entreprise",
        "Attività economica dell'impresa",
    ]
    CORPORATE_ACTIVITY_END = [
        "MarketSales/ProcurementmarketEnteredonDetailsofinflows/outflows",
        "MarktAbsatz-/BeschaffungsmarktErfasstamDetailszudenZuflüssen/Abflüssen",
        "MarchéMarchédeventes/SaisileDétailssurlesentrées/sorties",
        "MercatoMercatodisbocco/RegistratoilDettaglisugliafflussi/suideflu",
    ]

    # Printed On
    PRINTED_ON = ["Printed on:", "Gedruckt am:", "Imprimé le:", "Stampato il:"]

    def process_client_history(self, string_client_history: str, char_metadata: list):
        legal_entity_args = {}
        legal_entity_args["name"] = ""
        legal_entity_args["domicile"] = ""
        legal_entity_args["purpose_of_br"] = []
        legal_entity_args["motivation"] = ""
        legal_entity_args["financial_table"] = ""
        legal_entity_args["financial_text"] = ""
        legal_entity_args["origin_of_assets"] = []
        legal_entity_args["corporate_activity"] = ""
        legal_entity_args["transactions"] = []

        # Loop through the lines of the extracted client history to get relevant fields
        lines = string_client_history.split("\n")
        for i, line in enumerate(lines):
            if any(element in line for element in self.LEGAL_ENTITY):
                temp_name = self.split_and_trim(line)
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].strip()
                        for element in self.BANKING_RELATIONS
                    ):
                        break
                    temp_name += " " + lines[j].strip()
                legal_entity_args["name"] = temp_name
            if any(element in line for element in self.DOMCILES):
                legal_entity_args["domicile"] = self.split_and_trim(line)
            if any(element in line for element in self.PURPOSE_BR_START):
                purpose = line.split(":")[1].strip()
                temp_purpose_details = []
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].strip()
                        for element in (
                            self.PURPOSE_BR_START
                            + self.PURPOSE_BR_END
                            + self.LAST_MODIFICATION
                        )
                    ):
                        break
                    temp_purpose_details.append(lines[j].strip())
                purpose_of_br = {
                    "purpose": purpose,
                    "details": "\n".join(temp_purpose_details),
                }
                legal_entity_args["purpose_of_br"].append(purpose_of_br)
            if any(element in line for element in self.MOTIVATION_TITLE):
                temp_motivation = []
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].strip()
                        for element in (self.MOTIVATION_END + self.LAST_MODIFICATION)
                    ):
                        break
                    temp_motivation.append(lines[j].strip())
                legal_entity_args["motivation"] = "\n".join(temp_motivation)
            if any(element in line for element in self.REMARKS_FINANCIALS):
                temp_financials = []
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].strip()
                        for element in self.ORIGIN_OF_ASSETS_TITLE
                    ):
                        break
                    temp_financials.append(lines[j])
                legal_entity_args["financial_text"] = "\n".join(temp_financials)
            if any(element in line for element in self.ORIGIN_OF_ASSETS_TITLE):
                init_new_origin = ""
                for j in range(i, len(lines)):
                    init_new_origin += lines[j].strip() + " "
                    if any(
                        element in lines[j].replace(" ", "")
                        for element in self.ORIGIN_OF_ASSETS_START
                    ):
                        init_new_origin = ""
                    if any(
                        element in lines[j].replace(" ", "")
                        for element in self.ORIGIN_OF_ASSETS_END
                    ):
                        legal_entity_args["origin_of_assets"].append(init_new_origin)
            if any(element in line for element in self.CORPORATE_ACTIVITY_TITLE):
                temp_corp_activity = []
                for j in range(i + 1, len(lines)):
                    if any(
                        element in lines[j].replace(" ", "")
                        for element in self.CORPORATE_ACTIVITY_END
                    ):
                        break
                    if not any(
                        element in lines[j].strip() for element in (self.PRINTED_ON)
                    ):
                        temp_corp_activity.append(lines[j])
                legal_entity_args["corporate_activity"] = "\n".join(temp_corp_activity)

        if any(x in string_client_history for x in self.FINANCIAL_TITLE):

            parsed_financial_table = self.manually_parse_table(
                char_metadata=char_metadata,
                table_keywords=self.KEYWORDS_FINANCIALS,
                column_names_kyc=self.COLUMN_NAMES_KYC,
            )
            legal_entity_args["financial_table"] = (
                parsed_financial_table  # TODO: confirm where or how this will be used
            )

        if any(x in string_client_history for x in self.TRANSACTIONS):
            try:
                parsed_trx_table = self.manually_parse_table(
                    char_metadata=char_metadata,
                    table_keywords=self.TRANSACTION_KEYWORDS,
                    column_names_kyc=self.COLUMN_NAMES_TRANSACTIONS,
                    is_trx=True,
                )

                legal_entity_args["transactions"] = parsed_trx_table
            except:
                pass

        return legal_entity_args

    def is_valid_document(self, client_history: str):
        return any(client_history.strip().startswith(_) for _ in self.LEGAL_ENTITY)

    def parse(self, pdf_path):
        string_client_history, char_metadata = self.load(pdf_path)
        if self.is_valid_document(string_client_history):

            processed_client_history = self.process_client_history(
                string_client_history, char_metadata
            )
            self.client = processed_client_history
            return processed_client_history


def fallback(obj):
    if is_dataclass(obj):
        return asdict(obj)
    raise TypeError(f"Object {obj} is not JSON serializable")
