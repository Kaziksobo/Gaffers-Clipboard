from src.logging_config import setup_logging
from src.app import App

def main():
    setup_logging()
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()