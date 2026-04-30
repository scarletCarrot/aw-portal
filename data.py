"""
Hardcoded sample client.

For V1 we keep ONE client in memory. The form pre-populates from STATIC fields
(things that change yearly at most: salary, expense budget, account types,
trust property, liabilities) and asks for DYNAMIC fields (current balances).

Numbers chosen to match the PRD's example so the generated PDFs are easy to
verify against the screenshots in karen-test/.
"""

# --- STATIC (entered once during onboarding, rarely changes) -----------------
SAMPLE_CLIENT = {
    "client_1": {
        "name": "Andrew Example",
        "dob": "1978-04-12",
        "ssn_last4": "1234",
        # Monthly take-home pay deposited into the inflow account.
        # Transcript: "$15,000/month after taxes" (PRD Inflow definition)
        "monthly_salary": 15000,
        # Retirement accounts (top half of TCC). Type, last-4, balance entered quarterly.
        "retirement_accounts": [
            {"type": "IRA", "last4": "8821", "balance": None},
            {"type": "Roth IRA", "last4": "4407", "balance": None, "cash_balance": None},
        ],
    },
    "client_2": {
        "name": "Rebecca Example",
        "dob": "1981-09-03",
        "ssn_last4": "5678",
        "monthly_salary": 0,  # spouse not earning in this example
        "retirement_accounts": [
            {"type": "401K", "last4": "9921", "balance": None},
            {"type": "Roth IRA", "last4": "3310", "balance": None},
            {"type": "Pension", "last4": "0044", "balance": None},
        ],
    },
    # Joint / non-retirement accounts (bottom half of TCC).
    "non_retirement_accounts": [
        {"type": "Schwab Brokerage", "last4": "7712", "balance": None, "cash_balance": None},
        # The 3 SACS accounts also appear here.
        {"type": "Inflow (Pinnacle Checking)", "last4": "1010", "balance": None, "is_sacs": "inflow"},
        {"type": "Outflow (Pinnacle Checking)", "last4": "2020", "balance": None, "is_sacs": "outflow"},
        {"type": "Private Reserve (HYSA)", "last4": "3030", "balance": None, "is_sacs": "private_reserve"},
    ],
    # Trust — usually funded by primary residence, valued via Zillow Zestimate.
    "trust": {
        "property_address": "123 Maple Lane, Atlanta, GA",
        "zillow_value": None,  # entered quarterly
    },
    # Liabilities — displayed separately, NOT subtracted from net worth.
    "liabilities": [
        {"type": "Mortgage", "interest_rate": 4.25, "balance": None},
        {"type": "Auto Loan", "interest_rate": 6.50, "balance": None},
    ],
    # SACS budget assumptions
    "sacs_budget": {
        # Agreed monthly outflow (rounded UP from actual ~$10,500 per Rebecca).
        "monthly_outflow": 11000,
        # Floor — never changes per Rebecca: "$1,000 buffer in their accounts".
        "floor": 1000,
        # Insurance deductibles, summed for private reserve target.
        "insurance_deductibles": {
            "auto": 1000,
            "home": 2000,
            "health": 1000,
        },
    },
}

# --- DEFAULTS for the form (so the demo "just works" on first load) ---------
# These would normally come from "last quarter's report" once history exists.
DEMO_BALANCES = {
    "c1_ret_balances": [11162.47, 15240.18],          # IRA, Roth IRA
    "c1_ret_cash":     [None, 316.00],                # cash within Roth IRA
    "c2_ret_balances": [88500.00, 22100.00, 41250.00],
    "c2_ret_cash":     [None, None, None],
    "non_ret_balances": [54300.00, 18420.00, 12150.00, 47800.00],  # brokerage, inflow, outflow, private reserve
    "non_ret_cash":     [1200.00, None, None, None],
    "trust_zillow":     452000.00,
    "liability_balances": [218400.00, 14250.00],
}


def get_sample_client():
    """Return a deep-ish copy so callers can mutate without poisoning the module."""
    import copy
    return copy.deepcopy(SAMPLE_CLIENT)
