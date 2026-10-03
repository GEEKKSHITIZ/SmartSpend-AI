import re
import sys
import joblib
import pandas as pd

from datetime import datetime
from pathlib import Path

sys.path.insert(
    0,
    str(Path(__file__).resolve().parent.parent)
)

from ml.data import load_expenses
from ml.features import create_monthly_dataset

from flask import (
    Flask,
    jsonify,
    request,
    render_template,
    redirect
)

from app.database import (
    get_db_connection,
    init_db
)

from ai.financial_context import (
    get_financial_summary,
    get_category_summary,
    get_forecast,
    get_month_difference,
    get_category_month_difference,
    get_financial_insights,
    build_financial_context,
    detect_what_if_parameters,
    calculate_what_if,
    detect_what_if_category,
    calculate_category_what_if,
    detect_question_intent,
    get_category_spending_for_month,
)

from ai.ollama_client import answer_financial_question


# =========================================================
# MODEL
# =========================================================

MODEL_PATH = (
    Path(__file__).resolve().parent.parent
    / "models"
    / "spending_forecast_model.joblib"
)

forecast_model = joblib.load(MODEL_PATH)


# =========================================================
# FLASK APP
# =========================================================

app = Flask(
    __name__,
    template_folder="../dashboard/templates",
    static_folder="../dashboard/static"
)

init_db()


# =========================================================
# DASHBOARD
# =========================================================

@app.route("/dashboard", methods=["GET"])
def dashboard():

    analytics = get_analytics()

    # -----------------------------------------------------
    # BUDGET
    # -----------------------------------------------------

    budget_response = get_budget_analysis()

    if isinstance(budget_response, tuple):
        budget_response = {
            "month": "Current Month",
            "budget": 0,
            "total_spending": 0,
            "remaining_budget": 0,
            "budget_used_percentage": 0,
            "status": "NOT_SET"
        }

    forecast = get_forecast()

    # -----------------------------------------------------
    # CATEGORY ANALYTICS
    # -----------------------------------------------------

    categories = get_category_analytics()

    print(
        "CATEGORY DATA:",
        categories
    )

    category_data = categories["categories"]

    # -----------------------------------------------------
    # MONTHLY ANALYTICS
    # -----------------------------------------------------

    monthly = get_monthly_analytics()

    monthly_data = monthly["monthly_analytics"]

    if monthly_data:

        max_spending = max(
            item["total_spending"]
            for item in monthly_data
        )

        for item in monthly_data:

            if max_spending > 0:
                item["bar_height"] = (
                    item["total_spending"]
                    / max_spending
                ) * 100
            else:
                item["bar_height"] = 0

    # -----------------------------------------------------
    # FINANCIAL INSIGHTS
    # -----------------------------------------------------

    insight_data = get_financial_insights()

    spending_patterns = (
        insight_data["spending_patterns"]
    )

    unusual_expenses = (
        insight_data["unusual_expenses"]
    )

    insights = (
        insight_data["insights"]
    )

    # -----------------------------------------------------
    # RENDER DASHBOARD
    # -----------------------------------------------------

    return render_template(
        "dashboard.html",

        analytics=analytics,

        budget=budget_response,

        forecast=forecast,

        categories=category_data,

        monthly=monthly_data,

        spending_patterns=spending_patterns,

        unusual_expenses=unusual_expenses,

        insights=insights
    )


# =========================================================
# HOME
# =========================================================

@app.route("/")
def home():
    return redirect("/dashboard")


# =========================================================
# ML FORECAST
# =========================================================

@app.route("/ml/forecast", methods=["GET"])
def forecast():

    expenses = load_expenses()

    monthly = create_monthly_dataset(
        expenses
    )

    monthly = monthly.dropna(
        subset=[
            "previous_month_spending"
        ]
    ).reset_index(drop=True)

    monthly["time_index"] = range(
        len(monthly)
    )

    next_month_index = len(monthly)

    previous_month_spending = (
        monthly[
            "total_spending"
        ].iloc[-1]
    )

    prediction = forecast_model.predict(
        pd.DataFrame({
            "time_index": [
                next_month_index
            ],
            "previous_month_spending": [
                previous_month_spending
            ]
        })
    )[0]

    return jsonify({
        "predicted_spending": round(
            float(prediction),
            2
        ),
        "currency": "INR"
    })


# =========================================================
# ADD EXPENSE - API
# =========================================================

@app.route(
    "/expenses",
    methods=["POST"]
)
def add_expense():

    data = request.get_json()

    if not data:
        return {
            "error": "Request body is required"
        }, 400

    amount = data.get("amount")
    category = data.get("category")
    description = data.get("description")

    if amount is None:
        return {
            "error": "Amount is required"
        }, 400

    try:
        amount = float(amount)

    except (
        TypeError,
        ValueError
    ):
        return {
            "error": "Amount must be a number"
        }, 400

    if amount <= 0:
        return {
            "error": "Amount must be greater than 0"
        }, 400

    if (
        not category
        or not category.strip()
    ):
        return {
            "error": "Category is required"
        }, 400

    connection = get_db_connection()

    cursor = connection.execute(
        """
        INSERT INTO expenses
        (amount, category, description)
        VALUES (?, ?, ?)
        """,
        (
            amount,
            category.strip(),
            description
        )
    )

    connection.commit()

    expense_id = cursor.lastrowid

    connection.close()

    return {
        "message": "Expense added successfully",
        "expense_id": expense_id
    }, 201


# =========================================================
# ANALYTICS
# =========================================================

@app.route(
    "/analytics",
    methods=["GET"]
)
def get_analytics():

    connection = get_db_connection()

    result = connection.execute(
        """
        SELECT
            COUNT(*) AS total_expenses,

            COALESCE(
                SUM(amount),
                0
            ) AS total_spending,

            COALESCE(
                AVG(amount),
                0
            ) AS average_expense,

            COALESCE(
                MAX(amount),
                0
            ) AS highest_expense,

            COALESCE(
                MIN(amount),
                0
            ) AS lowest_expense

        FROM expenses
        """
    ).fetchone()

    connection.close()

    return {
        "total_expenses":
            result["total_expenses"],

        "total_spending":
            result["total_spending"],

        "average_expense":
            result["average_expense"],

        "highest_expense":
            result["highest_expense"],

        "lowest_expense":
            result["lowest_expense"]
    }


