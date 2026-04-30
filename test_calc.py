"""
Quick assertion tests for the calculation engine.
Run with:  python test_calc.py
"""

from calc import (
    sacs_excess,
    sacs_private_reserve_target,
    tcc_retirement_total,
    tcc_non_retirement_total,
    tcc_grand_total_net_worth,
    tcc_liabilities_total,
    compute_report,
)
from data import get_sample_client, DEMO_BALANCES


def test_sacs_excess():
    # Rebecca's own example: $15k inflow, $11k outflow → $4k excess.
    assert sacs_excess(15000, 11000) == 4000
    assert sacs_excess(0, 0) == 0
    assert sacs_excess(15000, 18000) == -3000  # overspend month
    print("ok  sacs_excess")


def test_private_reserve_target():
    # 6 x $11,000 = $66,000 + $1,000 + $2,000 + $1,000 = $70,000
    assert sacs_private_reserve_target(11000, [1000, 2000, 1000]) == 70000
    # No deductibles
    assert sacs_private_reserve_target(10000, []) == 60000
    print("ok  private_reserve_target")


def test_retirement_total():
    assert tcc_retirement_total([11000, 15000]) == 26000
    assert tcc_retirement_total([11000, None, 15000]) == 26000  # tolerate Nones
    assert tcc_retirement_total([]) == 0
    print("ok  retirement_total")


def test_non_retirement_excludes_trust():
    # The function itself just sums what you give it.
    # The CRITICAL invariant is that callers must never pass the trust into it.
    accounts_only = [50000, 18000]   # brokerage + checking
    assert tcc_non_retirement_total(accounts_only) == 68000
    print("ok  non_retirement_total (caller responsible for excluding trust)")


def test_grand_total_includes_trust():
    # C1 ret 26k + C2 ret 151k + non-ret 68k + trust 450k = 695k
    assert tcc_grand_total_net_worth(26000, 151000, 68000, 450000) == 695000
    print("ok  grand_total_net_worth (trust IS included)")


def test_liabilities_separate():
    # Liabilities sum but are NEVER subtracted from net worth.
    # We model that by exposing the sum independently from grand_total.
    nw = tcc_grand_total_net_worth(26000, 151000, 68000, 450000)
    liab = tcc_liabilities_total([200000, 14000])
    assert nw == 695000
    assert liab == 214000
    # Net worth must NOT include liabilities
    assert nw != (nw - liab)
    print("ok  liabilities are separate from net worth")


def test_full_report_demo():
    client = get_sample_client()
    report = compute_report(client, DEMO_BALANCES)

    sacs = report["sacs"]
    tcc = report["tcc"]

    # Sanity-check SACS
    assert sacs["monthly_inflow"] == 15000
    assert sacs["monthly_outflow"] == 11000
    assert sacs["monthly_excess"] == 4000
    # Target = 6 * 11000 + (1000 + 2000 + 1000) = 70,000
    assert sacs["private_reserve_target"] == 70000
    assert sacs["floor"] == 1000

    # Sanity-check TCC
    assert tcc["client_1_retirement_total"] == round(11162.47 + 15240.18, 2)
    assert tcc["client_2_retirement_total"] == round(88500.00 + 22100.00 + 41250.00, 2)
    assert tcc["trust_value"] == 452000.00
    expected_grand = (
        tcc["client_1_retirement_total"]
        + tcc["client_2_retirement_total"]
        + tcc["non_retirement_total"]
        + tcc["trust_value"]
    )
    assert tcc["grand_total_net_worth"] == expected_grand

    # Liabilities NOT subtracted
    assert tcc["liabilities_total"] == 218400.00 + 14250.00
    assert tcc["grand_total_net_worth"] != (expected_grand - tcc["liabilities_total"])

    print("ok  full demo report")


if __name__ == "__main__":
    test_sacs_excess()
    test_private_reserve_target()
    test_retirement_total()
    test_non_retirement_excludes_trust()
    test_grand_total_includes_trust()
    test_liabilities_separate()
    test_full_report_demo()
    print("\nAll calculation tests passed.")
