# PRD: Daily Task & Goal Reminders

## Overview

Scheduled Telegram notifications for overdue tasks and monthly goal progress updates.

## Features

- **Daily Task Reminders**: Send Telegram notification each morning with tasks due today or overdue
- **Monthly Goal Reminders**: On the 1st of each month, send summary of goals with progress percentages
- **Configurable Schedule**: Dagster schedules with timezone-aware cron expressions
- **Smart Filtering**: Only include tasks with status "Not started" or "In progress"

## Implementation Notes

- Add new Dagster jobs in `src/dagster/reminders/`
- Query Notion API via existing `NotionClient` methods
- Format messages using existing `TelegramClient`
- Store last reminder timestamp to prevent duplicates

## Checklist

- [ ] Dagster job for daily task reminders
- [ ] Dagster job for monthly goal reminders
- [ ] Telegram message formatting for reminders
- [ ] Schedule configuration (cron)
- [ ] Tests for reminder logic
