"""Application entry point for Gaffer's Clipboard.

This module is executed when the package is launched as a module and is
responsible for bootstrapping runtime startup tasks. It configures logging,
creates the main `App` instance, and starts the GUI event loop via `main()`.
"""

from src.app import App
from src.logging_config import setup_logging


def main():
    """Entry point for the Gaffers Clipboard application.

    Configures logging, instantiates the main GUI application,
    and starts its event loop.
    """
    setup_logging()
    app = App()
    app.mainloop()


if __name__ == "__main__":
    main()
