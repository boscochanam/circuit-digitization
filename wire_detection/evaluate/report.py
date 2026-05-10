from wire_detection.evaluate.match import EvalResult


def generate_report(results: list[dict]) -> str:
    lines = ["# Evaluation Report\n"]
    lines.append(f"| {'Image':<20} | {'TP':<5} | {'FP':<5} | {'Redundant':<10} | {'FN':<5} | {'Precision':<10} | {'Recall':<10} | {'F1':<10} |")
    lines.append(f"|{'-'*22}|{'-'*7}|{'-'*7}|{'-'*12}|{'-'*7}|{'-'*12}|{'-'*12}|{'-'*12}|")

    total = EvalResult()
    for r in results:
        img = r.get("image", "unknown")
        e: EvalResult = r.get("result", EvalResult())
        lines.append(
            f"| {img:<20} | {e.tp:<5} | {e.fp:<5} | {e.redundant:<10} | {e.fn:<5} "
            f"| {e.precision:<10.4f} | {e.recall:<10.4f} | {e.f1:<10.4f} |"
        )
        total.tp += e.tp
        total.fp += e.fp
        total.redundant += e.redundant
        total.fn += e.fn
        total.gt_count += e.gt_count

    n = max(len(results), 1)
    avg_precision = total.tp / max(total.tp + total.fp + total.redundant, 1)
    avg_recall = total.tp / max(total.tp + total.fn, 1)
    avg_f1 = 2 * avg_precision * avg_recall / max(avg_precision + avg_recall, 1e-8)

    lines.append(f"\n**Aggregate:** TP={total.tp} FP={total.fp} FN={total.fn} "
                 f"Precision={avg_precision:.4f} Recall={avg_recall:.4f} F1={avg_f1:.4f}")

    return "\n".join(lines)
