"""Compatible flat tensors support logistic and small neural models through one interface."""

import numpy as np
from scipy.special import expit
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score


class BinaryModel:
    def __init__(self, features, family="logistic", hidden=16):
        if family not in {"logistic", "mlp"}:
            raise ValueError("Unsupported model family")
        self.features, self.family, self.hidden = features, family, hidden
        self.size = features + 1 if family == "logistic" else features * hidden + 2 * hidden + 1

    def initialize(self, seed):
        if self.family == "logistic":
            return np.zeros(self.size)
        return np.random.default_rng(seed).normal(0, 0.1, self.size)

    def predict(self, weights, values):
        if self.family == "logistic":
            return expit(values @ weights[:-1] + weights[-1])
        width, h = self.features * self.hidden, self.hidden
        hidden = np.tanh(
            values @ weights[:width].reshape(self.features, h) + weights[width : width + h]
        )
        return expit(hidden @ weights[width + h : width + 2 * h] + weights[-1])

    def gradient(self, weights, values, labels, l2):
        error = self.predict(weights, values) - labels
        if self.family == "logistic":
            return np.r_[values.T @ error / len(labels) + l2 * weights[:-1], error.mean()]
        width, h = self.features * self.hidden, self.hidden
        hidden = np.tanh(
            values @ weights[:width].reshape(self.features, h) + weights[width : width + h]
        )
        back = error[:, None] * weights[width + h : width + 2 * h] * (1 - hidden**2)
        gradient = np.r_[
            (values.T @ back / len(labels)).ravel(),
            back.mean(axis=0),
            hidden.T @ error / len(labels),
            error.mean(),
        ]
        gradient[:-1] += l2 * weights[:-1]
        return gradient

    def train(self, weights, values, labels, epochs, rate, l2=0.001):
        weights = weights.copy()
        for _ in range(epochs):
            weights -= rate * self.gradient(weights, values, labels, l2)
        if not np.isfinite(weights).all():
            raise ValueError("Training produced non-finite weights")
        return weights


def evaluate(model, weights, values, labels):
    probabilities = model.predict(weights, values)
    both = len(np.unique(labels)) == 2
    return {
        "auroc": float(roc_auc_score(labels, probabilities)) if both else None,
        "auprc": float(average_precision_score(labels, probabilities)) if both else None,
        "brier": float(brier_score_loss(labels, probabilities)),
        "log_loss": float(log_loss(labels, probabilities, labels=[0, 1])),
        "count": len(labels),
        "events": int(labels.sum()),
    }
