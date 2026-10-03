import sqlite3
import re

from pathlib import Path


# =========================
# DATABASE PATH
# =========================

DATABASE = (
    Path(__file__).resolve().parent.parent
    / "smartspend.db"
)


# =========================
# FINANCIAL SUMMARY
# =========================

def get_financial_summary():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(amount), 0),
            COUNT(*),
            COALESCE(AVG(amount), 0)
        FROM expenses
    """)

    total_spending, expense_count, average_expense = cursor.fetchone()

    connection.close()

    return {
        "total_spending": round(total_spending, 2),
        "expense_count": expense_count,
        "average_expense": round(average_expense, 2)
    }


# =========================
# CATEGORY SUMMARY
# =========================

def get_category_summary():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            category,
            SUM(amount) AS total_spending
        FROM expenses
        GROUP BY category
        ORDER BY total_spending DESC
    """)

    rows = cursor.fetchall()

    connection.close()

    return [
        {
            "category": row[0],
            "total_spending": round(row[1], 2)
        }
        for row in rows
    ]


# =========================
# MONTHLY SUMMARY
# =========================

def get_monthly_summary():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            strftime('%Y-%m', created_at) AS month,
            SUM(amount) AS total_spending
        FROM expenses
        GROUP BY month
        ORDER BY month ASC
    """)

    rows = cursor.fetchall()

    connection.close()

    return [
        {
            "month": row[0],
            "total_spending": round(row[1], 2)
        }
        for row in rows
    ]


# =========================
# SPENDING PATTERNS
# =========================

def get_spending_patterns():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    # =========================
    # CATEGORY-WISE SPENDING
    # =========================

    cursor.execute("""
        SELECT
            category,
            COUNT(*) AS expense_count,
            SUM(amount) AS total_spending,
            AVG(amount) AS average_expense
        FROM expenses
        GROUP BY category
        ORDER BY total_spending DESC
    """)

    category_rows = cursor.fetchall()

    # =========================
    # MONTHLY SPENDING
    # =========================

    cursor.execute("""
        SELECT
            strftime('%Y-%m', created_at) AS month,
            SUM(amount) AS total_spending
        FROM expenses
        GROUP BY month
        ORDER BY month ASC
    """)

    monthly_rows = cursor.fetchall()

    connection.close()

    patterns = []

    # =========================
    # CATEGORY SPENDING PATTERN
    # =========================

    if category_rows:

        total_spending = sum(
            row[2]
            for row in category_rows
        )

        if total_spending > 0:

            highest_category = category_rows[0]

            highest_percentage = (
                highest_category[2]
                / total_spending
            ) * 100

            patterns.append({
                "type": "dominant_category",
                "category": highest_category[0],
                "amount": round(
                    highest_category[2],
                    2
                ),
                "percentage": round(
                    highest_percentage,
                    2
                )
            })

            # =========================
            # MAJOR CATEGORIES
            # =========================

            major_categories = []

            for row in category_rows:

                percentage = (
                    row[2]
                    / total_spending
                ) * 100

                if percentage >= 20:

                    major_categories.append({
                        "category": row[0],
                        "percentage": round(
                            percentage,
                            2
                        ),
                        "amount": round(
                            row[2],
                            2
                        )
                    })

            if major_categories:

                patterns.append({
                    "type": "major_categories",
                    "categories": major_categories
                })

    # =========================
    # MONTHLY SPENDING PATTERN
    # =========================

    if len(monthly_rows) >= 2:

        latest_month = monthly_rows[-1]
        previous_month = monthly_rows[-2]

        latest_spending = latest_month[1]
        previous_spending = previous_month[1]

        difference = (
            latest_spending
            - previous_spending
        )

        if previous_spending != 0:

            percentage_change = (
                difference
                / previous_spending
            ) * 100

            patterns.append({
                "type": "monthly_change",
                "previous_month": previous_month[0],
                "latest_month": latest_month[0],
                "difference": round(
                    difference,
                    2
                ),
                "percentage_change": round(
                    percentage_change,
                    2
                )
            })

    return patterns


# =========================
# UNUSUAL EXPENSE DETECTION
# =========================

def get_unusual_expenses():

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            id,
            amount,
            category,
            description,
            created_at
        FROM expenses
        ORDER BY amount ASC
    """)

    rows = cursor.fetchall()

    connection.close()

    if len(rows) < 4:
        return []

    amounts = [
        row[1]
        for row in rows
    ]

    # =========================
    # IQR OUTLIER DETECTION
    # =========================

    n = len(amounts)

    q1_position = (n + 1) / 4
    q3_position = 3 * (n + 1) / 4

    def percentile(position):

        lower = int(position) - 1
        upper = lower + 1

        if upper >= n:
            return amounts[lower]

        fraction = (
            position
            - int(position)
        )

        return (
            amounts[lower]
            + fraction * (
                amounts[upper]
                - amounts[lower]
            )
        )

    q1 = percentile(q1_position)
    q3 = percentile(q3_position)

    iqr = q3 - q1

    upper_limit = q3 + (1.5 * iqr)

    unusual_expenses = []

    for row in rows:

        if row[1] > upper_limit:

            unusual_expenses.append({
                "id": row[0],
                "amount": round(
                    row[1],
                    2
                ),
                "category": row[2],
                "description": row[3],
                "created_at": row[4],
                "threshold": round(
                    upper_limit,
                    2
                )
            })

    return unusual_expenses


