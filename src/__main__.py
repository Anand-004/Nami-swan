"""Ensure `python -m src` runs main()."""
from .main import main
import sys

sys.exit(main())
