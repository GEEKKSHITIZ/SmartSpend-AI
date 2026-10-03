import sqlite3
from pathlib import Path

import pandas as pd


DATABASE = Path(__file__).resolve().parent.parent / "smartspend.db"


def load_expenses():
    connection = sqlite3.connect(DATABASE)

    query = """
        SELECT
            id,
            amount,
            category,
            description,
            created_at
        FROM expenses
        ORDER BY created_at ASC
    """

    dataframe = pd.read_sql_query(query, connection)

    connection.close()

    return dataframe