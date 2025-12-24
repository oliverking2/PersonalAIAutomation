# Roadmap

## Notion
- Daily updates of tasks due or overdue
- Add tasks via the Telegram chat
- Check if any open tasks have the same name when task created through API - error if so
  - Long term: maybe needs a clever incremental extract of current tasks to store task names to save a large extract each time
- Goals reminders
- Reading list, track when read
- Ability to add additional options to a select if doesn't match existing options

## Orchestration
- ~~Add a scheduler to run daily/hourly jobs~~
  - ~~Daily jobs which can be run and updates sent through Telegram~~
- ~~Migrate from Celery/Redis to Dagster~~

## Email Summaries
- ~~TLDR Newsletter~~
  - ~~Move from "days_back" to a timestamp in db~~
  - Summaries of the description down to ~100chars
- Medium Daily Digest
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
- Tool calls for the different Notion tasks

## Telegram
- ~~Notifications~~
- 2-way chat
- Add in AI for chatting

## Other
- ~~Standardised logging config~~
- ~~FastAPI API~~
- ~~Dockerise~~
- ~~Postgres for DB~~
- ~~Standardise to a single PG database~~
- Host application
- Add CI/CD
- Connect GlitchTip to Telegram using webhook and FastAPI
