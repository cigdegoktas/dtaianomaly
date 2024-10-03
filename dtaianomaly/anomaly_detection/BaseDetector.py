import abc
import os.path
import pickle
import numpy as np
from pathlib import Path
from typing import Optional, Union

from dtaianomaly import utils
from dtaianomaly.PrettyPrintable import PrettyPrintable


class BaseDetector(PrettyPrintable):
    """
    Abstract base class for time series anomaly detection.

    This base class defines method signatures to build
    specific anomaly detectors. User-defined detectors
    can be used throughout the ``dtaianomaly`` by extending
    this base class.
    """

    @abc.abstractmethod
    def fit(self, X: np.ndarray, y: Optional[np.ndarray] = None) -> 'BaseDetector':
        """
        Abstract method, fit this detector to the given data.

        Parameters
        ----------
        X: array-like of shape (n_samples, n_attributes)
            Input time series.
        y: array-like, default=None
            Ground-truth information.

        Returns
        -------
        self: BaseDetector
            Returns the instance itself.
        """

    @abc.abstractmethod
    def decision_function(self, X: np.ndarray) -> np.ndarray:
        """
        Abstract method, compute anomaly scores.

        Parameters
        ----------
        X: array-like of shape (n_samples, n_attributes)
            Input time series.

        Returns
        -------
        decision_scores: array-like of shape (n_samples)
            The computed anomaly scores.
        """

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        """
        Predict anomaly probabilities

        Estimate the probability of a sample of `X` being anomalous, 
        based on the anomaly scores obtained from `decision_function`
        by rescaling them to the range of [0, 1] via min-max scaling.

        Parameters
        ----------
        X: array-like of shape (n_samples, n_attributes)
            Input time series.

        Returns
        -------
        anomaly_scores: array-like of shape (n_samples)
            1D array with the same length as `X`, with values
            in the interval [0, 1], in which a higher value
            implies that the instance is more likely to be
            anomalous.

        Raises
        ------
        ValueError
            If `scores` is not a valid array.
        """
        if not utils.is_valid_array_like(X):
            raise ValueError("Input must be numerical array-like")

        raw_scores = self.decision_function(X)

        min_score = np.nanmin(raw_scores)
        max_score = np.nanmax(raw_scores)
        if min_score == max_score:
            return np.zeros(shape=(X.shape[0]))
        else:
            return (raw_scores - min_score) / (max_score - min_score)

    # @abc.abstractmethod
    # def __str__(self) -> str:
    #     """ Return a string representation of this anomaly detector. """

    def save(self, path: Union[str, Path]) -> None:
        """
        Save detector to disk as a pickle file with extension `.dtai`. If the given
        path consists of multiple subdirectories, then the not existing subdirectories
        are created.

        Parameters
        ----------
        path: str or Path
            Location where to store the detector.
        """
        # Add the '.dtai' extension
        if Path(path).suffix != '.dtai':
            path = f'{path}.dtai'

        # Create the subdirectory, if it doesn't exist
        if not os.path.exists(Path(path).parent):
            os.makedirs(Path(path).parent)

        # Effectively write the anomaly detector to disk
        with open(path, 'wb') as f:
            pickle.dump(self, f)


def load_detector(path: Union[str, Path]) -> BaseDetector:
    """
    Load a detector from disk.

    Warning: method relies on pickle. Only load trusted files!

    Parameters
    ----------
    path: str or Path
        Location of the stored detector.

    Returns
    -------
    detector: BaseDetector
        The loaded detector.
    """
    with open(path, 'rb') as f:
        detector = pickle.load(f)
    return detector