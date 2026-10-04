import os
from dotenv import load_dotenv
import pandas as pd
import psycopg


load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")


def load_expenses():

    if not DATABASE_URL:
        raise RuntimeError(
            "DATABASE_URL is not set in .env"
        )

    connection = psycopg.connect(
        DATABASE_URL
    )

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

    dataframe = pd.read_sql_query(
        query,
        connection
    )

    connection.close()

    return dataframe
