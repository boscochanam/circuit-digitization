from dataclasses import dataclass
from wire_detection.evaluate.metric import segment_dist


@dataclass
class EvalResult:
    tp: int = 0
    fp: int = 0
    redundant: int = 0
    fn: int = 0
    gt_count: int = 0
    recall: float = 0.0
    precision: float = 0.0
    f1: float = 0.0


def evaluate(
    detected: list[tuple[tuple[int, int], tuple[int, int]]],
    ground_truth: list[tuple[tuple[int, int], tuple[int, int]]],
    dist_thresh: int = 20,
) -> EvalResult:
    matched = [False] * len(ground_truth)
    tp = fp = redundant = 0

    for d in detected:
        best = float("inf")
        best_i = -1
        for gi, g in enumerate(ground_truth):
            dist = segment_dist(d, g)
            if dist < best:
                best = dist
                best_i = gi

        if best <= dist_thresh:
            if matched[best_i]:
                redundant += 1
            else:
                tp += 1
                matched[best_i] = True
        else:
            fp += 1

    fn = sum(1 for m in matched if not m)
    recall = tp / max(tp + fn, 1)
    precision = tp / max(tp + fp + redundant, 1)
    f1 = 2 * recall * precision / max(recall + precision, 1e-8)

    return EvalResult(
        tp=tp,
        fp=fp,
        redundant=redundant,
        fn=fn,
        gt_count=len(ground_truth),
        recall=recall,
        precision=precision,
        f1=f1,
    )
