# BudgetBloom

BudgetBloom is a student-friendly personal finance tracker built with Flask, SQLite, HTML, and CSS. Track income and expenses, review a monthly dashboard, group spending by category, and set monthly category budgets.

## Features

- Monthly income, expense, and available-balance summary
- Add and remove transactions with amount, date, description, and category
- Expense breakdown by category
- Monthly budgets with progress indicators and over-budget alerts
- SQLite persistence; demo records are inserted automatically in a fresh database
- Responsive layout for desktop and mobile

## Run locally

```bash
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open http://127.0.0.1:5000. The first run creates `budget_bloom.db` and adds sample transactions for the current month. Delete the database file to reset the demo data.

## OOP concepts demonstrated

- `Transaction` is an abstract base class that defines shared transaction state and the `balance_effect()` interface.
- `Income` and `Expense` inherit from `Transaction` and override `balance_effect()` with different behavior (polymorphism).
- `Budget` encapsulates the category limit and progress calculation.
- The Flask routes create domain objects, validate input, and persist their state with SQLite.

## Deploy

The included `Procfile` supports platforms that build Python web apps from a GitHub repository. Set a strong `SECRET_KEY` environment variable in the hosting platform. The SQLite database is suitable for local demos; for hosting with ephemeral files, configure a persistent disk or use a managed database.

## Privacy note

This educational demo stores information in a local SQLite file and has no user accounts. Do not enter real bank credentials or sensitive financial records.
