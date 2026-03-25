COMPARE_TRANSACTIONS_PURPOSE_OF_BR_PROMPT = """
Verify if details provided in {kyc_purpose_of_br} justify the transaction value present in {kyc_transactions}.
Ignore the case where there are no KYC transactions.
"""

ORIGIN_OF_ASSET_PROMPT = """
Based only on the asset origins of the client provided in {origin_of_assets}, check whether the text includes all of the following elements:
1. The history of this asset (background or timeline of how it evolved).
2. Type of the asset (e.g., employment, inheritance, investment, etc.)
3. The initial source of the asset (the concrete origin, e.g., which company, which person, which purchase, when, etc.).
4. The annual income of the main asset owner.
5. The names of co-owners, if there are any.
"""

# <Explain clearly why the text is complete, or to list which required elements are missing.>


SUMMARIZE_TRANSACTIONS_PROMPT = """
Based on the transactions description in {kyc_transactions}, please check if any transactions
are provided. If transactions are found, list them all by recording for each: amount, date,
currency.
"""

TOTAL_ASSET_PROMPT = """
Evaluate the total value of {kyc_origin_of_assets}.
"""

TOTAL_ASSET_COMPOSITION_PROMPT = """
Evaluate the total assets value in {kyc_total_remarks}.
"""

REMARKS_COMP_TOTAL_ASSET_PROMPT = """
Verify if the details provided in {kyc_total_remarks} justify the assets present in {kyc_total_assets}.
Details such as below should be mentioned if applicable:
    - type and location of real estate
    - bankable assets with bank information
    - estimated value of yacht
    - estimated value of operating group and BCP's share % in the group)

Please keep it concise and focus on assets the client has and not on what they don't have.
The objective is to understand if we have enough information for total assets remarks.
"""

FAMILY_MEMBERS_PROMPT = """
Extract all the family members mentioned in {client_notes}.
For each member record the following attributes:
    - name: the person's name
    - relation: the relation type to the client:  parent, sibling, child, spouse, other
    - source_of_wealth_relevant: whether this person contributes or has contributed to the client's wealth, e.g. through a donation, inheritance, etc.
    - politically_exposed: whether this person is marked as PEP (politically exposed person) in the notes
"""

CROSS_CHECK_PROMPT = """
Check if the person with name {name} is mentioned in the snippet {family_history}.
"""

CONTRADICTION_CHECKS_PROMPT = """
Check if there is any contradiction between details in {text1} and details in the following dictionary {dic_others}.
Provide a reasoning, a confidence level and decide if there is a contradiction or not.
"""
