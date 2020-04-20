import functools
import warnings


def deprecate(reason=None, alternative=None):
    """Decorator that prints a deprecation warning before a function is called.

    Args:
        reason: A reason for deprecation to display in the warning.
        alternative: A function/method object or string representing an
            applicable replacement for the deprecated function.
    """
    if alternative is not None:
        try:
            alternative = alternative.__name__
        except AttributeError:
            pass

    def decorator(deprecated_function):
        """
        Args:
            deprecated_function: The deprecated function for which to display a
                DeprecationWarning.
        """

        @functools.wraps(deprecated_function)
        def wrapper(*args, **kwargs):
            warnings.simplefilter("always", DeprecationWarning)
            warnings.warn(
                "Call to deprecated function {function_name}{reason}."
                "{alternative}".format(
                    function_name=deprecated_function.__name__,
                    reason=(": {}".format(reason) if reason is not None else ""),
                    alternative=(
                        " (Use {} instead)".format(alternative) if alternative is not None else ""
                    ),
                ),
                category=DeprecationWarning,
                stacklevel=2,
            )
            warnings.simplefilter("default", DeprecationWarning)
            return deprecated_function(*args, **kwargs)

        return wrapper

    return decorator
