"""GUI Profile Manager package."""
from . import profiles

__all__ = ["profiles"]


def get_app():
    from . import app
    return app


def get_local_api():
    from . import local_api
    return local_api
