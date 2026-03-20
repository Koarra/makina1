from langchain_core.prompts import PromptTemplate
from langgraph.graph import StateGraph, START, END
from langchain_openai import AzureChatOpenAI
from langchain_core.runnables.config import RunnableConfig
from pepnarrativeagent.pepstate import PEPAgentState
from pepnarrativeagent.const import (
    REVIEW_TYPE_NODE,
    BACKGROUND_NODE,
    CONNECTION_TYPE_NODE,
    EXPOSURE_DESCRIPTION_NODE,
    SOW_DESCRIPTION_NODE,
    AUM_DESCRIPTION_NODE,
    LOAN_DEBT_NODE,
    RISKFLAG_DETECTION_NODE,
    CONDITIONS_DESCRIPTION_NODE,
    FRONTEND_COMMENTS_NODE,
    OUTPUT_NODE,
    LLM_CONFIG,
    INPUT_AR_PROMPT,
    INPUT_PROFILE_PROMPT,
    EXTRACT_BACKGROUND_PROMPT,
    EXTRACT_REVIEW_TYPE_PROMPT,
    EXTRACT_CONNECTION_TYPE_PROMPT,
    EXPOSURE_DESCRIPTION_PROMPT,
    SOW_DESCRIPTION_PROMPT,
    AUM_DESCRIPTION_PROMPT,
    LOANS_DEBTS_PROMPT,
    RISKFLAGS_PROMPT,
    CONDITIONS_PROMPT,
    FRONTEND_COMMENTS_PROMPT,
)

import httpx
import math
from typing import Optional