# =========================
# FORECAST
# =========================

def get_forecast():

    from ml.predict import predict_next_month

    prediction = predict_next_month()

    return {
        "predicted_spending": round(
            float(prediction),
            2
        ),
        "currency": "INR"
    }


# =========================
# FINANCIAL INSIGHTS
# =========================

def get_financial_insights():

    summary = get_financial_summary()
    categories = get_category_summary()
    monthly = get_monthly_summary()
    forecast = get_forecast()

    spending_patterns = get_spending_patterns()
    unusual_expenses = get_unusual_expenses()

    insights = []

    # =========================
    # SPENDING PATTERN INSIGHTS
    # =========================

    for pattern in spending_patterns:

        # =========================
        # DOMINANT CATEGORY
        # =========================

        if pattern["type"] == "dominant_category":

            insights.append({
                "type": "dominant_category_insight",
                "message": (
                    f"{pattern['category']} accounts for "
                    f"{pattern['percentage']}% of your "
                    "total spending."
                )
            })

        # =========================
        # MONTHLY CHANGE
        # =========================

        elif pattern["type"] == "monthly_change":

            if pattern["difference"] < 0:

                insights.append({
                    "type": "spending_reduction",
                    "message": (
                        f"Your spending decreased by "
                        f"₹{abs(pattern['difference']):,.2f} "
                        f"({abs(pattern['percentage_change'])}%) "
                        f"from {pattern['previous_month']} "
                        f"to {pattern['latest_month']}."
                    )
                })

            elif pattern["difference"] > 0:

                insights.append({
                    "type": "spending_increase",
                    "message": (
                        f"Your spending increased by "
                        f"₹{pattern['difference']:,.2f} "
                        f"({pattern['percentage_change']}%) "
                        f"from {pattern['previous_month']} "
                        f"to {pattern['latest_month']}."
                    )
                })

    # =========================
    # HIGHEST SPENDING CATEGORY
    # =========================

    if categories:

        highest_category = categories[0]

        insights.append({
            "type": "highest_spending_category",
            "category": highest_category["category"],
            "amount": highest_category["total_spending"]
        })

    # =========================
    # OVERALL SPENDING TREND
    # =========================

    if len(monthly) >= 2:

        first_month = monthly[0]
        latest_month = monthly[-1]

        difference = round(
            latest_month["total_spending"]
            - first_month["total_spending"],
            2
        )

        insights.append({
            "type": "overall_trend",
            "start_month": first_month["month"],
            "end_month": latest_month["month"],
            "difference": difference
        })

    # =========================
    # FORECAST INSIGHT
    # =========================

    insights.append({
        "type": "forecast",
        "predicted_spending": forecast[
            "predicted_spending"
        ]
    })

    # =========================
    # UNUSUAL EXPENSE INSIGHT
    # =========================

    if unusual_expenses:

        insights.append({
            "type": "unusual_expenses",
            "count": len(unusual_expenses),
            "message": (
                f"{len(unusual_expenses)} unusual "
                "expense(s) were detected based on "
                "your spending pattern."
            )
        })

    else:

        insights.append({
            "type": "unusual_expenses",
            "count": 0,
            "message": (
                "No unusually high expenses were "
                "detected based on your current "
                "spending pattern."
            )
        })

    # =========================
    # FINAL RESPONSE
    # =========================

    return {
        "summary": summary,
        "insights": insights,
        "spending_patterns": spending_patterns,
        "unusual_expenses": unusual_expenses
    }


# =========================
# MONTH DIFFERENCE
# =========================

