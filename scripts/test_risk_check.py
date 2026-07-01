#!/usr/bin/env python3
"""
test_risk_check.py — proves the deterministic gate actually gates.

risk_check.py is the one component that must not be talked around by any prompt,
so it gets tested directly: each case writes a proposal + a state file, runs
risk_check.py as a subprocess, and asserts the PASS/FAIL verdict and exit code.

Run:  python3 scripts/test_risk_check.py     (exits 0 if all cases pass)
"""
import json, os, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RISK = os.path.join(ROOT, "scripts", "risk_check.py")

BASE_STATE = {
    "account_value": 200.0, "peak_value": 200.0, "day_start_value": 200.0,
    "moonshot_sleeve_value": 40.0, "logged_trades": 60, "positions": [],
}


def run_case(name, proposal, state=None, settlement=None):
    """Run one proposal through risk_check.py in an isolated temp root.

    Returns (exit_code, stdout). We copy the real script into a temp tree so its
    os.path-relative reads of state/positions.json and state/settlement.json hit
    our fixtures instead of the repo's live book.
    """
    st = {**BASE_STATE, **(state or {})}
    with tempfile.TemporaryDirectory() as d:
        os.makedirs(os.path.join(d, "scripts"))
        os.makedirs(os.path.join(d, "state", "pending"))
        # copy the script under test
        with open(RISK) as f:
            open(os.path.join(d, "scripts", "risk_check.py"), "w").write(f.read())
        json.dump(st, open(os.path.join(d, "state", "positions.json"), "w"))
        if settlement is not None:
            json.dump(settlement, open(os.path.join(d, "state", "settlement.json"), "w"))
        ppath = os.path.join(d, "state", "pending", "t.json")
        json.dump(proposal, open(ppath, "w"))
        r = subprocess.run(
            [sys.executable, os.path.join(d, "scripts", "risk_check.py"), ppath],
            capture_output=True, text=True,
        )
        return r.returncode, (r.stdout + r.stderr)


def buy(**over):
    p = {"id": "t", "symbol": "XYZ", "sleeve": "core", "side": "buy",
         "notional": 50.0, "entry": 100.0, "stop": 97.0, "target": 130.0,
         "thesis": "test", "max_loss": 1.50}
    p.update(over)
    return p


CASES = []  # (name, expect_pass: bool, exit_code, proposal, state, settlement)

# --- Passing cases ---
CASES.append(("core buy within 3% band", True, 0, buy(), None, None))
CASES.append(("moonshot within 1/3 sleeve", True, 0,
              buy(sleeve="moonshot", notional=13.0, entry=74.9, stop=60.0, target=95.0),
              None, None))
CASES.append(("plain sell (no settlement file)", True, 0,
              {"id": "t", "symbol": "XYZ", "side": "sell", "sleeve": "core",
               "notional": 50.0, "entry": 100.0, "thesis": "exit"}, None, None))

# --- Failing cases: the caps must bite ---
CASES.append(("risk over 7% hard cap", False, 1,
              # notional 100 @ (100->80) = $20 max loss = 10% of a $200 account
              buy(notional=100.0, stop=80.0),
              None, None))
CASES.append(("stop above entry (long)", False, 1, buy(stop=105.0), None, None))
CASES.append(("notional exceeds account value", False, 1,
              buy(notional=250.0, stop=99.5), None, None))
CASES.append(("moonshot exceeds 1/3 of sleeve", False, 1,
              buy(sleeve="moonshot", notional=20.0, entry=74.9, stop=70.0), None, None))
CASES.append(("missing stop on a buy", False, 1,
              {"id": "t", "symbol": "XYZ", "sleeve": "core", "side": "buy",
               "notional": 50.0, "entry": 100.0, "thesis": "no stop"}, None, None))
CASES.append(("peak drawdown halt blocks new buys", False, 1,
              buy(), {"account_value": 100.0, "peak_value": 200.0}, None))
CASES.append(("day-loss halt blocks new buys", False, 1,
              buy(), {"account_value": 150.0, "day_start_value": 200.0}, None))
CASES.append(("sell of unsettled symbol blocked", False, 1,
              {"id": "t", "symbol": "XYZ", "side": "sell", "sleeve": "core",
               "notional": 50.0, "entry": 100.0, "thesis": "exit"},
              None, {"unsettled_symbols": ["XYZ"]}))

# --- Safety invariant: circuit breakers must NOT trap you in a losing book ---
CASES.append(("sell allowed even in a 40%+ drawdown (de-risking)", True, 0,
              {"id": "t", "symbol": "XYZ", "side": "sell", "sleeve": "core",
               "notional": 50.0, "entry": 100.0, "thesis": "cut risk"},
              {"account_value": 100.0, "peak_value": 200.0}, None))


def main():
    failures = []
    for name, expect_pass, want_code, prop, state, settle in CASES:
        code, out = run_case(name, prop, state, settle)
        got_pass = code == 0
        ok = (got_pass == expect_pass) and (code == want_code)
        verdict = "PASS " if got_pass else "FAIL "
        mark = "ok  " if ok else "XX  "
        print(f"  {mark}[{verdict}exit={code}] {name}")
        if not ok:
            failures.append((name, want_code, code, out.strip()))
    print()
    if failures:
        print(f"{len(failures)} case(s) did not match expectation:")
        for name, want, got, out in failures:
            print(f"  - {name}: wanted exit {want}, got {got}\n      {out}")
        sys.exit(1)
    print(f"All {len(CASES)} risk-gate cases behaved as expected.")


if __name__ == "__main__":
    main()
