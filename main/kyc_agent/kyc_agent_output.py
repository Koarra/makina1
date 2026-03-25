from langgraph.graph import END, StateGraph

from main.kyc_agent.common import build_llm
from main.kyc_agent.kyc_checks_nodes import (
    node_section3_purpose_of_br, node_section4_origin_of_assets,
    node_section6_total_assets, node_section7_remarks_total_assets,
    node_section8_activity, node_section10_family_situation,
    node_section11_1_consistency_checks_pep_asm,
    node_section11_2_consistency_checks_within_kyc,
    node_section13_scap_flag_checks, node_section14_siap_checks)
from main.kyc_agent.kyc_state import KycState


class KycAgentOutput:

    def __init__(self):
        self.llm = build_llm()

        self.graph = StateGraph(KycState)
        self.graph.add_node(
            "section3_purpose_of_br",
            lambda s: node_section3_purpose_of_br(s, self.llm),
        )
        self.graph.add_node(
            "section4_origin_of_assets",
            lambda s: node_section4_origin_of_assets(s, self.llm),
        )
        self.graph.add_node(
            "section6_total_assets",
            lambda s: node_section6_total_assets(s, self.llm)
        )
        self.graph.add_node(
            "section7_remarks_total_assets",
            lambda s: node_section7_remarks_total_assets(s, self.llm),
        )
        self.graph.add_node(
            "section8_activity",
            lambda s: node_section8_activity(s, self.llm)
        )
        self.graph.add_node(
            "section10_family_situation",
            lambda s: node_section10_family_situation(s, self.llm),
        )
        self.graph.add_node(
            "section11_1_consistency_checks_pep_asm",
            node_section11_1_consistency_checks_pep_asm,
        )
        self.graph.add_node(
            "section11_2_consistency_checks_within_kyc",
            lambda s: node_section11_2_consistency_checks_within_kyc(s, self.llm),
        )
        self.graph.add_node(
            "section13_scap_flag_checks", node_section13_scap_flag_checks
        )
        self.graph.add_node("section14_siap_checks", node_section14_siap_checks)

        # execution order
        self.graph.set_entry_point("section3_purpose_of_br")
        self.graph.add_edge("section3_purpose_of_br", "section4_origin_of_assets")
        self.graph.add_edge("section4_origin_of_assets", "section6_total_assets")
        self.graph.add_edge("section6_total_assets", "section7_remarks_total_assets")
        self.graph.add_edge("section7_remarks_total_assets", "section8_activity")
        self.graph.add_edge("section8_activity", "section10_family_situation")
        self.graph.add_edge("section10_family_situation", "section11_1_consistency_checks_pep_asm")
        self.graph.add_edge("section11_1_consistency_checks_pep_asm", "section11_2_consistency_checks_within_kyc")
        self.graph.add_edge("section11_2_consistency_checks_within_kyc", "section13_scap_flag_checks")
        self.graph.add_edge("section13_scap_flag_checks", "section14_siap_checks")
        self.graph.add_edge("section14_siap_checks", END)

        self.agent = self.graph.compile()
