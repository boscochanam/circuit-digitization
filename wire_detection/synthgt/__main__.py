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

from wire_detection.synthgt.circuits import CATALOG, CATALOG_BY_NAME
from wire_detection.synthgt.evaluate import run_suite


def _fmt_row(r: dict) -> str:
    s, c, d = r["params"]
    params = f"j{s:g}/c{c:g}/d{d:g}"
    sim = "  n/a" if r["sim_ok_rate"] is None else f"{r['sim_ok_rate'] * 100:4.0f}%"
    inj = "  -" if r["mean_injected"] is None else f"{r['mean_injected']:4.1f}"
    return (f"   L{r['severity']}  {params:12}  "
            f"F1 {r['f1']:.2f}  rec {r['recall']:.2f}  prec {r['precision']:.2f}   "
            f"sim_ok {sim}   inj {inj}")


def _print_report(results: list[dict]) -> None:
    print("\nSynthetic ground-truth evaluation - real join + SPICE vs authored netlist")
    print("=" * 78)
    for res in results:
        clean = res["rows"][0]
        flag = "" if clean["f1"] >= 0.999 else "  <-- CLEAN JOIN IMPERFECT (layout bug)"
        gt = res["gt_mA"]
        mA = f"{gt:.3f}mA" if gt is not None else "n/a"
        exp = f"{res['expect_mA']:.3f}mA" if res["expect_mA"] is not None else "n/a"
        print(f"\n{res['name']}  ({res['components']} comps / {res['nets']} nets / "
              f"{res['gt_pairs']} gt-pairs)   I_src clean={mA} expect={exp}{flag}")
        if res["note"]:
            print(f"   {res['note']}")
        print("   level  error(jit/cut/drop)  join                       spice")
        for r in res["rows"]:
            print(_fmt_row(r))

    print("\n" + "-" * 78)
    print("legend: F1/rec/prec = component-connectivity vs ground truth (rec down =")
    print("        fragmentation, prec down = shorts). sim_ok = % seeds that simulate")
    print("        to the authored current with no injected test source. inj = mean")
    print("        fake sources injected (fragmentation magnitude).")
    print("\nCAVEAT: the error model (jitter/cut/drop) is a PLACEHOLDER, not yet")
    print("calibrated to the real detector. Join scores are a robustness/regression")
    print("signal, not a prediction of real-image performance. See")
    print("docs/synthetic-eval-plan.md. The SPICE half is sound (we control the netlist).")
    if not results[0]["spice_on"]:
        print("\n[ngspice not found - SPICE columns skipped. Set NGSPICE_PATH.]")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="wire_detection.synthgt")
    ap.add_argument("-c", "--circuit", action="append",
                    help="restrict to named circuit(s); repeatable")
    ap.add_argument("-s", "--seeds", type=int, default=8,
                    help="error seeds per non-clean level (default 8)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    args = ap.parse_args(argv)

    specs = CATALOG
    if args.circuit:
        unknown = [c for c in args.circuit if c not in CATALOG_BY_NAME]
        if unknown:
            ap.error(f"unknown circuit(s): {', '.join(unknown)}. "
                     f"available: {', '.join(CATALOG_BY_NAME)}")
        specs = [CATALOG_BY_NAME[c] for c in args.circuit]

    results = run_suite(specs, seeds=args.seeds)
    if args.json:
        json.dump(results, sys.stdout, indent=2)
        print()
    else:
        _print_report(results)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
