# file: core/app_info.py

"""Application metadata.

This module stores app metadata such as version and author.
These values are not stored in config.json.
"""

__version__ = "2.3.4"
__author__ = "fengyec2"
__app_name__ = "SeewoSplash"
__description__ = "SeewoSplash"
__license__ = "GPLv3"
__repository__ = "https://github.com/fengyec2/custom-seewo-splash-screen"

APP_INFO = {
    "version": __version__,
    "author": __author__,
    "app_name": __app_name__,
    "description": __description__,
    "license": __license__,
    "repository": __repository__,
}


def get_version():
    """Get version string."""
    return __version__


def get_author():
    """Get author name."""
    return __author__


def get_app_name():
    """Get app name."""
    return __app_name__


def get_repository():
    """Get repository URL."""
    return __repository__


def get_full_info():
    """Get a copy of full app metadata."""
    return APP_INFO.copy()


def get_version_string():
    """Get formatted version string."""
    return f"{__app_name__} v{__version__}"


def get_about_text():
    """Get about text."""
    return f"""{__app_name__} v{__version__}

{__description__}

Author: {__author__}
License: {__license__}
Repository: {__repository__}
"""

