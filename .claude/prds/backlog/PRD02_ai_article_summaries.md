# PRD: AI-Powered Article Summaries

## Overview

Use AWS Bedrock to generate concise summaries of newsletter articles for improved Telegram readability.

## Features

- **Description Summarisation**: Reduce article descriptions to ~100 characters using LLM
- **Batch Processing**: Summarise articles in batches to reduce API calls
- **Caching**: Store summaries in database to avoid re-processing
- **Fallback**: If summarisation fails, use truncated original description

## Implementation Notes

- Extend `BedrockClient` or create `SummaryService`
- Add `summary` column to articles table (nullable)
- Integrate into newsletter processing pipeline after extraction
- Use cost-effective model (Claude Haiku) for summarisation

## Checklist

- [ ] Database migration for summary column
- [ ] Summary generation service using Bedrock
- [ ] Integration with newsletter pipeline
- [ ] Update Telegram message format to use summaries
- [ ] Tests for summary generation
