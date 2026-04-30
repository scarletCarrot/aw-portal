"""
Calculation engine for SACS and TCC reports.

Every rule in this file is sourced verbatim from the discovery call transcript.
Tests in test_calc.py exercise each rule. If a rule changes, change it HERE
and the templates pick it up automatically.
"""

from typing import List, Optional


# ---------------------------------------------------------------------------
# SACS — Simple Automated Cash Flow
# ---------------------------------------------------------------------------

def sacs_excess(monthly_inflow: float, monthly_outflow: float) -> float:
    """
    Excess = Inflow - Outflow.

    Transcript (Rebecca, ~10:00):
        "the blue arrow going down is simply the excess between
         the inflow and outflow"
    """
    return monthly_inflow - monthly_outflow


def sacs_private_reserve_target(
    monthly_expenses: float,
    insurance_deductibles: List[float],
    months_buffer: int = 6,
) -> float:
    """
    Private Reserve Target = (6 x monthly expenses) + sum(deductibles).

    Transcript (Rebecca, ~09:30):
        "6 months of their normal expenses based off that same worksheet
         we used above and all of their insurance deductibles ... we add
         all of that together with [plus] their monthly expense and
         then that's their target for their savings"
    """
    return (months_buffer * monthly_expenses) + sum(insurance_deductibles)


# ---------------------------------------------------------------------------
# TCC — Total Client Chart
# ---------------------------------------------------------------------------

def tcc_retirement_total(balances: List[Optional[float]]) -> float:
    """
    Sum of one spouse's retirement account balances.

    Transcript (Rebecca, ~21:30):
        "this gray box at the top that says client one retirement only
         that is the total of these two accounts for the client"
    """
    return sum(b for b in balances if b is not None)


def tcc_non_retirement_total(balances: List[Optional[float]]) -> float:
    """
    Sum of all non-retirement (joint) accounts. EXCLUDES the trust.

    Transcript (Rebecca, ~24:28):
        "when we go to add these up we do not add the trust in"
        "the non retirement total ... this is only the accounts, not the trust"
    """
    return sum(b for b in balances if b is not None)


def tcc_grand_total_net_worth(
    client_1_retirement: float,
    client_2_retirement: float,
    non_retirement: float,
    trust: float,
) -> float:
    """
    Net Worth = C1 Retirement + C2 Retirement + Non-Retirement + Trust.

    Transcript (Rebecca, ~25:30):
        "we add the three boxes plus the trust and that is the grand total
         of their net worth ... four numbers going to that"
    """
    return client_1_retirement + client_2_retirement + non_retirement + trust


def tcc_liabilities_total(balances: List[Optional[float]]) -> float:
    """
    Sum of all liabilities. Displayed SEPARATELY from net worth.

    Transcript (Rebecca, ~26:15):
        "we do not subtract liabilities from their net worth
         they're just a separate box"
    """
    return sum(b for b in balances if b is not None)


# ---------------------------------------------------------------------------
# Convenience: compute everything for one client at once.
# ---------------------------------------------------------------------------

def compute_report(client: dict, balances: dict) -> dict:
    """
    Take the static `client` config and the `balances` entered for this quarter,
    return a dict of all derived numbers ready for the templates.
    """
    # Fill in dynamic balances onto the client structure (non-mutating)
    c1 = client["client_1"]
    c2 = client["client_2"]
    non_ret = client["non_retirement_accounts"]
    liabs = client["liabilities"]

    c1_ret_balances = balances["c1_ret_balances"]
    c2_ret_balances = balances["c2_ret_balances"]
    non_ret_balances = balances["non_ret_balances"]
    liability_balances = balances["liability_balances"]
    trust_value = balances["trust_zillow"] or 0

    # SACS numbers
    monthly_inflow = c1["monthly_salary"] + c2["monthly_salary"]
    monthly_outflow = client["sacs_budget"]["monthly_outflow"]
    deductibles = list(client["sacs_budget"]["insurance_deductibles"].values())

    # Find the private reserve account balance (last entry in non_ret with is_sacs=='private_reserve')
    private_reserve_balance = next(
        (bal for acct, bal in zip(non_ret, non_ret_balances)
         if acct.get("is_sacs") == "private_reserve"),
        0
    )
    inflow_balance = next(
        (bal for acct, bal in zip(non_ret, non_ret_balances)
         if acct.get("is_sacs") == "inflow"),
        0
    )
    outflow_balance = next(
        (bal for acct, bal in zip(non_ret, non_ret_balances)
         if acct.get("is_sacs") == "outflow"),
        0
    )

    sacs = {
        "monthly_inflow": monthly_inflow,
        "monthly_outflow": monthly_outflow,
        "monthly_excess": sacs_excess(monthly_inflow, monthly_outflow),
        "floor": client["sacs_budget"]["floor"],
        "private_reserve_target": sacs_private_reserve_target(
            monthly_expenses=monthly_outflow,
            insurance_deductibles=deductibles,
        ),
        "private_reserve_balance": private_reserve_balance or 0,
        "inflow_balance": inflow_balance or 0,
        "outflow_balance": outflow_balance or 0,
    }

    # TCC numbers
    c1_total = tcc_retirement_total(c1_ret_balances)
    c2_total = tcc_retirement_total(c2_ret_balances)

    # Non-retirement excludes any account flagged as a SACS account?
    # Per Rebecca: "in most of our client situations usually their bank accounts
    # are on the bottom right ... these are joint accounts ... these are the accounts
    # that are on the SACS — the inflow, outflow, and private reserve. So those are
    # still there." → SACS accounts ARE counted in non-retirement total.
    non_ret_total = tcc_non_retirement_total(non_ret_balances)
    liabilities_total = tcc_liabilities_total(liability_balances)
    grand_total = tcc_grand_total_net_worth(c1_total, c2_total, non_ret_total, trust_value)

    tcc = {
        "client_1_retirement_total": c1_total,
        "client_2_retirement_total": c2_total,
        "non_retirement_total": non_ret_total,
        "trust_value": trust_value,
        "grand_total_net_worth": grand_total,
        "liabilities_total": liabilities_total,
    }

    return {"sacs": sacs, "tcc": tcc}