class PEPAgent:
    def __init__(self, llm_config: dict = LLM_CONFIG):
        self.workflow = StateGraph(PEPAgentState)
        http_client = httpx.Client(verify=False, follow_redirects=True)
        self.llm = AzureChatOpenAI(
            **llm_config,
            http_client=http_client,
        )
        # Logprobs-enabled LLM for categorical (binary) decision nodes
        self.llm_with_logprobs = AzureChatOpenAI(
            **llm_config,
            http_client=http_client,
        ).bind(logprobs=True, top_logprobs=5)

        self.workflow.add_node(node=REVIEW_TYPE_NODE, action=self.extract_type_of_review)  # type: ignore
        self.workflow.add_node(BACKGROUND_NODE, self.extract_one_liner_background)  # type: ignore
        self.workflow.add_node(CONNECTION_TYPE_NODE, self.extract_connection_type)  # type: ignore
        self.workflow.add_node(EXPOSURE_DESCRIPTION_NODE, self.extract_exposure_description)  # type: ignore
        self.workflow.add_node(SOW_DESCRIPTION_NODE, self.extract_sow_description)  # type: ignore
        self.workflow.add_node(AUM_DESCRIPTION_NODE, self.extract_aum_description)  # type: ignore
        self.workflow.add_node(LOAN_DEBT_NODE, self.extract_loan_debt)  # type: ignore
        self.workflow.add_node(RISKFLAG_DETECTION_NODE, self.detect_riskflags)  # type: ignore
        self.workflow.add_node(CONDITIONS_DESCRIPTION_NODE, self.extract_conditions)  # type: ignore
        self.workflow.add_node(FRONTEND_COMMENTS_NODE, self.extract_frontend_comments)  # type: ignore
        self.workflow.add_node(OUTPUT_NODE, self.print_output)  # type: ignore

        self.workflow.add_edge(START, REVIEW_TYPE_NODE)
        self.workflow.add_edge(REVIEW_TYPE_NODE, BACKGROUND_NODE)
        self.workflow.add_edge(BACKGROUND_NODE, CONNECTION_TYPE_NODE)
        self.workflow.add_edge(CONNECTION_TYPE_NODE, EXPOSURE_DESCRIPTION_NODE)
        self.workflow.add_edge(EXPOSURE_DESCRIPTION_NODE, SOW_DESCRIPTION_NODE)
        self.workflow.add_edge(SOW_DESCRIPTION_NODE, AUM_DESCRIPTION_NODE)
        self.workflow.add_edge(AUM_DESCRIPTION_NODE, LOAN_DEBT_NODE)
        self.workflow.add_edge(LOAN_DEBT_NODE, RISKFLAG_DETECTION_NODE)
        self.workflow.add_edge(RISKFLAG_DETECTION_NODE, CONDITIONS_DESCRIPTION_NODE)
        self.workflow.add_edge(CONDITIONS_DESCRIPTION_NODE, FRONTEND_COMMENTS_NODE)
        self.workflow.add_edge(FRONTEND_COMMENTS_NODE, OUTPUT_NODE)
        self.workflow.add_edge(OUTPUT_NODE, END)

        self.agent = self.workflow.compile()

    def _parse_logprobs(self, response) -> tuple:
        """Return (confidence, alternatives) from a logprob response.

        confidence   – probability [0-1] of the first output token
        alternatives – {token: probability} for the top-5 alternatives at that position
        """
        logprobs_data = response.response_metadata.get("logprobs", {}).get("content", [])
        if not logprobs_data:
            return None, {}
        first = logprobs_data[0]
        confidence = math.exp(first["logprob"])
        alternatives = {
            alt["token"]: round(math.exp(alt["logprob"]), 4)
            for alt in first.get("top_logprobs", [])
        }
        return round(confidence, 4), alternatives

    def extract_type_of_review(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + EXTRACT_REVIEW_TYPE_PROMPT)
        response = (prompt_template | self.llm_with_logprobs).invoke(agent_state)
        confidence, alternatives = self._parse_logprobs(response)
        return {
            "review_status": response.content,
            "review_status_confidence": confidence,
            "review_status_alternatives": alternatives,
        }

    def extract_one_liner_background(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_PROFILE_PROMPT + EXTRACT_BACKGROUND_PROMPT)
        background = (prompt_template | self.llm).invoke(agent_state)
        return {"one_liner_background": background.content}

    def extract_connection_type(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + EXTRACT_CONNECTION_TYPE_PROMPT)
        response = (prompt_template | self.llm_with_logprobs).invoke(agent_state)
        confidence, alternatives = self._parse_logprobs(response)
        return {
            "connection_type": response.content,
            "connection_type_confidence": confidence,
            "connection_type_alternatives": alternatives,
        }

    def extract_exposure_description(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + EXPOSURE_DESCRIPTION_PROMPT)
        exposure_description = (prompt_template | self.llm).invoke(agent_state)
        return {"exposure_description": exposure_description.content}

    def extract_sow_description(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + SOW_DESCRIPTION_PROMPT)
        sow_description = (prompt_template | self.llm).invoke(agent_state)
        return {"sow_description": sow_description.content}

    def extract_aum_description(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + AUM_DESCRIPTION_PROMPT)
        aum_description = (prompt_template | self.llm).invoke(agent_state)
        return {"aum_description": aum_description.content}

    def extract_loan_debt(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + LOANS_DEBTS_PROMPT)
        loans_debts = (prompt_template | self.llm).invoke(agent_state)
        return {"loans_debts": loans_debts.content}

    def detect_riskflags(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + RISKFLAGS_PROMPT)
        riskflags = (prompt_template | self.llm).invoke(agent_state)
        return {"risk_flags": riskflags.content}

    def extract_conditions(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + CONDITIONS_PROMPT)
        conditions = (prompt_template | self.llm).invoke(agent_state)
        return {"conditions": conditions.content}

    def extract_frontend_comments(self, agent_state: dict) -> dict:
        prompt_template = PromptTemplate.from_template(INPUT_AR_PROMPT + FRONTEND_COMMENTS_PROMPT)
        response = (prompt_template | self.llm_with_logprobs).invoke(agent_state)
        confidence, alternatives = self._parse_logprobs(response)
        return {
            "frontend_comments": response.content,
            "frontend_comments_confidence": confidence,
            "frontend_comments_alternatives": alternatives,
        }

    def _confidence_bar(self, confidence: float, width: int = 20) -> str:
        filled = int(round(confidence * width))
        bar = "#" * filled + "-" * (width - filled)
        return f"[{bar}] {confidence * 100:.1f}%"

    def _flag(self, confidence: float, threshold: float = 0.80) -> str:
        return "⚠  LOW CONFIDENCE — recommend human review" if confidence < threshold else "✓  High confidence"

    def print_output(self, agent_state: dict) -> None:
        print("# Review Type:\n", agent_state["review_status"])
        print("# PEP Background:\n", agent_state["one_liner_background"])
        print("# Exposure Type:\n", agent_state["connection_type"])
        print("# Exposure Description:\n", agent_state["exposure_description"])
        print("# SoW Description:\n", agent_state["sow_description"])
        print("# AuM Description:\n", agent_state["aum_description"])
        print("# Loans and Debts:\n", agent_state["loans_debts"])
        print("# Riskflags:\n", agent_state["risk_flags"])
        print("# Conditions:\n", agent_state["conditions"])
        print("# Conclusion:\n", agent_state["frontend_comments"])

        # ── Logprob Confidence Report ──────────────────────────────────────────
        print("\n" + "=" * 60)
        print("  LOGPROB CONFIDENCE REPORT (categorical decisions)")
        print("=" * 60)

        categorical = [
            ("Review Type",    "review_status",     "review_status_confidence",     "review_status_alternatives"),
            ("Connection Type", "connection_type",   "connection_type_confidence",   "connection_type_alternatives"),
            ("Conclusion",     "frontend_comments", "frontend_comments_confidence", "frontend_comments_alternatives"),
        ]

        for label, val_key, conf_key, alt_key in categorical:
            decision    = agent_state.get(val_key, "N/A")
            confidence  = agent_state.get(conf_key)
            alternatives = agent_state.get(alt_key, {})

            print(f"\n  {label}: {decision!r}")
            if confidence is not None:
                print(f"    Confidence : {self._confidence_bar(confidence)}")
                print(f"    Status     : {self._flag(confidence)}")
                if alternatives:
                    sorted_alts = sorted(alternatives.items(), key=lambda x: -x[1])
                    print("    Top tokens :")
                    for token, prob in sorted_alts[:5]:
                        print(f"      {token!r:20s}  {prob * 100:5.1f}%")
            else:
                print("    Confidence : N/A")

        print("=" * 60)

    def invoke(self, input, config: RunnableConfig | None = None) -> dict:
        return self.agent.invoke(input, config)
