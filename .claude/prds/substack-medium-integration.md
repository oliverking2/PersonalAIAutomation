# PRD: Substack & Medium Newsletter Integration

## Overview

Extend newsletter extraction to support Substack and Medium Daily Digest emails.

## Features

- **Substack Parser**: Extract articles from Substack emails (multiple feeds)
  - Joe Reis, DataExpert.io, Daily Dose of Data Science, Seattle Data Guy
- **Medium Daily Digest Parser**: Extract articles from Medium digest emails
  - Requires handling Medium authentication/login flows
- **Unified Storage**: Store all newsletter types in existing articles table with source tag
- **Configurable Feeds**: Add/remove feeds via configuration without code changes

## Implementation Notes

- Create `src/newsletters/substack/` and `src/newsletters/medium/` modules
- Follow existing TLDR parser pattern (`fetcher.py`, `parser.py`, `service.py`)
- Medium may require browser automation or OAuth for access
- Add `source` enum to distinguish newsletter types

## Checklist

- [ ] Substack email parser (HTML extraction)
- [ ] Medium Daily Digest parser
- [ ] Database schema update for source tracking
- [ ] Feed configuration system
- [ ] Dagster jobs for each newsletter type
- [ ] Tests for parsers
