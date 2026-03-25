from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI

from main.constants import (
    AZURE_OPENAI_LLM_CONFIG,
    ESTIMATE_INVESTMENT_RETURNS,
    TI_FREQUENCY_CONVERSION_DICT,
)
from main.utils.amount import Amount
from main.utils.grammars import ExplicitAnswer
from main.utils.number_parser import NumberParser


class TotalIncomeExtractor:

    def __init__(
        self,
        llm_args: dict = AZURE_OPENAI_LLM_CONFIG,
        ti_freq_conversion: dict = TI_FREQUENCY_CONVERSION_DICT,
        ti_invest_rate: dict = ESTIMATE_INVESTMENT_RETURNS,
        return_lower_bound: bool = True,
    ):
        self.return_lower_bound = return_lower_bound
        self.num_llm = AzureChatOpenAI(**llm_args)
        self.llm_struct = self.num_llm.with_structured_output(ExplicitAnswer)
        self.number_parser = NumberParser()
        self.conv_frequencies = ti_freq_conversion
        self.ti_invest_rate = ti_invest_rate

    def __call__(self, data, sow_dictionary):
        full_text_res_employment = self.build_extract_employment(sow_dictionary)
        investments_classified = self.estimate_investment_returns(sow_dictionary)
        computed_income = sum([item.get('Amount')[-1] for item in investments_classified.values() if item.get('Amount') is not None], Amount(0))
        computed_income += sum([amount for desc, amount in filter(lambda _: _[1] is not None, full_text_res_employment)], Amount(0))
        if data["client_type"] == "Natural Person":
            remarks_total_assets = data["total_assets"]["remarks_total_assets"]
        else:
            remarks_total_assets = data["financial_text"]
        explicit_income_amount = self.extract_explicit_income_mention(remarks_total_assets)

        return computed_income, full_text_res_employment, investments_classified, explicit_income_amount

    def extract_explicit_income_mention(self, context):

        explicit_question = """
Is there an estimate of the total yearly income of the client explicitly stated in the client notes ?

    {client}

    Only include current employment and not former ones for this field. Do not try to create your own estimate.
"""
        template = PromptTemplate(
            template=explicit_question, input_variables=["client"]
        )
        system_message = SystemMessage("""
Answer in the following format:
    {
        'answer': it can be only 'Yes' or 'No',
        'value': list of values or range of the client's total current yearly income followed by their three-letters currency ISO code
    }

    If no estimate can be determined, set 'value' to an empty list
""")
        human_message = HumanMessage(template.format(client=context))
        messages = [system_message, human_message]
        response = self.llm_struct.invoke(messages)

        explicit_income_amount = None
        if response["answer"] == "Yes":
            tmp = self.number_parser(str(response["value"][0]))
            if tmp is not None and len(tmp) > 0:
                explicit_income_amount = tmp[0]
        return explicit_income_amount

    def build_extract_employment(self, sow_dictionary):
        result_json = {
            sow: {"Value": metadata["Net Income"], "Frequency": metadata["Frequency"]}
            for sow, metadata in sow_dictionary.items()
            if (metadata["Net Income"] != "" and metadata["Is Current"] == "Yes")
        }

        list_set_incomes = []
        for key in result_json:
            temp_amount = self.number_parser(result_json[key]["Value"])
            if temp_amount and result_json[key]["Frequency"] != "":
                amount = temp_amount[-1]
                amount.number = (
                    amount.number * self.conv_frequencies[result_json[key]["Frequency"]]
                )
                list_set_incomes.append((key, amount))
            else:
                list_set_incomes.append((key, None))
        return list_set_incomes

    def estimate_investment_returns(self, sow_dictionary):
        result_json = {
            sow: {
                "Justification": metadata["Justification"],
                "Type": metadata["Investment"],
                "Amount": metadata["Asset Value"],
            }
            for sow, metadata in sow_dictionary.items()
            if metadata["Class"] == "asset"
            and metadata["Net Income"] == ""
            and metadata["Asset Value"] != ""
        }

        for _, value in result_json.items():
            value["Amount"] = self.number_parser(value["Amount"])
            value["Percent Return"] = (
                self.ti_invest_rate.get(value["Type"]) if value["Type"] else 0
            )
            if not value["Percent Return"]:
                value["Percent Return"] = 0
            if value["Amount"]:
                value["Return"] = value["Amount"][-1] * value["Percent Return"] / 100
            else:
                value["Return"] = None
        return result_json