def get_month_difference(
    start_month,
    end_month
):

    monthly = get_monthly_summary()

    start_spending = next(
        (
            item["total_spending"]
            for item in monthly
            if item["month"] == start_month
        ),
        None
    )

    end_spending = next(
        (
            item["total_spending"]
            for item in monthly
            if item["month"] == end_month
        ),
        None
    )

    if (
        start_spending is None
        or end_spending is None
    ):
        return None

    return {
        "start_month": start_month,
        "end_month": end_month,
        "start_spending": start_spending,
        "end_spending": end_spending,
        "difference": round(
            end_spending
            - start_spending,
            2
        )
    }


# =========================
# CATEGORY MONTH DIFFERENCE
# =========================

def get_category_month_difference(
    start_month,
    end_month
):

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            category,

            SUM(
                CASE
                    WHEN strftime('%Y-%m', created_at) = ?
                    THEN amount
                    ELSE 0
                END
            ) AS start_spending,

            SUM(
                CASE
                    WHEN strftime('%Y-%m', created_at) = ?
                    THEN amount
                    ELSE 0
                END
            ) AS end_spending

        FROM expenses

        WHERE strftime('%Y-%m', created_at)
        IN (?, ?)

        GROUP BY category

        ORDER BY category
    """, (
        start_month,
        end_month,
        start_month,
        end_month
    ))

    rows = cursor.fetchall()

    connection.close()

    return [
        {
            "category": row[0],

            "start_spending": round(
                row[1] or 0,
                2
            ),

            "end_spending": round(
                row[2] or 0,
                2
            ),

            "difference": round(
                (row[2] or 0)
                - (row[1] or 0),
                2
            )
        }
        for row in rows
    ]

def get_category_spending_for_month(
    category,
    month
):

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT
            COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE category = ?
        AND strftime('%Y-%m', created_at) = ?
    """, (
        category,
        month
    ))

    result = cursor.fetchone()

    connection.close()

    return round(
        result[0] or 0,
        2
    )


# =========================
# BUILD FINANCIAL CONTEXT
# =========================

def build_financial_context(
    start_month=None,
    end_month=None
):

    monthly_difference = None
    category_differences = []

    # =========================
    # MONTH COMPARISON
    # =========================

    if start_month and end_month:

        monthly_difference = get_month_difference(
            start_month,
            end_month
        )

        category_differences = (
            get_category_month_difference(
                start_month,
                end_month
            )
        )

    summary = get_financial_summary()
    categories = get_category_summary()
    monthly = get_monthly_summary()
    forecast = get_forecast()

    insight_data = get_financial_insights()

    spending_patterns = (
        insight_data["spending_patterns"]
    )

    unusual_expenses = (
        insight_data["unusual_expenses"]
    )

    # =========================
    # BASE CONTEXT
    # =========================

    context = f"""
FINANCIAL SUMMARY

Total spending across all available months:

₹{summary['total_spending']}

Number of expenses across all available months:

{summary['expense_count']}

Average expense across all available expenses:

₹{summary['average_expense']}

"""

    # =========================
    # CATEGORY SPENDING
    # =========================

    context += "\nCATEGORY SPENDING\n"

    for item in categories:

        context += (
            f"{item['category']}: "
            f"₹{item['total_spending']}\n"
        )

    # =========================
    # MONTHLY SPENDING
    # =========================

    context += "\nMONTHLY SPENDING\n"

    for item in monthly:

        context += (
            f"{item['month']}: "
            f"₹{item['total_spending']}\n"
        )

    # =========================
    # MONTHLY DIFFERENCE
    # =========================

    if monthly_difference:

        context += (
            "\nCALCULATED MONTHLY DIFFERENCE\n"

            f"{monthly_difference['start_month']}: "
            f"₹{monthly_difference['start_spending']}\n"

            f"{monthly_difference['end_month']}: "
            f"₹{monthly_difference['end_spending']}\n"

            f"Difference: "
            f"₹{monthly_difference['difference']}\n"
        )

    # =========================
    # CATEGORY-WISE DIFFERENCE
    # =========================

    if category_differences:

        context += (
            "\nCATEGORY-WISE MONTHLY DIFFERENCE\n"
        )

        for item in category_differences:

            context += (
                f"{item['category']}: "
                f"{item['start_spending']} → "
                f"{item['end_spending']} "
                f"(Difference: "
                f"{item['difference']})\n"
            )

    # =========================
    # FORECAST
    # =========================

    context += (
        "\nFORECAST\n"

        f"Next month predicted spending: "
        f"₹{forecast['predicted_spending']}\n"
    )

    # =========================
    # SPENDING PATTERNS
    # =========================

    context += "\nSPENDING PATTERNS\n"

    for pattern in spending_patterns:

        if pattern["type"] == "dominant_category":

            context += (
                f"Dominant category: "
                f"{pattern['category']} "
                f"(₹{pattern['amount']}, "
                f"{pattern['percentage']}% of total spending)\n"
            )

        elif pattern["type"] == "major_categories":

            context += (
                "Major spending categories:\n"
            )

            for category in pattern["categories"]:

                context += (
                    f"- {category['category']}: "
                    f"₹{category['amount']} "
                    f"({category['percentage']}%)\n"
                )

        elif pattern["type"] == "monthly_change":

            context += (
                f"Monthly spending change from "
                f"{pattern['previous_month']} to "
                f"{pattern['latest_month']}: "
                f"₹{pattern['difference']} "
                f"({pattern['percentage_change']}%)\n"
            )

    # =========================
    # UNUSUAL EXPENSES
    # =========================

    context += "\nUNUSUAL EXPENSES\n"

    if unusual_expenses:

        for expense in unusual_expenses:

            context += (
                f"ID: {expense['id']}, "
                f"Category: {expense['category']}, "
                f"Amount: ₹{expense['amount']}, "
                f"Description: "
                f"{expense['description'] or 'No description'}\n"
            )

    else:

        context += (
            "No unusually high expenses detected "
            "based on the current spending pattern.\n"
        )

    # =========================
    # FINANCIAL INSIGHTS
    # =========================

    context += "\nFINANCIAL INSIGHTS\n"

    for insight in insight_data["insights"]:

        if insight["type"] == "highest_spending_category":

            context += (
                f"Highest spending category: "
                f"{insight['category']} "
                f"(₹{insight['amount']})\n"
            )

        elif insight["type"] == "overall_trend":

            context += (
                f"Spending change from "
                f"{insight['start_month']} to "
                f"{insight['end_month']}: "
                f"₹{insight['difference']}\n"
            )

        elif insight["type"] == "forecast":

            context += (
                f"Predicted next month spending: "
                f"₹{insight['predicted_spending']}\n"
            )

        elif insight["type"] in [
            "dominant_category_insight",
            "spending_reduction",
            "spending_increase"
        ]:

            context += (
                f"{insight['message']}\n"
            )

        elif insight["type"] == "unusual_expenses":

            context += (
                f"{insight['message']}\n"
            )

    return context


