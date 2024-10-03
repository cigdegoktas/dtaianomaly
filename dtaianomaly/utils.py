from collections.abc import Sequence

import numpy as np


def is_valid_list(value, target_type):
    """
    Check if the given list is a valid, with each instance being a member
    of the given type.

    Parameters
    ----------
    value: object
        The value to check if it is a valid list
    target_type: Type
        The type of each object in the given list

    Returns
    -------
    is_valid: bool
        True if and only if the given ``value`` is a list and all elements in
        the list are of type ``Type``, otherwise False.
    """
    return isinstance(value, list) and all(isinstance(item, target_type) for item in value)


def is_valid_array_like(array):
    """
    Check if input is "array-like". Within ``dtaianomaly``, this is
    either a numpy array of numerical values or a python sequence of
    numerical values.

    Parameters
    ----------
    array: object
        The array to check if it is a valid array-like

    Returns
    -------
    is_valid: bool
        True if and only if the given array is either a numpy array
        or a python sequence, in which the type entirely consists of
        numerical values, otherwise False.
    """
    # Check for valid numpy array
    if isinstance(array, np.ndarray):
        if array.size == 0:
            return True

        return np.issubdtype(array.dtype, np.number) or np.issubdtype(array.dtype, np.floating) or np.issubdtype(array.dtype, bool)

    # Check for numerical sequence
    if isinstance(array, Sequence) and not isinstance(array, str):
        if len(array) == 0:
            return True

        return all(isinstance(item, (int, float)) for item in array)

    # Default case
    return False