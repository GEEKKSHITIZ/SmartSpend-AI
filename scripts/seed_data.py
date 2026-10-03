import sqlite3
from pathlib import Path


DATABASE = Path(__file__).resolve().parent.parent / "smartspend.db"


expenses = [
    # January 2026
    (1200, "Food", "Groceries", "2026-01-05 10:30:00"),
    (450, "Transport", "Metro and bus", "2026-01-08 09:15:00"),
    (800, "Entertainment", "Movie", "2026-01-12 19:30:00"),
    (2500, "Shopping", "Clothes", "2026-01-18 16:20:00"),
    (900, "Utilities", "Internet bill", "2026-01-25 11:00:00"),

    # February 2026
    (1400, "Food", "Groceries", "2026-02-04 10:20:00"),
    (500, "Transport", "Cab", "2026-02-07 18:10:00"),
    (1200, "Entertainment", "Gaming", "2026-02-13 20:00:00"),
    (1800, "Shopping", "Shoes", "2026-02-19 15:45:00"),
    (950, "Utilities", "Electricity bill", "2026-02-25 12:00:00"),

    # March 2026
    (1600, "Food", "Groceries", "2026-03-03 10:00:00"),
    (550, "Transport", "Fuel", "2026-03-09 08:30:00"),
    (1000, "Entertainment", "Restaurant", "2026-03-14 20:15:00"),
    (2200, "Shopping", "Electronics", "2026-03-20 14:30:00"),
    (1100, "Utilities", "Internet and electricity", "2026-03-26 11:30:00"),

    # April 2026
    (1700, "Food", "Groceries", "2026-04-04 10:10:00"),
    (600, "Transport", "Fuel", "2026-04-08 09:00:00"),
    (1300, "Entertainment", "Restaurant", "2026-04-15 20:30:00"),
    (2000, "Shopping", "Clothes", "2026-04-21 17:00:00"),
    (1050, "Utilities", "Electricity bill", "2026-04-26 12:15:00"),

    # May 2026
    (1900, "Food", "Groceries", "2026-05-05 10:30:00"),
    (650, "Transport", "Fuel", "2026-05-09 08:45:00"),
    (1400, "Entertainment", "Movies and food", "2026-05-16 19:45:00"),
    (2400, "Shopping", "Electronics", "2026-05-22 16:30:00"),
    (1150, "Utilities", "Internet bill", "2026-05-27 11:20:00"),

    # June 2026
    (2100, "Food", "Groceries", "2026-06-04 10:00:00"),
    (700, "Transport", "Fuel", "2026-06-08 09:15:00"),
    (1500, "Entertainment", "Restaurant", "2026-06-14 20:00:00"),
    (2600, "Shopping", "Clothes", "2026-06-20 15:30:00"),
    (1200, "Utilities", "Electricity bill", "2026-06-26 12:00:00"),

    # July 2026
    (2300, "Food", "Groceries", "2026-07-05 10:15:00"),
    (750, "Transport", "Fuel", "2026-07-09 08:50:00"),
    (1600, "Entertainment", "Restaurant", "2026-07-15 20:20:00"),
    (2800, "Shopping", "Electronics", "2026-07-21 16:45:00"),
    (1250, "Utilities", "Internet bill", "2026-07-27 11:30:00"),

    # August 2026
    (2500, "Food", "Groceries", "2026-08-04 10:20:00"),
    (800, "Transport", "Fuel", "2026-08-08 09:10:00"),
    (1700, "Entertainment", "Restaurant", "2026-08-14 20:10:00"),
    (3000, "Shopping", "Electronics", "2026-08-20 15:50:00"),
    (1300, "Utilities", "Electricity bill", "2026-08-26 12:10:00"),

    # September 2026
    (2700, "Food", "Groceries", "2026-09-03 10:00:00"),
    (850, "Transport", "Fuel", "2026-09-08 09:20:00"),
    (1800, "Entertainment", "Restaurant", "2026-09-12 20:30:00"),
    (3200, "Shopping", "Electronics", "2026-09-16 16:00:00"),
    (1350, "Utilities", "Internet bill", "2026-09-18 11:45:00"),
]


def seed_database():
    connection = sqlite3.connect(DATABASE)

    connection.execute("DELETE FROM expenses")

    connection.executemany(
        """
        INSERT INTO expenses
        (amount, category, description, created_at)
        VALUES (?, ?, ?, ?)
        """,
        expenses
    )

    connection.commit()

    count = connection.execute(
        "SELECT COUNT(*) FROM expenses"
    ).fetchone()[0]

    connection.close()

    print(f"Inserted {count} demo expenses successfully.")


if __name__ == "__main__":
    seed_database()