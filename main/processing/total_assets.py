from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI

from main.constants import AZURE_OPENAI_LLM_CONFIG
from main.utils.grammars import ExplicitAnswer
from main.utils.number_parser import NumberParser


class TotalAssetsExtractor:

    def __init__(self, llm_config: dict = AZURE_OPENAI_LLM_CONFIG):
        self.llm = AzureChatOpenAI(**llm_config)
        self.llm_struct = self.llm.with_structured_output(ExplicitAnswer)
        self.number_parser = NumberParser()

    def parse_num(self, string):
        res = self.number_parser(string)
        if res:
            return min(res)

    def __call__(self, data, sow_dictionary):
        if data["client_type"] == "Natural Person":
            remarks_total_assets = data["total_assets"]["remarks_total_assets"]
            estimated_assets = data["total_assets"]["Total estimated assets"][0]
        else:
            remarks_total_assets = data["financial_text"]
            estimated_assets = None
        context = remarks_total_assets
        explicit_question = """
Is there an estimate of the total wealth of the client explicitly stated in the client notes ?

    {client}

    Do not try to create your own estimate.
"""
        template = PromptTemplate(
            template=explicit_question, input_variables=["client"]
        )
        system_message = SystemMessage("""
Answer in the following format:
    {
        'answer': it can be only 'Yes' or 'No',
        'value': list of values or range of the client's total wealth followed by their three-letters currency ISO code
    }

    If no estimate can be determined, set 'value' to an empty list
""")
        human_message = HumanMessage(template.format(client=context))
        messages = [system_message, human_message]
        response = self.llm_struct.invoke(messages)

        # # Save different possible asset totals
        alternative_totals = {}
        alternative_totals["structured_ta"] = estimated_assets
        alternative_totals["unstructured_explicit_ta"] = None
        if response["answer"] == "Yes":
            tmp = self.number_parser(response["value"][0])
            if tmp is not None and len(tmp) > 0:
                alternative_totals["unstructured_explicit_ta"] = tmp[0]

        complicated_amounts = {
            sow: metadata["Asset Value"]
            for sow, metadata in sow_dictionary.items()
            if metadata["Class"] == "asset"
        }

        alternative_totals["unstructured_deduced_assets"] = {
            x: self.parse_num(y) for x, y in complicated_amounts.items()
        }
        alternative_totals["unstructured_deduced_assets"] = {
            x: y
            for x, y in alternative_totals["unstructured_deduced_assets"].items()
            if y is not None
        }

        return alternative_totals
