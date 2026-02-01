from src.logging_config import setup_logging

setup_logging()

from app import App

if __name__ == "__main__":
    app = App()
    app.mainloop()