# =========================================================
# ANALYTICS PAGE
# =========================================================

@app.route(
    "/analytics/page",
    methods=["GET"]
)
def analytics_page():

    analytics = get_analytics()

    categories = (
        get_category_analytics()
        ["categories"]
    )

    monthly = (
        get_monthly_analytics()
        ["monthly_analytics"]
    )

    trends = (
        get_spending_trends()
        ["trends"]
    )

    return render_template(
        "analytics.html",

        analytics=analytics,

        categories=categories,

        monthly=monthly,

        trends=trends
    )


# =========================================================
# CATEGORY ANALYTICS
# =========================================================

@app.route(
    "/analytics/categories",
    methods=["GET"]
)
def get_category_analytics():

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT
            category,

            COUNT(*) AS expense_count,

            SUM(amount) AS total_spending,

            AVG(amount) AS average_expense,

            ROUND(
                (
                    SUM(amount) * 100.0
                )
                /
                NULLIF(
                    (
                        SELECT SUM(amount)
                        FROM expenses
                    ),
                    0
                ),
                2
            ) AS percentage

        FROM expenses

        GROUP BY category

        ORDER BY total_spending DESC
        """
    ).fetchall()

    connection.close()

    return {
        "categories": [
            dict(row)
            for row in results
        ]
    }


# =========================================================
# MONTHLY ANALYTICS
# =========================================================

@app.route(
    "/analytics/monthly",
    methods=["GET"]
)
def get_monthly_analytics():

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT

            strftime(
                '%Y-%m',
                created_at
            ) AS month,

            COUNT(*) AS expense_count,

            SUM(amount) AS total_spending,

            AVG(amount) AS average_expense

        FROM expenses

        GROUP BY strftime(
            '%Y-%m',
            created_at
        )

        ORDER BY month DESC
        """
    ).fetchall()

    connection.close()

    return {
        "monthly_analytics": [
            dict(row)
            for row in results
        ]
    }


# =========================================================
# GET EXPENSES
# =========================================================

@app.route(
    "/expenses",
    methods=["GET"]
)
def get_expenses():

    connection = get_db_connection()

    expenses = connection.execute(
        """
        SELECT *
        FROM expenses
        ORDER BY id DESC
        """
    ).fetchall()

    connection.close()

    return {
        "count": len(expenses),

        "expenses": [
            dict(expense)
            for expense in expenses
        ]
    }


# =========================================================
# SPENDING TRENDS
# =========================================================

