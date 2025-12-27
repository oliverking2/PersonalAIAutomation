"""Entry point for running Telegram polling as a module.

Allows running with: python -m src.telegram
"""

from src.telegram.polling import main

if __name__ == "__main__":
    main()
