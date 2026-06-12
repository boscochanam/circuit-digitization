"""CLI: synthesize authored circuits, run the real join + SPICE under increasing
detector-style error, and print join + sim scores against ground truth.

    uv run python -m wire_detection.synthgt                 # full suite
    uv run python -m wire_detection.synthgt -c ring6_r -s 16
    uv run python -m wire_detection.synthgt --json > out.json

SPICE needs ngspice (set NGSPICE_PATH). Without it, join scores still run.
"""
from __future__ import annotations

import argparse
import json
import sys

from wire_detection.core.join_strategies import list_strategies
from wire_detection.synthgt.circuits import CATALOG, CATALOG_BY_NAME
from wire_detection.synthgt.evaluate import (
    DEFAULT_STRATEGY,
    compare_strategies,
    run_suite,
)


def _fmt_row(r: dict) -> str:
    p = r["params"]
    params = f"j{p[0]:g}/c{p[1]:g}/d{p[2]:g}/w{p[3]:g}/a{p[4]:g}/d{p[5]:.0f}"
    sim = "  n/a" if r["sim_ok_rate"] is None else f"{r['sim_ok_rate'] * 100:4.0f}%"
    inj = "  -" if r["mean_injected"] is None else f"{r['mean_injected']:4.1f}"
    return (f"   L{r['severity']}  {params:26}  "
            f"F1 {r['f1']:.2f}  rec {r['recall']:.2f}  prec {r['precision']:.2f}   "
            f"sim_ok {sim}   inj {inj}")


def _print_report(results: list[dict]) -> None:
    print("\nSynthetic ground-truth evaluation - real join + SPICE vs authored netlist")
    print(f"strategy: {results[0]['strategy']}")
    print("=" * 78)
    for res in results:
        clean = res["rows"][0]
        flag = "" if clean["f1"] >= 0.999 else "  <-- CLEAN JOIN IMPERFECT (layout bug)"
        if res.get("expect_match") is False:
            flag += "  <-- ORACLE != AUTHORED EXPECTATION (spec bug)"
        gt = res["gt_mA"]
        mA = f"{gt:.3f}mA" if gt is not None else "n/a"
        exp = f"{res['expect_mA']:.3f}mA" if res["expect_mA"] is not None else "n/a"
        print(f"\n{res['name']}  ({res['components']} comps / {res['nets']} nets / "
              f"{res['gt_pairs']} gt-pairs)   I_src clean={mA} expect={exp}{flag}")
        if res["note"]:
            print(f"   {res['note']}")
        print("   level  error(jit/cut/drop/wrongpin/anchor)    join                  spice")
        for r in res["rows"]:
            print(_fmt_row(r))

    print("\n" + "-" * 78)
    print("legend: F1/rec/prec = component-connectivity vs ground truth (rec down =")
    print("        fragmentation, prec down = shorts/over-merge). sim_ok = % seeds")
    print("        where EVERY source current matches the clean oracle with no")
    print("        injected test source. inj = mean fake sources injected.")
    print("        NB: a single cross-short doesn't change DC currents (no return")
    print("        path), so over-merge shows in precision, not in sim_ok.")
    print("\nCAVEAT: the error model (jitter/cut/drop/wrong-pin) is a PLACEHOLDER,")
    print("not yet calibrated to the real detector. Join scores are a robustness/")
    print("regression signal, not a prediction of real-image performance. See")
    print("docs/synthetic-eval-plan.md. The SPICE half is sound (we control the netlist).")
    if not results[0]["spice_on"]:
        print("\n[ngspice not found - SPICE columns skipped. Set NGSPICE_PATH.]")


def _print_leaderboard(rows: list[dict], n_circuits: int, seeds: int) -> None:
    print(f"\nJoin-strategy leaderboard (join only, {n_circuits} circuits x {seeds} "
          f"seeds, ground-truth F1)")
    print("=" * 78)
    print(f"{'strategy':22} {'clean':>6} {'L1':>6} {'L2':>6} {'L3':>6} {'L4':>6}   "
          f"{'mean(err)':>9}")
    print("-" * 78)
    for r in rows:
        by = r["by_severity"]
        flag = "" if r["clean"] >= 0.999 else "  <-- fails clean"
        cells = "  ".join(f"{v:.2f}" for v in by)
        print(f"{r['strategy']:22} {cells}   {r['mean_err_f1']:>7.3f}{flag}")
    print("-" * 78)
    print("ranked by mean F1 over error levels L1-L4 (higher = more robust to the")
    print("placeholder error). 'fails clean' = can't recover an easy case = broken.")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wire_detection.synthgt")
    ap.add_argument("-c", "--circuit", action="append",
                    help="restrict to named circuit(s); repeatable")
    ap.add_argument("-s", "--seeds", type=int, default=8,
                    help="error seeds per non-clean level (default 8)")
    ap.add_argument("--strategy", default=DEFAULT_STRATEGY,
                    help=f"join strategy to evaluate (default {DEFAULT_STRATEGY})")
    ap.add_argument("--compare", action="store_true",
                    help="rank EVERY join strategy on ground truth (join-only leaderboard)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args(argv)

    known = {s["name"] for s in list_strategies()}
    if args.strategy not in known:
        ap.error(f"unknown strategy '{args.strategy}'. available: {', '.join(sorted(known))}")

    specs = CATALOG
    if args.circuit:
        unknown = [c for c in args.circuit if c not in CATALOG_BY_NAME]
        if unknown:
            ap.error(f"unknown circuit(s): {', '.join(unknown)}. "
                     f"available: {', '.join(CATALOG_BY_NAME)}")
        specs = [CATALOG_BY_NAME[c] for c in args.circuit]

    if args.compare:
        all_strats = [s["name"] for s in list_strategies()]
        rows = compare_strategies(all_strats, specs, seeds=args.seeds)
        if args.json:
            json.dump(rows, sys.stdout, indent=2)
            print()
        else:
            _print_leaderboard(rows, len(specs), args.seeds)
        return 0

    results = run_suite(specs, seeds=args.seeds, strategy=args.strategy)
    if args.json:
        json.dump(results, sys.stdout, indent=2)
        print()
    else:
        _print_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
