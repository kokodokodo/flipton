from .instanceswitcher import MastodonInstanceSwitcher, FliptonError

__all__ = ["MastodonInstanceSwitcher", "FliptonError"]

def __dir__():
    return __all__