# =========================
# BASIC WHAT-IF CALCULATION
# =========================

def calculate_what_if(
    monthly_saving,
    months
):

    monthly_saving = float(
        monthly_saving
    )

    months = int(months)

    total_saving = (
        monthly_saving
        * months
    )

    return {
        "monthly_saving": round(
            monthly_saving,
            2
        ),
        "months": months,
        "total_saving": round(
            total_saving,
            2
        )
    }


# =========================
# CATEGORY SPENDING
# =========================

def get_category_spending(category):

    connection = sqlite3.connect(DATABASE)
    cursor = connection.cursor()

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM expenses
        WHERE LOWER(category) = LOWER(?)
    """, (category,))

    spending = cursor.fetchone()[0]

    connection.close()

    return round(
        spending,
        2
    )


# =========================
# CATEGORY WHAT-IF
# =========================

def calculate_category_what_if(
    category,
    monthly_reduction,
    months
):

    category_spending = (
        get_category_spending(category)
    )

    monthly_reduction = float(
        monthly_reduction
    )

    months = int(months)

    total_saving = (
        monthly_reduction
        * months
    )

    return {
        "category": category,
        "current_spending": category_spending,
        "monthly_reduction": round(
            monthly_reduction,
            2
        ),
        "months": months,
        "total_saving": round(
            total_saving,
            2
        )
    }


# =========================
# DETECT WHAT-IF CATEGORY
# =========================

def detect_what_if_category(question):

    question_lower = question.lower()

    match = re.search(
        r"\b([a-zA-Z]+)\s+spending\b",
        question_lower
    )

    if match:

        category = match.group(1).strip()

        generic_words = [
            "overall",
            "total",
            "monthly",
            "my",
            "your"
        ]

        if category in generic_words:
            return None

        return category.title()

    return None


# =========================
# DETECT WHAT-IF PARAMETERS
# =========================

def detect_what_if_parameters(question):

    question_lower = question.lower()

    # =========================
    # CATEGORY DETECTION
    # =========================

    category_keywords = [
        "food",
        "shopping",
        "transport",
        "entertainment",
        "utilities",
        "travel",
        "medical",
        "health",
        "education",
        "rent",
        "bills"
    ]

    detected_category = None

    for category in category_keywords:

        if re.search(
            rf"\b{re.escape(category)}\b",
            question_lower
        ):

            detected_category = (
                category.title()
            )

            break

    # =========================
    # PERCENTAGE DETECTION
    # =========================

    percentage_match = re.search(
        r"(-?\d+(?:\.\d+)?)\s*%",
        question_lower
    )

    if percentage_match:

        percentage = float(
            percentage_match.group(1)
        )

        # Invalid percentage

        if percentage < 0 or percentage > 100:

            return {
                "invalid_percentage": True,
                "percentage": percentage,
                "category": detected_category
            }

        # Reduction phrases

        if any(
            phrase in question_lower
            for phrase in [
                "reduce",
                "decrease",
                "cut",
                "lower",
                "spend less"
            ]
        ):

            percentage = -percentage

        return {
            "percentage": percentage,
            "category": detected_category
        }

    # =========================
    # AMOUNT + MONTHS
    # =========================

    amount_match = re.search(
        r"(?:₹|rs\.?|inr)?\s*(\d+(?:,\d{3})*(?:\.\d+)?)",
        question_lower
    )

    months_match = re.search(
        r"(\d+)\s*months?",
        question_lower
    )

    if (
        not amount_match
        or not months_match
    ):

        return None

    amount = float(
        amount_match.group(1).replace(
            ",",
            ""
        )
    )

    months = int(
        months_match.group(1)
    )

    return {
        "monthly_saving": amount,
        "months": months,
        "category": detected_category
    }


# =========================
# QUESTION INTENT DETECTION
# =========================


def detect_question_intent(question):

    question_lower = question.lower()

    # =========================
    # MONTHS
    # =========================

    months = [
        "january",
        "february",
        "march",
        "april",
        "may",
        "june",
        "july",
        "august",
        "september",
        "october",
        "november",
        "december"
    ]

    # =========================
    # SPENDING PHRASES
    # =========================

    spending_phrases = [
        "how much",
        "spent",
        "spending",
        "expense",
        "expenses"
    ]

    # =========================
    # WHAT-IF
    # =========================

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

        return "what_if"

    # =========================
    # FORECAST
    # =========================

    if any(
        phrase in question_lower
        for phrase in [
            "forecast",
            "predict",
            "predicted",
            "next month"
        ]
    ):

        return "forecast"

    # =========================
    # SPENDING ANALYSIS
    # =========================

    if any(
        phrase in question_lower
        for phrase in [
            "why did",
            "why has",
            "reason",
            "increase",
            "decrease"
        ]
    ):

        return "analysis"

    # =========================
    # CATEGORY LIST
    # =========================

    categories = [
        "food",
        "shopping",
        "transport",
        "entertainment",
        "utilities",
        "travel",
        "medical",
        "health",
        "education",
        "rent",
        "bills"
    ]

    has_month = any(
        month in question_lower
        for month in months
    )

    has_category = any(
        category in question_lower
        for category in categories
    )

    # =========================
    # CATEGORY + MONTH
    # =========================

    if (
        has_month
        and has_category
        and any(
            phrase in question_lower
            for phrase in spending_phrases
        )
        and any(
            phrase in question_lower
            for phrase in [
                "spend on",
                "spent on",
                "spending on",
                "expense on",
                "expenses on"
            ]
        )
    ):

        return "category_monthly"

    # =========================
    # MONTHLY SPENDING
    # =========================

    if (
        has_month
        and any(
            phrase in question_lower
            for phrase in spending_phrases
        )
    ):

        return "monthly"

    # =========================
    # CATEGORY SPECIFIC
    # =========================

    if any(
        phrase in question_lower
        for phrase in [
            "spend on",
            "spent on",
            "spending on",
            "expense on",
            "expenses on"
        ]
    ):

        return "category_specific"

    # =========================
    # CATEGORY ANALYSIS
    # =========================

    if any(
        phrase in question_lower
        for phrase in [
            "which category",
            "highest category",
            "most spending"
        ]
    ):

        return "category"

    # =========================
    # BROAD FINANCIAL QUESTION
    # =========================

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

        return "summary"

    # =========================
    # TOTAL SPENDING
    # =========================

    if any(
        phrase in question_lower
        for phrase in [
            "how much",
            "total spending",
            "total spent",
            "overall spending"
        ]
    ):

        return "summary"

    # =========================
    # GENERAL
    # =========================

    return "general"
