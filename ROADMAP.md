# Roadmap

## Notion

## Orchestration

## Email Summaries - Read Emails then push summary to Telegram
- TLDR Newsletter
  - Summaries of the description down to ~100chars rather than truncating
- Medium Daily Digest - will need to manage login flows
- Substack - likely different configs per feed
  - Joe Reis
  - DataExpert.io (Subscription needed?)
  - Daily Dose of Data Science
  - Seattle Data Guy
  - more added recently

## API

## AI
- Add in AI for summarising news articles
- Standardise JSON validation when getting data from AI

## Telegram Agent
- Multiple messages needing to be processed at once
- Add in AI for 2-way chat
- Add Notion tasks/goals/reading lists via the Telegram chat

## Other
- Host application
- Add CI/CD
- Connect GlitchTip to Telegram using webhook and FastAPI
- Split unit test and integration testing, pytest for parallisation and runs on running with Claude

# Roadmap Ideas for Consideration

🔴 High Value / Core Experience

| Idea                  | Description                                                                            | Complexity |
|-----------------------|----------------------------------------------------------------------------------------|------------|
| Daily Briefing        | Morning summary combining: weather, calendar (via Graph), overdue tasks, goal progress | Medium     |
| URL to Reading List   | Send a URL via Telegram, AI extracts title/category and adds to reading list           | Low        |

🟢 Productivity & Automation

| Idea              | Description                                                                 | Complexity |
|-------------------|-----------------------------------------------------------------------------|------------|
| Recurring Tasks   | Template-based recurring task creation (weekly reviews, monthly goals)      | Low        |
| Quick Capture     | Telegram command to quickly add thoughts/ideas to a dedicated Notion inbox  | Low        |

🟣 AI Enhancements

| Idea                  | Description                                                                      | Complexity |
|-----------------------|----------------------------------------------------------------------------------|------------|
| Conversation Memory   | Long-term memory across sessions (embeddings + vector search)                    | High       |
| Multi-Model Routing   | Use Haiku for simple tasks, Sonnet for complex reasoning, Opus for planning      | Medium     |
| Context Injection     | Automatically include relevant context (recent tasks, goals) in agent prompts    | Medium     |

⚪ Infrastructure & Ops

| Idea              | Description                                                           | Complexity |
|-------------------|-----------------------------------------------------------------------|------------|
| Metrics Dashboard | Grafana/similar dashboard for system health, API latency, agent usage | Medium     |
| Backup & Export   | Regular export of all data to S3/local for disaster recovery          | Low        |
| Rate Limiting     | Protect against runaway agent loops or API abuse                      | Low        |
