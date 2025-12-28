# PRD21: AI-Powered Description Summarisation for Newsletter Alerts

**Status: IN PROGRESS**
**Created: 2025-12-28**

## Overview

Enhance `format_newsletter_alert` to use AI-powered summarisation for article descriptions that exceed 150 characters, rather than truncating them mid-sentence. Descriptions under 150 characters remain unchanged.

## Problem Statement

Currently, `format_newsletter_alert` in `src/alerts/formatters/formatters.py` truncates descriptions to 150 characters:

```python
description = item.metadata.get("description", "")
if description:
    lines.append(description[:150])
```

This produces awkward, mid-sentence cuts:

```
Design is about finding the right problem, the right intent, and the right vision. The features you design and build today should be considered a step

Your Laptop Isn't Ready for LLMs. That's About to Change (10 minute read)
Laptop designs need to be upgraded to make running AI models locally possible. The average laptop is underpowered for large language models. The most
```

Users lose context and the message feels incomplete. AI summarisation would produce coherent, meaningful summaries that preserve the key information.

## Proposed Solution

Replace hard truncation with intelligent summarisation:

1. **Short descriptions (≤150 chars)**: Keep as-is
2. **Long descriptions (>150 chars)**: Use AI to summarise to ~150 characters
3. **Fallback**: If AI fails, fall back to truncation with ellipsis

### Expected Output

**Before (truncation)**:
```
Design is about finding the right problem, the right intent, and the right vision. The features you design and build today should be considered a step
```

**After (AI summary)**:
```
Design is about problem-finding, intent, and vision—today's features should be steps toward a larger goal.
```

## Architecture

Summarise at format time using Claude Haiku (cost-effective model).

```
format_newsletter_alert()
         │
         ▼
  ┌──────────────────┐
  │ For each item:   │
  │   if len > 150:  │
  │     summarise()  │
  └──────────────────┘
         │
         ▼
   BedrockClient
   (Claude Haiku)
```

## Implementation

### New Module: Summariser

```
src/alerts/formatters/
├── formatters.py      # MODIFY - Use summariser
└── summariser.py      # NEW - AI summarisation
```

### Updated Formatter

```python
from src.alerts.formatters.summariser import summarise_description

def format_newsletter_alert(alert: AlertData) -> str:
    # ... existing code ...
    if description:
        summary = summarise_description(description, max_length=150)
        lines.append(summary)
```

## Cost Analysis

Using Claude 3 Haiku for summarisation:

| Metric | Value |
|--------|-------|
| Input tokens (avg description) | ~100 tokens |
| Output tokens (summary) | ~50 tokens |
| Cost per summary | ~$0.00004 |
| Articles per newsletter | ~20 |
| Cost per newsletter | ~$0.0008 |
| Newsletters per month | ~60 |
| **Monthly cost** | **~$0.05** |

## File Changes Summary

| File | Change |
|------|--------|
| `src/alerts/formatters/summariser.py` | NEW - Summarisation service |
| `src/alerts/formatters/formatters.py` | MODIFY - Use summariser |
| `src/alerts/formatters/__init__.py` | MODIFY - Export summariser |
| `testing/alerts/formatters/test_summariser.py` | NEW - Unit tests |

## Success Criteria

1. Descriptions ≤150 characters remain unchanged
2. Descriptions >150 characters are coherently summarised
3. Summaries preserve key information from the original
4. Fallback to truncation works when AI fails
