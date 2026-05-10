from wire_detection.experiment.sweep import ConfigResult


def generate_ranking_table(results: list[ConfigResult], top_n: int = 20) -> str:
    lines = ["## Ranking\n"]
    lines.append(
        f"| {'Rank':<5} | {'F1':<8} | {'Precision':<10} | {'Recall':<8} | {'TP':<5} | {'FP':<5} | {'FN':<5} | {'Params':<60} |"
    )
    lines.append(f"|{'-'*7}|{'-'*10}|{'-'*12}|{'-'*10}|{'-'*7}|{'-'*7}|{'-'*7}|{'-'*62}|")

    for i, r in enumerate(results[:top_n]):
        param_str = ", ".join(f"{k}={v}" for k, v in r.params.items())
        lines.append(
            f"| {i+1:<5} | {r.f1:<8.4f} | {r.precision:<10.4f} | {r.recall:<8.4f} "
            f"| {r.tp:<5} | {r.fp:<5} | {r.fn:<5} | {param_str:<60} |"
        )

    return "\n".join(lines)
