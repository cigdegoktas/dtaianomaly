import abc
import numpy as np
import copy
from typing import Optional, Dict
from scipy.stats import binom
from scipy.special import erf


class TimeSeriesAnomalyDetector(abc.ABC):

    @abc.abstractmethod
    def fit(self, trend_data: np.ndarray, labels: Optional[np.array] = None) -> 'TimeSeriesAnomalyDetector':
        raise NotImplementedError("Abstract method 'fit(np.ndarray, Optional[np.array])' should be implemented by the specific anomaly detector!")

    @abc.abstractmethod
    def decision_function(self, trend_data: np.ndarray) -> np.array:
        raise NotImplementedError("Abstract method 'decision_scores(np.ndarray)' should be implemented by the specific anomaly detector!")

    @staticmethod
    @abc.abstractmethod
    def load(parameters: Dict[str, any]) -> 'TimeSeriesAnomalyDetector':
        raise NotImplementedError("Abstract method 'load()' should be implemented by the specific anomaly detector!")

    def predict_proba(self, trend_data: np.ndarray, normalization_strategy: str = 'unifying') -> np.array:
        decision_scores = self.decision_function(trend_data)
        return self._normalize(decision_scores, normalization_strategy)

    @staticmethod
    def _normalize(decision_scores: np.array, normalization_strategy: str) -> np.array:
        # Use min-max normalization to normalize the decision scores
        if normalization_strategy == 'min-max':
            min_decision_score = np.min(decision_scores)
            max_decision_score = np.max(decision_scores)
            probability = (decision_scores - min_decision_score) / (max_decision_score - min_decision_score)

        # Use a unifying strategy to normalize the decision scores (https://epubs.siam.org/doi/abs/10.1137/1.9781611972818.2)
        elif normalization_strategy == 'unifying':
            mean = np.mean(decision_scores)
            std = np.std(decision_scores)
            pre_erf_scores = (decision_scores - mean) / (std * np.sqrt(2))
            erf_scores = erf(pre_erf_scores)
            probability = erf_scores.clip(0, 1).ravel()

        # Raise an exception if an invalid decision score was given
        else:
            raise ValueError(f"Invalid normalization strategy '{normalization_strategy}'!"
                             f"Valid options are: 'unifying', 'min-max'")

        # Return the probabilities, aka normalized decision scores,
        return probability

    def predict_confidence(self, trend_data: np.ndarray, contamination: float) -> np.array:
        # paper: https://link.springer.com/chapter/10.1007/978-3-030-67664-3_14
        # github: https://github.com/Lorenzo-Perini/Confidence_AD/tree/master
        n_samples = len(trend_data)
        n_anomalies = int(n_samples * contamination)
        posterior_prob = self.predict_proba(trend_data)
        prediction = posterior_prob > np.quantile(posterior_prob, 1 - contamination)

        conf_func = np.vectorize(lambda p: 1 - binom.cdf(n_samples - n_anomalies, n_samples, p))
        ex_wise_conf = conf_func(posterior_prob)
        np.place(ex_wise_conf, prediction == 0, 1 - ex_wise_conf[prediction == 0])  # if the example is classified as normal, use 1 - confidence.

        return ex_wise_conf

    def deepcopy(self) -> 'TimeSeriesAnomalyDetector':
        return copy.deepcopy(self)
