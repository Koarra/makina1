from langgraph.graph import END, StateGraph

from main.constants import AZURE_OPENAI_LLM_CONFIG, run_compliance_check
from main.edd_agent.edd_checks import (activity, corroboration,
                                        expected_nnm_or_current_aum,
                                        expected_transactions, final_summary,
                                        negative_news,
                                        other_relevant_information,
                                        other_risk_aspects,
                                        purpose_of_business_relationship,
                                        request_type, risk_category,
                                        source_of_wealth,
                                        total_wealth_composition,
                                        type_of_business_relationship)
from main.edd_agent.edd_state import EddState


class EddAssessmentAgentOutput:

    def __init__(self, llm_config: dict = AZURE_OPENAI_LLM_CONFIG):
        # run_compliance_check = AzureChatOpenAI(**AZURE_OPENAI_LLM_CONFIG)
        self.graph = StateGraph(EddState)
        self.graph.add_node(
            "type_of_business_relationship", type_of_business_relationship
        )
        self.graph.add_node("request_type", request_type)
        self.graph.add_node("risk_category", risk_category)
        self.graph.add_node(
            "purpose_of_business_relationship",
            lambda s: purpose_of_business_relationship(s, run_compliance_check),
        )
        self.graph.add_node("expected_nnm_or_current_aum", expected_nnm_or_current_aum)
        self.graph.add_node(
            "expected_transactions",
            lambda s: expected_transactions(s, run_compliance_check),
        )
        self.graph.add_node("activity", lambda s: activity(s, run_compliance_check))
        self.graph.add_node(
            "total_wealth_composition",
            lambda s: total_wealth_composition(s, run_compliance_check),
        )
        self.graph.add_node(
            "source_of_wealth", lambda s: source_of_wealth(s, run_compliance_check)
        )
        self.graph.add_node("corroboration", corroboration)
        self.graph.add_node("negative_news", negative_news)
        self.graph.add_node("other_risk_aspects", other_risk_aspects)
        self.graph.add_node("other_relevant_information", other_relevant_information)
        self.graph.add_node(
            "final_summary", lambda s: final_summary(s, run_compliance_check)
        )
        self.graph.set_entry_point("type_of_business_relationship")
        self.graph.add_edge("type_of_business_relationship", "request_type")
        self.graph.add_edge("request_type", "risk_category")
        self.graph.add_edge("risk_category", "purpose_of_business_relationship")
        self.graph.add_edge(
            "purpose_of_business_relationship", "expected_nnm_or_current_aum"
        )
        self.graph.add_edge("expected_nnm_or_current_aum", "expected_transactions")
        self.graph.add_edge("expected_transactions", "activity")
        self.graph.add_edge("activity", "total_wealth_composition")
        self.graph.add_edge("total_wealth_composition", "source_of_wealth")
        self.graph.add_edge("source_of_wealth", "corroboration")
        self.graph.add_edge("corroboration", "negative_news")
        self.graph.add_edge("negative_news", "other_risk_aspects")
        self.graph.add_edge("other_risk_aspects", "other_relevant_information")
        self.graph.add_edge("other_relevant_information", "final_summary")
        self.graph.add_edge("final_summary", END)
        self.agent = self.graph.compile()
