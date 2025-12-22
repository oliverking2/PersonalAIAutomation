"""Combine all dagster definitions."""

from dagster import Definitions
from src.dagster.newsletters.definitions import defs as newsletters_defs

defs = Definitions.merge(newsletters_defs)
