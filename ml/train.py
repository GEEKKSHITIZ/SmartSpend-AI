import sys
from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LinearRegression
from sklearn.metrics import mean_absolute_error, mean_squared_error

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import load_expenses
from features import create_monthly_dataset

def evaluate_model(model, X_test, y_test):
    predictions = model.predict(X_test)

    mae = mean_absolute_error(y_test, predictions)
    rmse = mean_squared_error(y_test, predictions) ** 0.5

    return mae, rmse, predictions

def walk_forward_validation(monthly):
    results = []

    for test_index in range(5, len(monthly)):
        train_data = monthly.iloc[:test_index]
        test_data = monthly.iloc[test_index:test_index + 1]

        X_train = train_data[
            ["time_index", "previous_month_spending"]
        ]
        y_train = train_data["total_spending"]

        X_test = test_data[
            ["time_index", "previous_month_spending"]
        ]
        y_test = test_data["total_spending"]

        model = LinearRegression()
        model.fit(X_train, y_train)

        prediction = model.predict(X_test)[0]

        results.append({
            "actual": y_test.iloc[0],
            "predicted": prediction,
            "error": abs(y_test.iloc[0] - prediction)
        })

    return pd.DataFrame(results)

def evaluate_walk_forward(results):
    mae = mean_absolute_error(
        results["actual"],
        results["predicted"]
    )

    rmse = mean_squared_error(
        results["actual"],
        results["predicted"]
    ) ** 0.5

    return mae, rmse

def train_forecasting_model():
    expenses = load_expenses()
    monthly = create_monthly_dataset(expenses)

    # Convert month into sequential time index
    monthly["time_index"] = range(len(monthly))

    monthly["time_index"] = range(len(monthly))

    monthly = monthly.dropna(
        subset=["previous_month_spending"]
    ).reset_index(drop=True)

    monthly["time_index"] = range(len(monthly))

    X = monthly[["time_index", "previous_month_spending"]]
    y = monthly["total_spending"]

    split_index = len(monthly) - 2
    X_train = X.iloc[:split_index]
    X_test = X.iloc[split_index:]

    y_train = y.iloc[:split_index]
    y_test = y.iloc[split_index:]  
    model = LinearRegression()
    model.fit(X_train, y_train)

    models_dir = Path(__file__).resolve().parent.parent / "models"
    models_dir.mkdir(exist_ok=True)

    model_path = models_dir / "spending_forecast_model.joblib"

    joblib.dump(model, model_path)

    print(f"Model saved to: {model_path}")
    mae, rmse, test_predictions = evaluate_model(
    model,
    X_test,
    y_test
)

    print()
    print("Test set predictions:")

    for actual, predicted in zip(y_test, test_predictions):
        print(
            f"Actual: ₹{actual:.2f} | "
            f"Predicted: ₹{predicted:.2f}"
        )

    print(f"MAE: ₹{mae:.2f}")
    print(f"RMSE: ₹{rmse:.2f}")
    return model, monthly


if __name__ == "__main__":
    model, monthly = train_forecasting_model()

    validation_results = walk_forward_validation(monthly)

    print()
    print("Walk-forward validation:")
    print(validation_results)

    validation_mae, validation_rmse = evaluate_walk_forward(
    validation_results
)

    print()
    print(f"Walk-forward MAE: ₹{validation_mae:.2f}")
    print(f"Walk-forward RMSE: ₹{validation_rmse:.2f}")

    print("Model trained successfully.")
    print()
    print("Historical monthly spending:")
    print(monthly)

    next_month_index = len(monthly)

    prediction = model.predict(
    pd.DataFrame({
        "time_index": [next_month_index],
        "previous_month_spending": [monthly["total_spending"].iloc[-1]]
    })
)[0]

    print()
    print(f"Next month predicted spending: ₹{prediction:.2f}")