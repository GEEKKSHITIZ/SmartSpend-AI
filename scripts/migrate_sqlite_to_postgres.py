import sqlite3
import os

import psycopg
from dotenv import load_dotenv


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

SQLITE_DATABASE = "smartspend.db"


def migrate():

    sqlite_connection = sqlite3.connect(
        SQLITE_DATABASE
    )

    sqlite_connection.row_factory = sqlite3.Row

    postgres_connection = psycopg.connect(
        DATABASE_URL
    )

    try:

        # =========================
        # USERS
        # =========================

        users = sqlite_connection.execute(
            """
            SELECT
                id,
                name,
                email,
                password_hash,
                created_at
            FROM users
            ORDER BY id
            """
        ).fetchall()

        for user in users:

            postgres_connection.execute(
                """
                INSERT INTO users
                (id, name, email, password_hash, created_at)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                (
                    user["id"],
                    user["name"],
                    user["email"],
                    user["password_hash"],
                    user["created_at"]
                )
            )

        # =========================
        # EXPENSES
        # =========================

        expenses = sqlite_connection.execute(
            """
            SELECT
                id,
                amount,
                category,
                description,
                created_at
            FROM expenses
            ORDER BY id
            """
        ).fetchall()

        for expense in expenses:

            postgres_connection.execute(
    """
    INSERT INTO expenses
    (id, amount, category, description, created_at)
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (id) DO NOTHING
    """,
    (
        expense["id"],
        expense["amount"],
        expense["category"],
        expense["description"],
        expense["created_at"]
    )
)

        # =========================
        # BUDGETS
        # =========================

        budgets = sqlite_connection.execute(
            """
            SELECT
                id,
                month,
                amount,
                created_at
            FROM budgets
            ORDER BY id
            """
        ).fetchall()

        for budget in budgets:

            postgres_connection.execute(
    """
    INSERT INTO budgets
    (id, month, amount, created_at)
    VALUES (%s, %s, %s, %s)
    ON CONFLICT (id) DO NOTHING
    """,
    (
        budget["id"],
        budget["month"],
        budget["amount"],
        budget["created_at"]
    )
)

        postgres_connection.commit()

        print("Migration completed successfully.")
        print(f"Users migrated: {len(users)}")
        print(f"Expenses migrated: {len(expenses)}")
        print(f"Budgets migrated: {len(budgets)}")

    except Exception:

        postgres_connection.rollback()
        raise

    finally:

        sqlite_connection.close()
        postgres_connection.close()


if __name__ == "__main__":
    migrate()