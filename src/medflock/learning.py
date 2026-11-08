import numpy as np
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score


def predict(weights: np.ndarray, x: np.ndarray) -> np.ndarray:
    return 1 / (1 + np.exp(-np.clip(x @ weights, -30, 30)))


def train(weights: np.ndarray, x: np.ndarray, y: np.ndarray, epochs: int, lr: float):
    result = weights.copy()
    for _ in range(epochs):
        gradient = x.T @ (predict(result, x) - y) / len(y)
        result -= lr * (gradient + 0.001 * np.r_[result[:-1], 0])
    return result


def metrics(weights, x, y):
    probabilities = predict(weights, x)
    both = len(np.unique(y)) == 2
    return {
        "auroc": float(roc_auc_score(y, probabilities)) if both else None,
        "auprc": float(average_precision_score(y, probabilities)) if both else None,
        "brier": float(brier_score_loss(y, probabilities)),
        "count": len(y),
        "events": int(y.sum()),
    }


def partition(x, y, clients: int, mode: str, seed: int):
    rng = np.random.default_rng(seed)
    indices = rng.permutation(len(y))
    if mode == "label_skew":
        indices = indices[np.argsort(y[indices], kind="stable")]
    elif mode == "feature_skew":
        indices = indices[np.argsort(x[indices, 0], kind="stable")]
    elif mode != "iid":
        raise ValueError("Unknown partition mode")
    return [part for part in np.array_split(indices, clients)]
