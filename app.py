from __future__ import annotations

import os
import sqlite3
from abc import ABC, abstractmethod
from datetime import date, datetime
from pathlib import Path

from flask import Flask, flash, redirect, render_template, request, url_for


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("BUDGET_BLOOM_DB", BASE_DIR / "budget_bloom.db"))
app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "local-demo-key-change-before-deploy")

CATEGORIES = ["Food", "Transport", "Housing", "Shopping", "Health", "Education", "Entertainment", "Utilities", "Salary", "Other"]
EXPENSE_CATEGORIES = [c for c in CATEGORIES if c != "Salary"]


def db() -> sqlite3.Connection:
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    return connection


class Transaction(ABC):
    """Base class for a money movement; subclasses define its signed effect."""

    def __init__(self, amount: float, category: str, description: str, happened_on: date):
        if amount <= 0:
            raise ValueError("Amount must be greater than zero.")
        self.amount = round(float(amount), 2)
        self.category = category
        self.description = description.strip()
        self.happened_on = happened_on

    @abstractmethod
    def balance_effect(self) -> float:
        raise NotImplementedError


class Income(Transaction):
    def balance_effect(self) -> float:
        return self.amount


class Expense(Transaction):
    def balance_effect(self) -> float:
        return -self.amount


class Budget:
    def __init__(self, category: str, limit: float):
        if limit <= 0:
            raise ValueError("Budget limit must be greater than zero.")
        self.category = category
        self.limit = round(float(limit), 2)

    def progress(self, spent: float) -> float:
        return min(100.0, spent / self.limit * 100)


def init_db() -> None:
    with db() as con:
        con.executescript("""
            CREATE TABLE IF NOT EXISTS transactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                kind TEXT NOT NULL CHECK(kind IN ('income', 'expense')),
                amount REAL NOT NULL CHECK(amount > 0),
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                happened_on TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS budgets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                month TEXT NOT NULL,
                limit_amount REAL NOT NULL CHECK(limit_amount > 0),
                UNIQUE(category, month)
            );
        """)
        if con.execute("SELECT COUNT(*) FROM transactions").fetchone()[0] == 0:
            today = date.today()
            month_day = lambda day: date(today.year, today.month, min(day, 28)).isoformat()
            demo = [
                ("income", 28000, "Salary", "Monthly stipend", month_day(1)),
                ("expense", 1850, "Food", "Groceries and snacks", month_day(3)),
                ("expense", 620, "Transport", "Bus pass", month_day(5)),
                ("expense", 2400, "Education", "Course materials", month_day(8)),
                ("expense", 1250, "Entertainment", "Movie night", month_day(10)),
                ("expense", 3100, "Food", "Weekend meals", month_day(12)),
            ]
            con.executemany("INSERT INTO transactions(kind,amount,category,description,happened_on) VALUES(?,?,?,?,?)", demo)
            month = today.strftime("%Y-%m")
            con.executemany("INSERT OR IGNORE INTO budgets(category,month,limit_amount) VALUES(?,?,?)", [
                ("Food", month, 6000), ("Transport", month, 2500), ("Education", month, 5000), ("Entertainment", month, 3000)
            ])


def money(value: float) -> str:
    return f"₹{value:,.0f}"


@app.template_filter("money")
def money_filter(value: float) -> str:
    return money(value or 0)


@app.get("/")
def dashboard():
    selected_month = request.args.get("month", date.today().strftime("%Y-%m"))
    try:
        datetime.strptime(selected_month, "%Y-%m")
    except ValueError:
        selected_month = date.today().strftime("%Y-%m")
    with db() as con:
        rows = con.execute("SELECT * FROM transactions WHERE substr(happened_on,1,7)=? ORDER BY happened_on DESC,id DESC", (selected_month,)).fetchall()
        income_total = sum(r["amount"] for r in rows if r["kind"] == "income")
        expense_total = sum(r["amount"] for r in rows if r["kind"] == "expense")
        budgets = con.execute("SELECT * FROM budgets WHERE month=? ORDER BY category", (selected_month,)).fetchall()
        spending = {r["category"]: r["total"] for r in con.execute("SELECT category,SUM(amount) total FROM transactions WHERE kind='expense' AND substr(happened_on,1,7)=? GROUP BY category", (selected_month,))}
        budget_cards = []
        for b in budgets:
            model = Budget(b["category"], b["limit_amount"])
            spent = spending.get(b["category"], 0)
            budget_cards.append({"category": b["category"], "limit": model.limit, "spent": spent, "left": max(model.limit-spent, 0), "progress": model.progress(spent), "over": spent > model.limit})
        category_totals = sorted(spending.items(), key=lambda pair: pair[1], reverse=True)
    return render_template("dashboard.html", month=selected_month, transactions=rows, income=income_total, expenses=expense_total, balance=income_total-expense_total, budgets=budget_cards, categories=category_totals)


@app.post("/transactions")
def add_transaction():
    kind = request.form.get("kind", "expense")
    category = request.form.get("category", "Other")
    try:
        amount = float(request.form.get("amount", "0"))
        happened_on = date.fromisoformat(request.form.get("happened_on", ""))
        description = request.form.get("description", "").strip()
        if not description:
            raise ValueError("Add a short description.")
        if kind not in {"income", "expense"}:
            raise ValueError("Choose income or expense.")
        if category not in (CATEGORIES if kind == "income" else EXPENSE_CATEGORIES):
            raise ValueError("Choose a valid category.")
        model = (Income if kind == "income" else Expense)(amount, category, description, happened_on)
        with db() as con:
            con.execute("INSERT INTO transactions(kind,amount,category,description,happened_on) VALUES(?,?,?,?,?)", (kind, model.amount, model.category, model.description, model.happened_on.isoformat()))
        flash("Transaction added.", "success")
    except (ValueError, TypeError) as exc:
        flash(str(exc) or "Enter a valid amount and date.", "error")
    return redirect(url_for("dashboard", month=request.form.get("happened_on", date.today().isoformat())[:7]))


@app.post("/transactions/<int:transaction_id>/delete")
def delete_transaction(transaction_id: int):
    with db() as con:
        con.execute("DELETE FROM transactions WHERE id=?", (transaction_id,))
    flash("Transaction removed.", "success")
    return redirect(url_for("dashboard", month=request.form.get("month", date.today().strftime("%Y-%m"))))


@app.post("/budgets")
def save_budget():
    category = request.form.get("category", "")
    month = request.form.get("month", date.today().strftime("%Y-%m"))
    try:
        datetime.strptime(month, "%Y-%m")
        if category not in EXPENSE_CATEGORIES:
            raise ValueError("Choose a valid spending category.")
        model = Budget(category, float(request.form.get("limit", "0")))
        with db() as con:
            con.execute("INSERT INTO budgets(category,month,limit_amount) VALUES(?,?,?) ON CONFLICT(category,month) DO UPDATE SET limit_amount=excluded.limit_amount", (model.category, month, model.limit))
        flash(f"{category} budget saved for {month}.", "success")
    except (ValueError, TypeError) as exc:
        flash(str(exc) or "Enter a valid budget.", "error")
    return redirect(url_for("dashboard", month=month))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
