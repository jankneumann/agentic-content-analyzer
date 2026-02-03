"""Allow running the CLI as a module: python -m src.cli"""

from src.cli.main import app

if __name__ == "__main__":
    app()
