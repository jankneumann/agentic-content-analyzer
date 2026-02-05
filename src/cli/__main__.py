"""Allow running the CLI as a module: python -m src.cli"""

from src.cli.app import app

if __name__ == "__main__":
    app()
