import datetime


def get_date():
    return datetime.datetime.now().strftime("%Y-%m-%d")

def get_date_12hr_min():
    return datetime.datetime.now().strftime("%Y-%m-%d: %I:%M%p")

def get_date_24hr_min():
    return datetime.datetime.now().strftime("%Y-%m-%d: %H:%M")

def listify(variable):
    """
    Convert a given variable into a list.

    If the variable is already a list, it's returned as is. If it's a string, it's returned as a
    single-element list. If it's another iterable (like a set or tuple), it's converted to a list.

    Parameters
    ----------
    variable : iterable or str
        The variable to be converted to a list. This can be any iterable or string.

    Returns
    -------
    list
        The variable converted to a list.

    Raises
    ------
    TypeError
        If the variable is not an iterable and not a string.

    Examples
    --------
    >>> listify("Hello")
    ['Hello']
    >>> listify([1, 2, 3])
    [1, 2, 3]
    >>> listify((1, 2, 3))
    [1, 2, 3]
    """
    if isinstance(variable, str):
        return [variable]
    elif isinstance(variable, (list, tuple)):
        return list(variable)
    elif hasattr(variable, 'tolist'):  # np.array like object
        return variable.tolist()
    elif hasattr(variable, 'to_list'):  # pd.Series like object
        return variable.to_list()
    elif hasattr(variable, '__iter__'):
        # If it's a dataframe like object get list of all values
        if hasattr(variable, 'to_numpy'):
            return variable.to_numpy().tolist()
        else:
            return list(variable)
    else:
        return [variable]