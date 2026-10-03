import sys
import joblib
from pathlib import Path
import pandas as pd


MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "spending_forecast_model.joblib"
)

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import load_expenses
from features import create_monthly_dataset


def load_model():
    return joblib.load(MODEL_PATH)


def predict_next_month():
    model = load_model()

    expenses = load_expenses()
    monthly = create_monthly_dataset(expenses)

    monthly = monthly.dropna(
        subset=["previous_month_spending"]
    ).reset_index(drop=True)

    # No expense data available
    if monthly.empty:
        return 0.0

    monthly["time_index"] = range(len(monthly))

    next_month_index = len(monthly)

    previous_month_spending = monthly["total_spending"].iloc[-1]

    prediction = model.predict(
        pd.DataFrame({
            "time_index": [next_month_index],
            "previous_month_spending": [previous_month_spending]
        })
    )[0]

    return prediction


if __name__ == "__main__":
    prediction = predict_next_month()

    print(f"Predicted next month spending: ₹{prediction:.2f}")