@app.route(
    "/analytics/trends",
    methods=["GET"]
)
def get_spending_trends():

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT

            strftime(
                '%Y-%m',
                created_at
            ) AS month,

            SUM(amount) AS total_spending

        FROM expenses

        GROUP BY strftime(
            '%Y-%m',
            created_at
        )

        ORDER BY month ASC
        """
    ).fetchall()

    connection.close()

    trends = []

    for index, row in enumerate(results):

        current_spending = (
            row["total_spending"]
        )

        if index == 0:

            change_percentage = 0

        else:

            previous_spending = (
                results[
                    index - 1
                ]["total_spending"]
            )

            if previous_spending == 0:

                change_percentage = 0

            else:

                change_percentage = (
                    (
                        current_spending
                        - previous_spending
                    )
                    / previous_spending
                ) * 100

        trends.append({
            "month": row["month"],

            "total_spending":
                current_spending,

            "change_percentage":
                round(
                    change_percentage,
                    2
                )
        })

    return {
        "trends": trends
    }


# =========================================================
# BUDGET PAGE
# =========================================================

@app.route(
    "/budgets/page",
    methods=["GET"]
)
def budget_page():

    selected_month = request.args.get(
        "month"
    )

    if not selected_month:

        selected_month = (
            datetime.now()
            .strftime("%Y-%m")
        )

    connection = get_db_connection()

    # -----------------------------------------------------
    # GET BUDGET
    # -----------------------------------------------------

    budget_row = connection.execute(
        """
        SELECT amount
        FROM budgets
        WHERE month = ?
        """,
        (selected_month,)
    ).fetchone()

    # -----------------------------------------------------
    # GET MONTHLY SPENDING
    # -----------------------------------------------------

    spending_row = connection.execute(
        """
        SELECT
            COALESCE(
                SUM(amount),
                0
            ) AS total

        FROM expenses

        WHERE strftime(
            '%Y-%m',
            created_at
        ) = ?
        """,
        (selected_month,)
    ).fetchone()

    # -----------------------------------------------------
    # BUDGET HISTORY
    # -----------------------------------------------------

    budget_history = connection.execute(
        """
        SELECT
            month,
            amount

        FROM budgets

        ORDER BY month DESC
        """
    ).fetchall()

    connection.close()

    # -----------------------------------------------------
    # CALCULATE VALUES
    # -----------------------------------------------------

    budget_amount = (
        float(budget_row["amount"])
        if budget_row
        else 0
    )

    total_spent = float(
        spending_row["total"]
    )

    remaining = (
        budget_amount
        - total_spent
    )

    # -----------------------------------------------------
    # BUDGET PERCENTAGE
    # -----------------------------------------------------

    if budget_amount > 0:

        budget_used_percentage = (
            total_spent
            / budget_amount
        ) * 100

    else:

        budget_used_percentage = 0

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    if budget_amount == 0:

        status = "Not Set"

    elif budget_used_percentage >= 100:

        status = "Over Budget"

    elif budget_used_percentage >= 80:

        status = "Near Limit"

    else:

        status = "On Track"

    # -----------------------------------------------------
    # RENDER PAGE
    # -----------------------------------------------------

    return render_template(
        "budget.html",

        budget_amount=budget_amount,

        total_spent=total_spent,

        remaining=remaining,

        budget_used_percentage=round(
            budget_used_percentage,
            1
        ),

        status=status,

        current_month=selected_month,

        budget_history=budget_history
    )


# =========================================================
# SET BUDGET
# =========================================================

@app.route(
    "/budgets",
    methods=["GET", "POST"]
)
def set_budget():

    if request.method == "GET":

        return redirect(
            "/dashboard"
        )

    data = request.get_json()

    if not data:

        return {
            "error":
                "Request body is required"
        }, 400

    month = data.get("month")
    amount = data.get("amount")

    if not month:

        return {
            "error":
                "Month is required"
        }, 400

    if amount is None:

        return {
            "error":
                "Budget amount is required"
        }, 400

    try:

        amount = float(amount)

    except (
        TypeError,
        ValueError
    ):

        return {
            "error":
                "Budget amount must be a number"
        }, 400

    if amount <= 0:

        return {
            "error":
                "Budget amount must be greater than 0"
        }, 400

    connection = get_db_connection()

    try:

        existing_budget = connection.execute(
            """
            SELECT id
            FROM budgets
            WHERE month = ?
            """,
            (month,)
        ).fetchone()

        if existing_budget:

            connection.execute(
                """
                UPDATE budgets
                SET amount = ?
                WHERE month = ?
                """,
                (
                    amount,
                    month
                )
            )

            connection.commit()

            budget_id = (
                existing_budget["id"]
            )

            connection.close()

            return {
                "message":
                    "Budget updated successfully",

                "budget_id":
                    budget_id,

                "month":
                    month,

                "amount":
                    amount
            }, 200

        cursor = connection.execute(
            """
            INSERT INTO budgets
            (month, amount)
            VALUES (?, ?)
            """,
            (
                month,
                amount
            )
        )

        connection.commit()

        budget_id = cursor.lastrowid

        connection.close()

        return {
            "message":
                "Budget set successfully",

            "budget_id":
                budget_id,

            "month":
                month,

            "amount":
                amount
        }, 201

    except Exception:

        connection.close()

        return {
            "error":
                "Unable to save budget"
        }, 500


# =========================================================
# BUDGET ANALYSIS
# =========================================================

@app.route(
    "/analytics/budget",
    methods=["GET"]
)
def get_budget_analysis():

    connection = get_db_connection()

    current_month = connection.execute(
        """
        SELECT strftime(
            '%Y-%m',
            'now'
        ) AS month
        """
    ).fetchone()["month"]

    budget = connection.execute(
        """
        SELECT amount
        FROM budgets
        WHERE month = ?
        """,
        (current_month,)
    ).fetchone()

    spending = connection.execute(
        """
        SELECT COALESCE(
            SUM(amount),
            0
        ) AS total_spending

        FROM expenses

        WHERE strftime(
            '%Y-%m',
            created_at
        ) = ?
        """,
        (current_month,)
    ).fetchone()

    connection.close()

    if not budget:

        return {
            "error":
                "Budget not set for current month"
        }, 404

    budget_amount = budget["amount"]

    total_spending = (
        spending["total_spending"]
    )

    remaining_budget = (
        budget_amount
        - total_spending
    )

    budget_used_percentage = (
        total_spending
        / budget_amount
    ) * 100

    if budget_used_percentage >= 100:

        status = "OVER_BUDGET"

    elif budget_used_percentage >= 80:

        status = "NEAR_LIMIT"

    else:

        status = "UNDER_BUDGET"

    return {
        "month":
            current_month,

        "budget":
            budget_amount,

        "total_spending":
            total_spending,

        "remaining_budget":
            remaining_budget,

        "budget_used_percentage":
            round(
                budget_used_percentage,
                2
            ),

        "status":
            status
    }


# =========================================================
# SPENDING INSIGHTS
# =========================================================

@app.route(
    "/analytics/insights",
    methods=["GET"]
)
def get_spending_insights():

    connection = get_db_connection()

    results = connection.execute(
        """
        SELECT

            category,

            COUNT(*) AS expense_count,

            SUM(amount) AS total_spending,

            AVG(amount) AS average_expense

        FROM expenses

        GROUP BY category

        ORDER BY total_spending DESC
        """
    ).fetchall()

    connection.close()

    if not results:

        return {
            "message":
                "No expense data available"
        }

    total_spending = sum(
        row["total_spending"]
        for row in results
    )

    insights = []

    for row in results:

        category_percentage = (
            row["total_spending"]
            / total_spending
        ) * 100

        insights.append({
            "category":
                row["category"],

            "expense_count":
                row["expense_count"],

            "total_spending":
                row["total_spending"],

            "average_expense":
                round(
                    row["average_expense"],
                    2
                ),

            "percentage_of_total":
                round(
                    category_percentage,
                    2
                )
        })

    top_category = (
        results[0]["category"]
    )

    return {
        "total_spending":
            total_spending,

        "top_spending_category":
            top_category,

        "insights":
            insights
    }


# =========================================================
# UPDATE EXPENSE - API
# =========================================================

@app.route(
    "/expenses/<int:expense_id>",
    methods=["PUT"]
)
def update_expense(expense_id):

    data = request.get_json()

    if not data:

        return {
            "error":
                "Request body is required"
        }, 400

    amount = data.get("amount")
    category = data.get("category")
    description = data.get("description")

    if amount is None:

        return {
            "error":
                "Amount is required"
        }, 400

    try:

        amount = float(amount)

    except (
        TypeError,
        ValueError
    ):

        return {
            "error":
                "Amount must be a number"
        }, 400

    if amount <= 0:

        return {
            "error":
                "Amount must be greater than 0"
        }, 400

    if (
        not category
        or not category.strip()
    ):

        return {
            "error":
                "Category is required"
        }, 400

    connection = get_db_connection()

    existing_expense = connection.execute(
        """
        SELECT *
        FROM expenses
        WHERE id = ?
        """,
        (expense_id,)
    ).fetchone()

    if not existing_expense:

        connection.close()

        return {
            "error":
                "Expense not found"
        }, 404

    connection.execute(
        """
        UPDATE expenses

        SET
            amount = ?,
            category = ?,
            description = ?

        WHERE id = ?
        """,
        (
            amount,
            category.strip(),
            description,
            expense_id
        )
    )

    connection.commit()

    connection.close()

    return {
        "message":
            "Expense updated successfully",

        "expense_id":
            expense_id
    }


# =========================================================
# DELETE EXPENSE - API
# =========================================================

@app.route(
    "/expenses/<int:expense_id>",
    methods=["DELETE"]
)
def delete_expense(expense_id):

    connection = get_db_connection()

    existing_expense = connection.execute(
        """
        SELECT *
        FROM expenses
        WHERE id = ?
        """,
        (expense_id,)
    ).fetchone()

    if not existing_expense:

        connection.close()

        return {
            "error":
                "Expense not found"
        }, 404

    connection.execute(
        """
        DELETE FROM expenses
        WHERE id = ?
        """,
        (expense_id,)
    )

    connection.commit()

    connection.close()

    return {
        "message":
            "Expense deleted successfully",

        "expense_id":
            expense_id
    }


# =========================================================
# AI ASK
# =========================================================

@app.route(
    "/ai/ask",
    methods=["POST"]
)
def ask_ai():

    # =====================================================
    # BASIC VALIDATION
    # =====================================================

    data = request.get_json(
        silent=True
    )

    if not data:

        return jsonify({
            "success": False,
            "error":
                "Invalid request."
        }), 400

    question = data.get(
        "question",
        ""
    ).strip()

    if not question:

        return jsonify({
            "success": False,
            "error":
                "Please enter a question."
        }), 400

    if len(question) > 500:

        return jsonify({
            "success": False,
            "error": (
                "Question is too long. "
                "Please keep it under "
                "500 characters."
            )
        }), 400

    # =====================================================
    # FINANCIAL QUESTION FILTER
    # =====================================================

    finance_keywords = [

        "spend",
        "spent",
        "spending",
        "expense",
        "expenses",
        "money",
        "budget",
        "saving",
        "save",
        "saved",
        "cost",
        "costs",
        "amount",
        "income",
        "financial",
        "finance",
        "category",
        "food",
        "shopping",
        "transport",
        "utilities",
        "entertainment",
        "travel",
        "medical",
        "health",
        "education",
        "rent",
        "bills",
        "forecast",
        "predict",
        "prediction",
        "month",
        "monthly",
        "increase",
        "increased",
        "decrease",
        "decreased",
        "reduce",
        "reduced",
        "cut",
        "lower",
        "change",
        "compare",
        "difference",
        "highest",
        "most",
        "unusual",
        "pattern",
        "what if"
    ]

    question_lower = question.lower()

    if not any(
        keyword in question_lower
        for keyword in finance_keywords
    ):

        return jsonify({
            "success": True,

            "answer": (
                "I can only answer "
                "questions related to "
                "your spending, "
                "expenses, budget, "
                "savings, categories, "
                "forecasts, and "
                "financial patterns."
            ),

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "unsupported"
        })

    # =====================================================
    # DETECT MONTHS
    # =====================================================

    month_names = {

        "january": "01",
        "february": "02",
        "march": "03",
        "april": "04",
        "may": "05",
        "june": "06",
        "july": "07",
        "august": "08",
        "september": "09",
        "october": "10",
        "november": "11",
        "december": "12"
    }

    detected_months = []

    for (
        month_name,
        month_number
    ) in month_names.items():

        if month_name in question_lower:

            detected_months.append(
                f"2026-{month_number}"
            )

    detected_months = sorted(
        set(detected_months)
    )

    start_month = None
    end_month = None

    if len(detected_months) >= 2:

        start_month = (
            detected_months[0]
        )

        end_month = (
            detected_months[1]
        )

    elif len(detected_months) == 1:

        start_month = (
            detected_months[0]
        )

    # =====================================================
    # DETECT INTENT
    # =====================================================

    intent = detect_question_intent(
        question
    )

    # =====================================================
    # FORCE WHAT-IF DETECTION
    # =====================================================

    what_if_phrases = [

        "what if",
        "if i reduce",
        "if i increase",
        "if i save",
        "how much can i save",
        "if i cut",
        "if i lower",
        "if i decrease"
    ]

    if any(
        phrase in question_lower
        for phrase in what_if_phrases
    ):

        intent = "what_if"

    # =====================================================
    # FORCE BROAD FINANCIAL QUESTION
    # =====================================================

    broad_financial_phrases = [

        "all my categories",
        "all my spending",
        "every financial detail",
        "all financial details",
        "every other financial detail",
        "everything about my spending"
    ]

    if any(
        phrase in question_lower
        for phrase in broad_financial_phrases
    ):

        intent = "summary"

    print(
        "Detected intent:",
        intent
    )

    # =====================================================
    # NATURAL SPENDING COMPARISON
    # =====================================================

    comparison_phrases = [

        "why did my spending",
        "why has my spending",
        "why is my spending",
        "spending increase",
        "spending increased",
        "spending decrease",
        "spending decreased",
        "spending change",
        "spending changed",
        "why did i spend more",
        "why did i spend less",
        "recently",
        "compared to",
        "compare",
        "difference between"
    ]

    if any(
        phrase in question_lower
        for phrase in comparison_phrases
    ):

        intent = "analysis"

        if "recently" in question_lower:

            monthly_data = (
                get_monthly_analytics()
                ["monthly_analytics"]
            )

            if len(monthly_data) >= 2:

                start_month = (
                    monthly_data[1]["month"]
                )

                end_month = (
                    monthly_data[0]["month"]
                )

    # =====================================================
    # CATEGORY + MONTH
    # =====================================================

    if intent == "category_monthly":

        categories = get_category_summary()

        monthly_data = (
            get_monthly_analytics()
            ["monthly_analytics"]
        )

        matched_category = None
        selected_month = None
        requested_category = None

        category_match = re.search(
            r"(?:spend|spent|spending|expense|expenses)"
            r"\s+on\s+([a-zA-Z]+)",
            question_lower
        )

        if category_match:

            requested_category = (
                category_match.group(1)
                .strip()
            )

            for category in categories:

                if (
                    category["category"].lower()
                    ==
                    requested_category.lower()
                ):

                    matched_category = category
                    break

        if not matched_category:

            return jsonify({
                "success": True,

                "answer": (
                    "I could not identify "
                    "a valid category and "
                    "month in your question."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "category_monthly"
            })

        if not start_month:

            return jsonify({
                "success": True,

                "answer": (
                    "Please specify "
                    "a valid month."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "category_monthly"
            })

        for item in monthly_data:

            if item["month"] == start_month:

                selected_month = item
                break

        month_display = (
            datetime.strptime(
                start_month,
                "%Y-%m"
            ).strftime("%B")
        )

        if not selected_month:

            return jsonify({
                "success": True,

                "answer": (
                    "I don't have "
                    "spending data "
                    f"available for "
                    f"{month_display}."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "category_monthly"
            })

        category_month = (
            get_category_spending_for_month(
                matched_category["category"],
                start_month
            )
        )

        return jsonify({
            "success": True,

            "answer": (
                f"You spent "
                f"₹{category_month:,.2f} "
                f"on "
                f"{matched_category['category']} "
                f"in {month_display}."
            ),

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "category_monthly",

            "category":
                matched_category["category"],

            "month":
                start_month,

            "amount":
                category_month
        })

    # =====================================================
    # MONTHLY SPENDING
    # =====================================================

    if intent == "monthly":

        if not start_month:

            return jsonify({
                "success": True,

                "answer": (
                    "Please specify a month, "
                    "for example: "
                    "'How much did I spend "
                    "in August?'"
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "monthly"
            })

        monthly_data = (
            get_monthly_analytics()
            ["monthly_analytics"]
        )

        selected_month = None

        for item in monthly_data:

            if item["month"] == start_month:

                selected_month = item
                break

        month_display = (
            datetime.strptime(
                start_month,
                "%Y-%m"
            ).strftime("%B")
        )

        if not selected_month:

            return jsonify({
                "success": True,

                "answer": (
                    "I don't have "
                    "spending data "
                    "available for "
                    f"{month_display}."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "monthly"
            })

        answer = (
            "You spent "
            f"₹{selected_month['total_spending']:,.2f} "
            f"in {month_display}."
        )

        return jsonify({
            "success": True,

            "answer":
                answer,

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "monthly",

            "month":
                start_month,

            "amount":
                selected_month[
                    "total_spending"
                ]
        })

    # =====================================================
    # SUMMARY
    # =====================================================

    if intent == "summary":

        summary = get_financial_summary()

        total_spending = summary.get(
            "total_spending",
            0
        )

        total_expenses = summary.get(
            "total_expenses",
            summary.get(
                "number_of_expenses",
                summary.get(
                    "expense_count",
                    0
                )
            )
        )

        average_expense = summary.get(
            "average_expense",
            0
        )

        answer = (
            "You have spent "
            f"₹{total_spending:,.2f} "
            "across "
            f"{total_expenses} "
            "expenses. "
            "Your average expense is "
            f"₹{average_expense:,.2f}."
        )

        return jsonify({
            "success": True,

            "answer":
                answer,

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "summary",

            "summary":
                summary
        })

    # =====================================================
    # CATEGORY SPECIFIC
    # =====================================================

    if intent == "category_specific":

        categories = get_category_summary()

        matched_category = None

        category_match = re.search(
            r"(?:spend|spent|spending|expense|expenses)"
            r"\s+on\s+([a-zA-Z]+)",
            question_lower
        )

        if category_match:

            requested_category = (
                category_match.group(1)
                .strip()
            )

            for category in categories:

                if (
                    category["category"].lower()
                    ==
                    requested_category.lower()
                ):

                    matched_category = category
                    break

            if not matched_category:

                return jsonify({
                    "success": True,

                    "answer": (
                        "I could not find "
                        "spending data for "
                        f"{requested_category.title()}."
                    ),

                    "model":
                        "backend-calculation",

                    "currency":
                        "INR",

                    "intent":
                        "category_specific",

                    "category":
                        requested_category.title()
                })

        else:

            return jsonify({
                "success": True,

                "answer": (
                    "I could not identify "
                    "the category you are "
                    "asking about."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "category_specific"
            })

        answer = (
            "You spent "
            f"₹{matched_category['total_spending']:,.2f} "
            "on "
            f"{matched_category['category']}."
        )

        return jsonify({
            "success": True,

            "answer":
                answer,

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "category_specific",

            "category":
                matched_category
        })

    # =====================================================
    # CATEGORY SUMMARY
    # =====================================================

    if intent == "category":

        categories = get_category_summary()

        if not categories:

            return jsonify({
                "success": True,

                "answer": (
                    "No category spending "
                    "data is available."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "category"
            })

        matched_category = None

        for category in categories:

            category_name = (
                category["category"]
            ).lower()

            if category_name in question_lower:

                matched_category = category
                break

        if matched_category:

            answer = (
                "You spent "
                f"₹{matched_category['total_spending']:,.2f} "
                "on "
                f"{matched_category['category']}."
            )

        else:

            highest_category = categories[0]

            answer = (
                "Your highest spending "
                "category is "
                f"{highest_category['category']} "
                "with "
                f"₹{highest_category['total_spending']:,.2f} "
                "spent."
            )

        return jsonify({
            "success": True,

            "answer":
                answer,

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "category",

            "categories":
                categories
        })

    # =====================================================
    # FORECAST
    # =====================================================

    if intent == "forecast":

        forecast_data = get_forecast()

        answer = (
            "Your predicted spending "
            "for the next month is "
            f"₹{forecast_data['predicted_spending']:,.2f}."
        )

        return jsonify({
            "success": True,

            "answer":
                answer,

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "forecast",

            "forecast":
                forecast_data
        })

    # =====================================================
    # SPENDING ANALYSIS
    # =====================================================

    if intent == "analysis":

        # -------------------------------------------------
        # SELECT MONTHS
        # -------------------------------------------------

        if "recently" in question_lower:

            monthly_data = (
                get_monthly_analytics()
                ["monthly_analytics"]
            )

            if len(monthly_data) < 2:

                return jsonify({
                    "success": True,

                    "answer": (
                        "There is not enough "
                        "monthly data to "
                        "compare spending."
                    ),

                    "model":
                        "backend-calculation",

                    "currency":
                        "INR",

                    "intent":
                        "analysis"
                })

            start_month = (
                monthly_data[1]["month"]
            )

            end_month = (
                monthly_data[0]["month"]
            )

        elif (
            not start_month
            or not end_month
        ):

            monthly_data = (
                get_monthly_analytics()
                ["monthly_analytics"]
            )

            if len(monthly_data) < 2:

                return jsonify({
                    "success": True,

                    "answer": (
                        "Please specify two "
                        "months to compare."
                    ),

                    "model":
                        "backend-calculation",

                    "currency":
                        "INR",

                    "intent":
                        "analysis"
                })

            start_month = (
                monthly_data[1]["month"]
            )

            end_month = (
                monthly_data[0]["month"]
            )

        # -------------------------------------------------
        # CHRONOLOGICAL ORDER
        # -------------------------------------------------

        if start_month > end_month:

            start_month, end_month = (
                end_month,
                start_month
            )

        # -------------------------------------------------
        # OVERALL DIFFERENCE
        # -------------------------------------------------

        difference_data = (
            get_month_difference(
                start_month,
                end_month
            )
        )

        difference = (
            difference_data["difference"]
        )

        # -------------------------------------------------
        # CATEGORY DIFFERENCES
        # -------------------------------------------------

        category_differences = (
            get_category_month_difference(
                start_month,
                end_month
            )
        )

        increased_categories = []

        decreased_categories = []

        for item in category_differences:

            category = item["category"]

            category_difference = (
                item["difference"]
            )

            if category_difference > 0:

                increased_categories.append(
                    f"{category}: "
                    f"+₹{category_difference:,.2f}"
                )

            elif category_difference < 0:

                decreased_categories.append(
                    f"{category}: "
                    f"-₹{abs(category_difference):,.2f}"
                )

        # -------------------------------------------------
        # BUILD ANSWER
        # -------------------------------------------------

        if difference < 0:

            answer = (
                "Your spending decreased "
                "from "
                f"{start_month} to "
                f"{end_month} by "
                f"₹{abs(difference):,.2f}."
            )

        elif difference > 0:

            answer = (
                "Your spending increased "
                "from "
                f"{start_month} to "
                f"{end_month} by "
                f"₹{difference:,.2f}."
            )

        else:

            answer = (
                "Your spending remained "
                "unchanged from "
                f"{start_month} to "
                f"{end_month}."
            )

        if decreased_categories:

            answer += (
                " Categories that decreased: "
                + ", ".join(
                    decreased_categories
                )
                + "."
            )

        if increased_categories:

            answer += (
                " Categories that increased: "
                + ", ".join(
                    increased_categories
                )
                + "."
            )

        return jsonify({
            "success": True,

            "answer":
                answer,

            "model":
                "backend-calculation",

            "currency":
                "INR",

            "intent":
                "analysis",

            "start_month":
                start_month,

            "end_month":
                end_month,

            "difference":
                difference,

            "category_differences":
                category_differences
        })

    # =====================================================
    # WHAT-IF ANALYSIS
    # =====================================================

    if intent == "what_if":

        what_if_params = (
            detect_what_if_parameters(
                question
            )
        )

        # -------------------------------------------------
        # INVALID / UNRECOGNIZED
        # -------------------------------------------------

        if what_if_params is None:

            return jsonify({
                "success": True,

                "answer": (
                    "I could not understand "
                    "the what-if scenario. "
                    "Please provide a percentage "
                    "or a saving amount."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "what_if"
            })

        # -------------------------------------------------
        # INVALID PERCENTAGE
        # -------------------------------------------------

        if what_if_params.get(
            "invalid_percentage"
        ):

            return jsonify({
                "success": True,

                "answer": (
                    "The percentage "
                    f"{what_if_params['percentage']:g}% "
                    "is invalid. Please use "
                    "a percentage between "
                    "0% and 100%."
                ),

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "what_if"
            })

        percentage = (
            what_if_params.get(
                "percentage"
            )
        )

        amount = (
            what_if_params.get(
                "monthly_saving"
            )
        )

        months = (
            what_if_params.get(
                "months"
            )
        )

        category = (
            what_if_params.get(
                "category"
            )
        )

        summary = get_financial_summary()

        # -------------------------------------------------
        # UNKNOWN CATEGORY
        # -------------------------------------------------

        if category:

            categories = get_category_summary()

            valid_category = any(
                item["category"].lower()
                ==
                category.lower()
                for item in categories
            )

            if not valid_category:

                return jsonify({
                    "success": True,

                    "answer": (
                        "I could not find "
                        "spending data for "
                        f"{category}."
                    ),

                    "model":
                        "backend-calculation",

                    "currency":
                        "INR",

                    "intent":
                        "what_if",

                    "category":
                        category
                })

        # -------------------------------------------------
        # CATEGORY-SPECIFIC %
        # -------------------------------------------------

        if (
            percentage is not None
            and category
        ):

            categories = get_category_summary()

            matched_category = None

            for item in categories:

                if (
                    item["category"].lower()
                    ==
                    category.lower()
                ):

                    matched_category = item
                    break

            if not matched_category:

                return jsonify({
                    "success": True,

                    "answer": (
                        "I could not find "
                        "spending data for "
                        f"{category}."
                    ),

                    "model":
                        "backend-calculation",

                    "currency":
                        "INR",

                    "intent":
                        "what_if",

                    "category":
                        category
                })

            category_spending = (
                matched_category[
                    "total_spending"
                ]
            )

            savings = (
                category_spending
                * (
                    abs(percentage)
                    / 100
                )
            )

            new_category_spending = (
                category_spending
                - savings
            )

            current_spending = (
                summary[
                    "total_spending"
                ]
            )

            new_total_spending = (
                current_spending
                - savings
            )

            answer = (
                f"If you reduce your "
                f"{category} spending by "
                f"{abs(percentage):g}%, "
                "you would save "
                f"₹{savings:,.2f}. "
                f"Your {category} spending "
                "would become approximately "
                f"₹{new_category_spending:,.2f}, "
                "and your overall spending "
                "would become approximately "
                f"₹{new_total_spending:,.2f}."
            )

            return jsonify({
                "success": True,

                "answer":
                    answer,

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "what_if",

                "category":
                    category,

                "percentage":
                    abs(percentage),

                "savings":
                    round(
                        savings,
                        2
                    ),

                "new_category_spending":
                    round(
                        new_category_spending,
                        2
                    ),

                "new_total_spending":
                    round(
                        new_total_spending,
                        2
                    )
            })

        # -------------------------------------------------
        # OVERALL PERCENTAGE
        # -------------------------------------------------

        if percentage is not None:

            current_spending = (
                summary[
                    "total_spending"
                ]
            )

            savings = (
                current_spending
                * (
                    abs(percentage)
                    / 100
                )
            )

            if percentage < 0:

                new_spending = (
                    current_spending
                    - savings
                )

                answer = (
                    "If you reduce your "
                    "spending by "
                    f"{abs(percentage):g}%, "
                    "your spending would be "
                    "approximately "
                    f"₹{new_spending:,.2f}, "
                    "saving "
                    f"₹{savings:,.2f}."
                )

            else:

                new_spending = (
                    current_spending
                    + savings
                )

                answer = (
                    "If your spending "
                    "increased by "
                    f"{percentage:g}%, "
                    "your total spending "
                    "would be approximately "
                    f"₹{new_spending:,.2f}."
                )

            return jsonify({
                "success": True,

                "answer":
                    answer,

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "what_if",

                "percentage":
                    abs(percentage),

                "savings":
                    round(
                        savings,
                        2
                    ),

                "new_spending":
                    round(
                        new_spending,
                        2
                    )
            })

        # -------------------------------------------------
        # AMOUNT + MONTHS
        # -------------------------------------------------

        if amount is not None:

            current_spending = (
                summary[
                    "total_spending"
                ]
            )

            if months is not None:

                total_saving = (
                    amount * months
                )

                new_spending = (
                    current_spending
                    - total_saving
                )

                if new_spending < 0:

                    new_spending = 0

                answer = (
                    "If you save "
                    f"₹{amount:,.2f} per month "
                    f"for {months} months, "
                    "you would save "
                    f"₹{total_saving:,.2f} "
                    "in total. "
                    "Your overall spending "
                    "would become approximately "
                    f"₹{new_spending:,.2f}."
                )

                return jsonify({
                    "success": True,

                    "answer":
                        answer,

                    "model":
                        "backend-calculation",

                    "currency":
                        "INR",

                    "intent":
                        "what_if",

                    "monthly_saving":
                        round(
                            amount,
                            2
                        ),

                    "months":
                        months,

                    "total_saving":
                        round(
                            total_saving,
                            2
                        ),

                    "new_spending":
                        round(
                            new_spending,
                            2
                        )
                })

            new_spending = (
                current_spending
                - amount
            )

            if new_spending < 0:

                new_spending = 0

            answer = (
                "If you save "
                f"₹{amount:,.2f}, "
                "your total spending "
                "would become approximately "
                f"₹{new_spending:,.2f}."
            )

            return jsonify({
                "success": True,

                "answer":
                    answer,

                "model":
                    "backend-calculation",

                "currency":
                    "INR",

                "intent":
                    "what_if",

                "saving":
                    round(
                        amount,
                        2
                    ),

                "new_spending":
                    round(
                        new_spending,
                        2
                    )
            })

    # =====================================================
    # FALLBACK
    # =====================================================

    return jsonify({
        "success": True,

        "answer": (
            "I could not determine "
            "the exact financial "
            "information you are asking for."
        ),

        "model":
            "backend-calculation",

        "currency":
            "INR",

        "intent":
            intent
    })


# =========================================================
# AI COPILOT
# =========================================================

@app.route(
    "/ai/copilot",
    methods=["POST"]
)
def ai_copilot():

    question = request.form.get(
        "question",
        ""
    ).strip()

    if not question:

        return redirect(
            "/dashboard"
        )

    with app.test_request_context(
        "/ai/ask",
        method="POST",
        json={
            "question": question
        }
    ):

        response = ask_ai()

    if isinstance(
        response,
        tuple
    ):

        response_data = (
            response[0].get_json()
        )

    else:

        response_data = (
            response.get_json()
        )

    print(
        "AI RESPONSE DATA:",
        response_data
    )

    # -----------------------------------------------------
    # DASHBOARD DATA
    # -----------------------------------------------------

    analytics = get_analytics()

    forecast = get_forecast()

    categories = (
        get_category_analytics()
        ["categories"]
    )

    monthly = (
        get_monthly_analytics()
        ["monthly_analytics"]
    )

    if monthly:

        max_spending = max(
            item["total_spending"]
            for item in monthly
        )

        for item in monthly:

            if max_spending > 0:

                item["bar_height"] = (
                    item["total_spending"]
                    / max_spending
                ) * 100

            else:

                item["bar_height"] = 0

    # -----------------------------------------------------
    # FINANCIAL INSIGHTS
    # -----------------------------------------------------

    insight_data = get_financial_insights()

    spending_patterns = (
        insight_data["spending_patterns"]
    )

    unusual_expenses = (
        insight_data["unusual_expenses"]
    )

    insights = (
        insight_data["insights"]
    )

    # -----------------------------------------------------
    # BUDGET
    # -----------------------------------------------------

    budget_response = get_budget_analysis()

    if isinstance(
        budget_response,
        tuple
    ):

        budget_response = {
            "month": "Current Month",
            "budget": 0,
            "total_spending": 0,
            "remaining_budget": 0,
            "budget_used_percentage": 0,
            "status": "NOT_SET"
        }

    # -----------------------------------------------------
    # RENDER DASHBOARD
    # -----------------------------------------------------

    return render_template(
        "dashboard.html",

        analytics=analytics,

        forecast=forecast,

        categories=categories,

        monthly=monthly,

        spending_patterns=spending_patterns,

        unusual_expenses=unusual_expenses,

        insights=insights,

        budget=budget_response,

        ai_response=(
            response_data.get("answer")
            or response_data.get("error")
        )
    )


# =========================================================
# AI INSIGHTS
# =========================================================

@app.route(
    "/ai/insights",
    methods=["GET"]
)
def ai_insights():

    insight_data = (
        get_financial_insights()
    )

    summary = (
        insight_data["summary"]
    )

    insights = (
        insight_data["insights"]
    )

    spending_patterns = (
        insight_data[
            "spending_patterns"
        ]
    )

    unusual_expenses = (
        insight_data[
            "unusual_expenses"
        ]
    )

    highest_category = next(
        (
            insight
            for insight in insights
            if insight["type"]
            ==
            "highest_spending_category"
        ),
        None
    )

    overall_trend = next(
        (
            insight
            for insight in insights
            if insight["type"]
            ==
            "overall_trend"
        ),
        None
    )

    forecast_insight = next(
        (
            insight
            for insight in insights
            if insight["type"]
            ==
            "forecast"
        ),
        None
    )

    answer = (
        "Your highest spending "
        "category is "
        f"{highest_category['category']} "
        "with "
        f"₹{highest_category['amount']:.2f} "
        "spent. "
        "Your spending increased "
        "from "
        f"{overall_trend['start_month']} "
        "to "
        f"{overall_trend['end_month']} "
        "by "
        f"₹{overall_trend['difference']:.2f}. "
        "Your predicted spending "
        "for next month is "
        f"₹{forecast_insight['predicted_spending']:.2f}."
    )

    return jsonify({
        "success": True,

        "answer":
            answer,

        "model":
            "backend-calculation",

        "currency":
            "INR",

        "summary":
            summary,

        "insights":
            insights,

        "spending_patterns":
            spending_patterns,

        "unusual_expenses":
            unusual_expenses
    })


# =========================================================
# EXPENSES PAGE
# =========================================================

@app.route(
    "/expenses/page",
    methods=["GET"]
)
def expenses_page():

    connection = (
        get_db_connection()
    )

    expenses = connection.execute(
        """
        SELECT
            id,
            amount,
            category,
            description,
            created_at

        FROM expenses

        ORDER BY created_at DESC
        """
    ).fetchall()

    connection.close()

    return render_template(
        "expenses.html",
        expenses=expenses
    )


# =========================================================
# CATEGORY NORMALIZATION
# =========================================================

def normalize_category(category):

    if not category:
        return category

    category_map = {
        "food": "Food",
        "shopping": "Shopping",
        "transport": "Transport",
        "entertainment": "Entertainment",
        "utilities": "Utilities",
        "travel": "Travel",
        "medical": "Medical",
        "health": "Health",
        "education": "Education",
        "rent": "Rent",
        "bills": "Bills"
    }

    category_clean = category.strip()

    return category_map.get(
        category_clean.lower(),
        category_clean
    )


# =========================================================
# ADD EXPENSE FROM FORM
# =========================================================

@app.route(
    "/expenses/add",
    methods=["POST"]
)
def add_expense_from_form():

    amount = request.form.get(
        "amount"
    )

    category = request.form.get(
        "category"
    )

    description = request.form.get(
        "description"
    )

    if not amount:

        return (
            "Amount is required",
            400
        )

    try:

        amount = float(amount)

    except (
        TypeError,
        ValueError
    ):

        return (
            "Amount must be a number",
            400
        )

    if amount <= 0:

        return (
            "Amount must be greater than 0",
            400
        )

    if (
        not category
        or not category.strip()
    ):

        return (
            "Category is required",
            400
        )

    category = normalize_category(
        category
    )

    connection = (
        get_db_connection()
    )

    connection.execute(
        """
        INSERT INTO expenses
        (amount, category, description)
        VALUES (?, ?, ?)
        """,
        (
            amount,
            category,
            description
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        "/expenses/page"
    )


# =========================================================
# DELETE EXPENSE FROM PAGE
# =========================================================

@app.route(
    "/expenses/delete/<int:expense_id>",
    methods=["POST"]
)
def delete_expense_from_page(
    expense_id
):

    connection = (
        get_db_connection()
    )

    expense = connection.execute(
        """
        SELECT id
        FROM expenses
        WHERE id = ?
        """,
        (expense_id,)
    ).fetchone()

    if expense is None:

        connection.close()

        return (
            "Expense not found",
            404
        )

    connection.execute(
        """
        DELETE FROM expenses
        WHERE id = ?
        """,
        (expense_id,)
    )

    connection.commit()

    connection.close()

    return redirect(
        "/expenses/page"
    )


# =========================================================
# EDIT EXPENSE PAGE
# =========================================================

@app.route(
    "/expenses/edit/<int:expense_id>",
    methods=["GET"]
)
def edit_expense_page(
    expense_id
):

    connection = (
        get_db_connection()
    )

    expense = connection.execute(
        """
        SELECT
            id,
            amount,
            category,
            description

        FROM expenses

        WHERE id = ?
        """,
        (expense_id,)
    ).fetchone()

    connection.close()

    if expense is None:

        return (
            "Expense not found",
            404
        )

    return render_template(
        "edit_expense.html",
        expense=expense
    )


# =========================================================
# UPDATE EXPENSE FROM PAGE
# =========================================================

@app.route(
    "/expenses/edit/<int:expense_id>",
    methods=["POST"]
)
def update_expense_from_page(
    expense_id
):

    amount = request.form.get(
        "amount"
    )

    category = request.form.get(
        "category"
    )

    description = request.form.get(
        "description"
    )

    if not amount:

        return (
            "Amount is required",
            400
        )

    try:

        amount = float(amount)

    except (
        TypeError,
        ValueError
    ):

        return (
            "Amount must be a number",
            400
        )

    if amount <= 0:

        return (
            "Amount must be greater than 0",
            400
        )

    if (
        not category
        or not category.strip()
    ):

        return (
            "Category is required",
            400
        )

    category = normalize_category(
        category
    )

    connection = (
        get_db_connection()
    )

    expense = connection.execute(
        """
        SELECT id
        FROM expenses
        WHERE id = ?
        """,
        (expense_id,)
    ).fetchone()

    if expense is None:

        connection.close()

        return (
            "Expense not found",
            404
        )

    connection.execute(
        """
        UPDATE expenses

        SET
            amount = ?,
            category = ?,
            description = ?

        WHERE id = ?
        """,
        (
            amount,
            category,
            description,
            expense_id
        )
    )

    connection.commit()

    connection.close()

    return redirect(
        "/expenses/page"
    )


# =========================================================
# RUN APPLICATION
# =========================================================

if __name__ == "__main__":

    app.run(
        debug=True
    )
