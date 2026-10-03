import pandas as pd


def create_features(dataframe):
    df = dataframe.copy()

    # Convert timestamp to datetime
    df["created_at"] = pd.to_datetime(df["created_at"])

    # Time-based features
    df["year"] = df["created_at"].dt.year
    df["month"] = df["created_at"].dt.month
    df["day"] = df["created_at"].dt.day
    df["day_of_week"] = df["created_at"].dt.dayofweek

    # Weekend indicator
    df["is_weekend"] = df["day_of_week"].isin([5, 6]).astype(int)

    # Monthly period
    df["year_month"] = df["created_at"].dt.to_period("M").astype(str)

    return df

def create_monthly_dataset(dataframe):
    df = dataframe.copy()

    df["created_at"] = pd.to_datetime(df["created_at"])

    monthly = (
        df.groupby(df["created_at"].dt.to_period("M"))
        .agg(
            total_spending=("amount", "sum"),
            expense_count=("amount", "count"),
            average_expense=("amount", "mean")
        )
        .reset_index()
    )

    monthly["year_month"] = monthly["created_at"].astype(str)

    monthly["previous_month_spending"] = monthly["total_spending"].shift(1)

    monthly.drop(columns=["created_at"], inplace=True)

    return monthly