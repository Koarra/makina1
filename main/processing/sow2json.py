from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import PromptTemplate
from langchain_openai import AzureChatOpenAI

from main.constants import (AZURE_OPENAI_LLM_CONFIG, CLIENT_HISTORY_PROMPT,
                             SOW_SYSTEM_PROMPT)
from main.utils.grammars import SowToJson, validate_model_with_pydantic
from main.utils.sow_parser import SowParser


class Sow2Dict:

    def __init__(
        self,
        map_prompt: str = CLIENT_HISTORY_PROMPT,
        system_prompt: str = SOW_SYSTEM_PROMPT,
        llm_config: dict = AZURE_OPENAI_LLM_CONFIG,
    ):

        self.__system_prompt = SystemMessage(system_prompt)
        self.__generation_prompt = PromptTemplate(
            template=map_prompt, input_variables=["client"]
        )
        self.__generation_engine = AzureChatOpenAI(**llm_config).with_structured_output(
            SowToJson
        )

        self.parser = SowParser()

    def __call__(self, data: dict):
        try:
            origins = data["origin_of_assets"]
            if data["client_type"] == "Natural Person":
                remarks_total_assets = data["total_assets"]["remarks_total_assets"]
            else:
                remarks_total_assets = data["financial_text"]
        except KeyError as exc:
            raise KeyError(
                "Sow2Dict expects PDF parser output with keys "
                "`origin_of_assets` and `total_assets.remarks_total_assets`."
            ) from exc

        assets = [remarks_total_assets] if remarks_total_assets else []

        total_assets_origin_of_assets = "\n".join([x for x in (origins + assets) if x])
        human_message = HumanMessage(
            self.__generation_prompt.format(client=total_assets_origin_of_assets)
        )
        messages = [self.__system_prompt, human_message]
        response = self.__generation_engine.invoke(messages)
        response = validate_model_with_pydantic(
            self.__generation_engine, response, SowToJson
        )

        sow_dictionary = {}
        for sow in response.activities:
            sow_dictionary_key = sow.description
            with_spaces_dict = {}
            for key, value in sow.details.model_dump(mode="json").items():
                key = key.replace("_", " ")
                with_spaces_dict[key] = value
            sow_dictionary[sow_dictionary_key] = with_spaces_dict
        return self.parser(sow_dictionary), sow_dictionary
