# Personal AI Automation

## Project Goal
This project is a personal, cloud-hosted AI assistant designed to automate day-to-day information workflows through a single conversational interface.

The assistant is accessed via a private 1:1 Telegram chat, where it can both proactively send notifications and respond interactively to questions and follow-up requests. It is intended to act as a persistent, context-aware assistant rather than a stateless chatbot.

The primary use cases include:
- summarising blog posts and articles received via email 
- scraping and summarising daily content such as Medium digests 
- answering questions and performing small automated tasks via natural language reducing manual overhead in recurring personal workflows

The system maintains conversational context across sessions using persisted history and summaries, allowing it to build continuity over time.

## Roadmap
- Standardised logging config to log to stdout and also a file
- Integrate with Telegram for Agentic Chat
- Telegram bot (chat UI + notifications)
- Daily jobs which can be run and updates sent through Telegram (Celery?)
- FastAPI layer for API
- Dockerised
- AWS Bedrock for models
- Integrate with Notion for task tracking
- Postgres for data storage using alembic

## Notion
- Daily updates of tasks due or overdue
- Add tasks via the Telegram chat 

## Email Summaries
- TLDR Newsletter
- Medium Daily Digest
- Substack
  - Joe Reis
  - DataExpert.io (Subscription needed?)
  - Daily Dose of Data Science
  - Seattle Data Guy
