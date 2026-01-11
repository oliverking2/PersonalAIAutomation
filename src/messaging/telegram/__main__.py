"""Entry point for running Telegram polling as a module.

Allows running with: python -m src.messaging.telegram
"""

from src.messaging.telegram.polling import main

if __name__ == "__main__":
    main()
