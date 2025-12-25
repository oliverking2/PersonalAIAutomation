# Roadmap

## Notion
- ~~Check if any open tasks have the same name when task created through API - error if so~~
  - Long term: maybe needs a clever incremental extract into a db of current tasks to store task names to save a large extract each time.
    so each time a request is made we do an incremental extract of tasks, update db then read from db.
- ~~Reading list, track when read~~

## Orchestration
- ~~Add a scheduler to run daily/hourly jobs~~
  - ~~Daily jobs which can be run and updates sent through Telegram~~
- ~~Migrate from Celery/Redis to Dagster~~
- Notion
  - Goals reminders each month 
  - Daily updates of tasks due or overdue to Telegram

## Email Summaries - Read Emails then push summary to Telegram
- ~~TLDR Newsletter~~
  - ~~Move from "days_back" to a timestamp in db~~
  - Summaries of the description down to ~100chars
- Medium Daily Digest - will need to manage login flows
- Substack - likely different configs per feed
  - Joe Reis
  - DataExpert.io (Subscription needed?)
  - Daily Dose of Data Science
  - Seattle Data Guy
  - more added recently

## API
- ~~Trigger orchestration tasks manually~~

## AI
- Integrate with AWS Bedrock for models
- Add in AI for summarising news articles
- ~~Tool calls for the different Notion tasks~~

## Telegram
- ~~Notifications~~
- 2-way chat
- Add in AI for chatting
- Add Notion tasks/goals/reading lists via the Telegram chat

## Other
- ~~Standardised logging config~~
- ~~FastAPI API~~
- ~~Dockerise~~
- ~~Postgres for DB~~
- ~~Standardise to a single PG database~~
- Host application
- Add CI/CD
- Connect GlitchTip to Telegram using webhook and FastAPI
