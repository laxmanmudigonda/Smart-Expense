<div align="center">
  <img src="static/logo.svg" alt="SmartExpense logo" width="88">

  # SmartExpense

  **A secure, full-stack personal finance manager built with Flask and SQLite.**

  CS50x Final Project

  [Features](#features) · [Technology](#technology) · [Run locally](#run-locally) · [Testing](#testing) · [Deployment](#deployment)
</div>

---

## Overview

SmartExpense helps users understand where their money goes. After creating an account, a user can record income and expenses, organize transactions into categories, set monthly budgets, and inspect charts that turn everyday financial activity into useful insights.

Personal spending is often scattered across receipts, banking applications, and memory. A simple list of purchases does not answer practical questions such as:

- How much did I save this month?
- Which category consumes most of my income?
- Am I close to exceeding my food budget?
- How has my spending changed over time?

SmartExpense answers these questions using the authenticated user's own SQLite records. The application does not substitute demonstration values when data is missing; dashboards, totals, progress indicators, charts, and exports are calculated from real records.

> **Video demonstration:** Coming soon. Add the final CS50 video URL here before submission.
>
> **Live application:** [laxman4355.pythonanywhere.com](https://laxman4355.pythonanywhere.com)

## Features

### Accounts and privacy

- Account registration, login, and logout
- Password hashing with Werkzeug
- Private, session-based access to financial records
- Strict user ownership checks for transactions, categories, and budgets
- Generic login errors that do not reveal whether an account exists

### Transaction management

- Add, edit, and delete income and expense transactions
- Store monetary values as positive integer cents to avoid floating-point errors
- Search transactions by description
- Filter by transaction type, category, and date range
- Sort by date or amount
- Export the current filtered result as CSV
- Protect exported spreadsheets against formula injection

### Categories and budgets

- Seventeen default income and expense categories for every new account
- User-created custom categories
- Category validation that prevents income categories from being used for expenses and vice versa
- Month-specific budgets for expense categories
- Remaining-budget values, progress indicators, and overspending warnings
- Database constraints that prevent duplicate budgets for the same category and month

### Dashboard and analytics

- All-time balance
- Current-month income, expenses, and savings
- Recent transaction history
- Category spending summaries
- Overall monthly budget utilization
- Income-versus-expense chart
- Monthly spending trend
- Expense distribution by category
- Budget-utilization chart
- Helpful empty states for new users

### User experience

- Responsive layouts for desktop and mobile screens
- Bootstrap navigation and forms
- Accessible labels and validation feedback
- Flash messages for successful and unsuccessful operations
- Custom error pages for common HTTP errors
- Configurable currency symbol, with Indian rupees (`₹`) as the default

## Technology

- **Backend:** Python 3, Flask, Jinja, and Werkzeug
- **Database:** SQLite with foreign-key enforcement and indexed queries
- **Frontend:** Semantic HTML, custom CSS, Bootstrap 5, and vanilla JavaScript
- **Charts:** Chart.js
- **Testing:** pytest and Flask's test client

The application uses a Flask application factory named `create_app()`. Tests can therefore provide an isolated temporary database and secret key without altering development or production data. SQLite connections are opened once per Flask application context, configured to return row objects, and closed automatically.

## Database design

The database contains four principal tables:

- `users` stores a case-insensitive unique username and a password hash. Plaintext passwords are never stored.
- `categories` stores user-owned income and expense categories.
- `transactions` stores the owner, category, type, description, date, and positive `amount_cents` value.
- `budgets` associates one expense category with one canonical `YYYY-MM` month and a positive limit in cents.

Foreign keys prevent orphaned records. Check constraints validate transaction types, positive amounts, ISO dates, and month formats. Indexes support transaction history, monthly calculations, category totals, and budget lookups. Every query involving private data includes the authenticated user's ID.

## Project structure

```text
Smart-Expense/
|-- app.py                 # Flask factory, routes, queries, and CLI
|-- helpers.py             # Authentication, CSRF, money, and validation helpers
|-- schema.sql             # Tables, constraints, indexes, and foreign keys
|-- requirements.txt       # Python dependencies
|-- static/
|   |-- css/styles.css     # Responsive visual system
|   |-- js/                # Forms and Chart.js behavior
|   `-- logo.svg           # Application logo and browser icon
|-- templates/             # Shared layout and page templates
|-- tests/                 # Automated application and security tests
`-- instance/              # Local SQLite database; excluded from Git
```

`app.py` keeps the core SQL close to the route that uses it so the application's data flow remains approachable for a CS50 project. Reusable authentication, CSRF, date, money, and validation logic lives in `helpers.py`. The complete schema is version-controlled in `schema.sql`, allowing a clean database to be reproduced from the command line.

## Run locally

### Requirements

- Python 3.11 or newer
- Git

### Windows PowerShell

```powershell
git clone https://github.com/laxmanmudigonda/Smart-Expense.git
cd Smart-Expense

py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m flask --app app:create_app init-db
python -m flask --app app:create_app run --debug
```

Open [http://127.0.0.1:5000](http://127.0.0.1:5000) in a browser. Run `init-db` when creating a new database. The command uses `CREATE TABLE IF NOT EXISTS` and does not add fake financial records.

### Configuration

Copy `.env.example` to `.env` as a reference for supported values. The application reads the following environment variables:

- `SECRET_KEY`: long random secret used to sign sessions; required when `APP_ENV=production`
- `APP_ENV`: set to `production` on a hosted deployment
- `SESSION_COOKIE_SECURE`: set to `true` when the application is served over HTTPS
- `CURRENCY_SYMBOL`: display symbol used for money; defaults to `₹`
- `DATABASE_PATH`: optional absolute path to the SQLite database

The application does not automatically load `.env`; set these values in the shell or through the hosting provider. Never commit a real secret key, `.env` file, virtual environment, or user database.

## Testing

Run the complete automated test suite from the activated virtual environment:

```powershell
python -m pytest -q
```

The tests use a fresh temporary SQLite database. Coverage includes registration, duplicate usernames, authentication failures, logout, password hashing, CSRF protection, transaction validation and ownership, exact amount conversion, category rules, dashboard calculations, month boundaries, budget uniqueness and overages, analytics JSON, CSV safety, unauthenticated access, security headers, and cross-user isolation.

## Security decisions

Submitted monetary values are parsed from a restricted decimal string and converted to cents before reaching SQLite. Month queries use an inclusive first day and the exclusive first day of the following month, avoiding month-length and timestamp-boundary bugs. SQL parameters are used for submitted values, while selectable sort orders come from a fixed whitelist.

Every state-changing form requires a session-bound CSRF token. Destructive operations accept `POST`, not `GET`. Jinja escapes displayed content, authenticated pages disable browser caching, and responses include headers that deny framing and MIME sniffing. Production mode refuses to start without an explicitly configured secret key.

## Deployment

SmartExpense is deployed on PythonAnywhere at [laxman4355.pythonanywhere.com](https://laxman4355.pythonanywhere.com). It requires a Python/WSGI hosting service because GitHub Pages cannot run its Flask backend. Production deployments should set all security-related environment values, serve the site over HTTPS, and use a persistent database volume.

## Limitations and future improvements

SmartExpense currently supports one currency symbol per installation rather than currency conversion or per-account currencies. It does not yet include password-reset email, recurring transactions, bank synchronization, receipt uploads, pagination, or automated backups.

Possible future improvements include recurring income and expenses, statement-import workflows, savings goals, encrypted backups, advanced accessibility testing, multi-currency accounts, and a PostgreSQL deployment suitable for higher concurrent usage.

## AI assistance acknowledgment

AI was used as a mentoring and pair-programming aid for architecture discussion, implementation suggestions, debugging, automated tests, security review, and documentation. The project owner is responsible for reviewing and understanding the code, verifying its final behavior, and accurately describing this assistance in the CS50 submission. No CS50 Finance distribution solution was copied into this project.

## Author

Developed by [laxmanmudigonda](https://github.com/laxmanmudigonda) as a CS50x final project.
