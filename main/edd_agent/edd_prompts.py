EDD_ASSESSMENT_PURPOSE_OF_BUSINESS_PROMPT = """
You are given a text that describes the purpose for opening a bank relationship.
Your task is to summarize it.
Return strictly the summary, nothing else as done in the following example.
Example:
Other - Details: Client transferred money from his SPV under a UBS trust to his personal account he holds locally in Jordan for personal spending (during the Eid holidays) The personal account was opened when the trust was set up by the client and the structure as 3rd party transactions are not allowed by the trustees. The SPV is under a trust managed by trustees and the client personal account are approved
Payment transactions with sensitive countries - Details: Personal account for the client is to send and receive transfers with third party transactions. Transfers has been done to client own account with XXX Bank, in Jordan for personal expenses and i...
Payment transactions - Details: Incoming Funds : We had received funds ($1.8M) on 05.02.2019 to client's account from ABC L... the Smith family. The shares of ABC were bought by Robert Smith (one of the 7 siblings) and thereafter the distribution was... Smith and John Smith. Our client, John Smith received $ 1,870,000 to his UBS account. Outgoing Funds : Client had transferred under trust structure and therefore can only receive payments from client himself as he is the settlor. Also the PIC can only...
Other - Details: Account is being re-classified as SIAP due to the companies subsidiaries businesses involved in exploration...
Other - Details: Review 2024 : No inflow/outflow transactions in 2023 No inflows/outflows expected in 2024.
Other - Details: Initial Funding and purpose : * The initial funding of $3M was supposed to come from the client personal acc... UBS ($1.8M) * The account will be used for the following: o To receive distributions from investments o For personal expenses...
Investing / Securities trading - Details: Account will be used mainly for wealth management/wealth planning

Example summary:
Purpose of business relationship:
Payment transactions: Inflows from the family's investment office ABC Limited.
Payment transactions with sensitive countries (Jordan); Transactions with the trust account and the client's own PIC for investments expected.
Other: The personal account was opened when the trust was set up by the client and the trustees needed settlor to have a personal account. 3rd party transactions are not allowed by the trustees.
Investing / Securities trading: the account will be used for wealth management and wealth planning.

As for the example, summarize the below purpose of business relationship text:
{purpose_of_business_txt}
"""

ACTIVITIES_PROMPT = """
Extract {entity} informations related to his job.
Text: "{text_to_provide}"
Respond in the following JSON format:
[
    "activities":[
        {{
            "year_joined": value,
            "year_left": value,
            "job_position": value,
            "company": value,
            "salary": value,
            "industry_field": value
        }}
    ]
]
"""

BANKABLE_ASSETS_PROMPT = """
Provided client notes:
{remarks_on_total_assets}

Based only on the above client notes, you are in charge of extracting the distinct bankable assets of the client.

For each bankable asset, we need information about the asset itself, amount, asset type, bank, and location.

Respond in the following JSON format:
[
    "assets": [
        {{
            "asset_description": <brief asset description>,
            "amount": <amount>,
            "currency": <currency>,
            "type": <bankable asset type>,
            "bank": <bank name>,
            "location": <location>
        }}
    ]
]
"""

REAL_ESTATE_PROMPT = """
Provided client notes:
{remarks_on_total_assets}

Based only on the above client notes, you are in charge of extracting the distinct real estate assets of the client.

For each real estate asset, we need information about the asset itself, value, asset type, and location.

Respond in the following JSON format:
[
    "assets":[
        {{
            "asset_description": <brief asset description>,
            "value": <value>,
            "currency": <currency>,
            "type": <bankable asset type>,
            "location": <location>
        }}
    ]
]
"""

PRIVATE_EQUITY_PROMPT = """
Provided client notes:
{remarks_on_total_assets}

Based only on the above client notes, you are in charge of extracting the distinct private equity assets of the client.

For each private equity asset, we need information about the asset itself, value, company name, and percentage ownership.

Respond in the following JSON format:
[
    "assets": [
        {{
            "asset_description": <asset description>,
            "value": <value>,
            "currency": <currency>,
            "company_name": <company name>,
            "percentage_ownership": <percentage ownership>
        }}
    ]
]
"""

OTHER_ASSETS_PROMPT = """
Provided client notes:
{remarks_on_total_assets}

Based only on the above client notes, you are in charge of extracting any other assets that do not fall into the category of bankable assets, real estate or private equity.

For each of these other assets, we need information about the asset itself and its value.

Respond in the following JSON format:
[
    "assets": [
        {{
            "asset_description": <asset description>,
            "value": <value>,
            "currency": <currency>
        }}
    ]
]
"""

SOW_SUMMARY_PROMPT = """
Provided client notes:
{client_history}

Based only on the above client notes, you are in charge of extracting distinct sources of wealth and their corroboration status. Once this is done, please provide:

1. A brief executive summary indicating the different wealth contributing elements (e.g. salaries, dividends, investment return, sale of business), focusing on the:
    - main income generating employments / shareholdings / investments
    - the relevant years and amounts with the engaged business activities / industries.
For company ownership, indicate key financial information.
In case of inheritance/donation indicate the name of the originator, relationship with the originator, date and amount of assets received, and one or two sentences about the originator.
Please keep this short and concise.

2. State in a sentence whether or not the source of wealth is considered plausible by the client advisor.

Respond in the following JSON format:
{{
    "sow_description": <executive summary of distinct sources of wealth>,
    "sow_plausibility": value
}}
"""

FINAL_SUMMARY_PROMPT = """
Provided client notes:
{client_history}

Based only on the above client notes, you are in charge of analyzing them and suggesting if we can proceed and approve the client or if we need to reject. If a client is missing important KYC documents or wealth corroboration and/or is missing important KYC documents, these should be cause for concern. Please also classify the request type into A, B or C.

Pease answer in below json format by providing request category, decision as well as the justification.
{{
    "request_type": <request type: A, B, or C>,
    "decision": <accept or reject>,
    "justification": <brief justification for decision>
}}
"""

ANTICIPATED_TRX_PROMPT = """
Provided client notes:
{client_history}

Based only on the above notes, extract the anticipated transaction pattern for this new client.

Your response should be concise - only describe the anticipated transaction pattern present in the text, do not infer anything on your own.

If you use non-English terms in your answer (e.g., file names, job titles, etc.), provide both the original term(s) and their English translation.

Respond in the following JSON format:
{{
    "anticipated_pattern": <executive summary of the transaction pattern from the client notes>
}}
"""
