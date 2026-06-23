# Import Flask tools for creating the web app, rendering HTML, reading form data, and returning files.
from flask import Flask, Response, render_template, request


# Create the Flask application object.
app = Flask(__name__)


# Store the expense choices that will appear on the form.
EXPENSE_CATEGORIES = [
    # Each category has a form-friendly key and a user-friendly label.
    {"key": "housing", "label": "Housing"},
    {"key": "groceries", "label": "Groceries"},
    {"key": "utilities", "label": "Utilities"},
    {"key": "transportation", "label": "Transportation"},
    {"key": "insurance", "label": "Insurance"},
    {"key": "debt", "label": "Debt payments"},
    {"key": "entertainment", "label": "Entertainment"},
    {"key": "savings", "label": "Savings"},
    {"key": "other", "label": "Other"},
]


# Convert text from the form into a rounded money number.
def parse_money(value):
    # float() changes text like "25.50" into a number, then round() keeps cents tidy.
    return round(float(value), 2)


# Format a number as money text.
def format_money(value):
    # The :.2f part always shows two decimal places.
    return f"${value:.2f}"


# Choose an insight message based on how much income has been used.
def get_budget_insight(percent_used):
    # Spending the full income, or more, needs the strongest warning.
    if percent_used >= 100:
        return {
            "title": "Income fully used",
            "message": "Your expenses use all of your income. Review the largest categories first and look for anything that can be reduced.",
            "tone": "danger",
        }

    # Around half the income is a good checkpoint.
    if percent_used >= 50:
        return {
            "title": "Halfway checkpoint",
            "message": "You have used at least half of your income. This can still be fine, but keep an eye on flexible spending.",
            "tone": "warning",
        }

    # Thirty percent is a healthy early signal.
    if percent_used >= 30:
        return {
            "title": "Spending is building",
            "message": "You have used at least 30% of your income. You still have room, but it is a good time to track upcoming expenses.",
            "tone": "notice",
        }

    # Below thirty percent is a comfortable range.
    return {
        "title": "Plenty of room",
        "message": "Your entered expenses are under 30% of your income. Keep tracking so the picture stays accurate.",
        "tone": "good",
    }


# Calculate the budget summary from the submitted form values.
def calculate_budget(form):
    # Keep validation messages here so the template can show them to the user.
    errors = []

    # Read the income field and remove extra spaces.
    income_text = form.get("monthly_income", "").strip()

    try:
        # Try to convert the income text into a money number.
        monthly_income = parse_money(income_text)
    except ValueError:
        # Show this error if the user typed something that is not a number.
        errors.append("Please enter your monthly salary or wage as a number.")

        # Use zero so the rest of the calculations can still run safely.
        monthly_income = 0

    # Income should be positive because the app subtracts expenses from it.
    if monthly_income <= 0:
        errors.append("Monthly salary or wage must be greater than zero.")

    # Store only the expense categories the user turned on.
    selected_expenses = []

    # Check each possible expense category from the list above.
    for category in EXPENSE_CATEGORIES:
        # Get the short key, such as "housing" or "groceries".
        key = category["key"]

        # A checkbox sends "on" only when the user checked it.
        enabled = form.get(f"enabled_{key}") == "on"

        # Read the amount field that belongs to this category.
        amount_text = form.get(f"amount_{key}", "").strip()

        # Start at zero in case this category is not enabled.
        amount = 0

        # Only validate and save the amount if the user enabled this expense.
        if enabled:
            try:
                # Convert the amount text into a money number.
                amount = parse_money(amount_text)
            except ValueError:
                # Show this error if the amount is missing or not numeric.
                errors.append(f"{category['label']} amount must be a number.")

                # Use zero so calculations do not crash.
                amount = 0

            # Negative expenses are not allowed in this simple tracker.
            if amount < 0:
                errors.append(f"{category['label']} amount cannot be negative.")

            # Add this enabled category to the expense breakdown.
            selected_expenses.append(
                {
                    # Save the key in case the template or future code needs it.
                    "key": key,

                    # Save the readable label for display.
                    "label": category["label"],

                    # Never let a negative value lower the total.
                    "amount": max(amount, 0),
                }
            )

    # Add all enabled expense amounts together.
    total_expenses = round(sum(expense["amount"] for expense in selected_expenses), 2)

    # Subtract expenses from income to show what is left.
    remaining_money = round(monthly_income - total_expenses, 2)

    # Calculate the percent of income used, avoiding division by zero.
    percent_used = round((total_expenses / monthly_income) * 100, 1) if monthly_income else 0

    # Keep the progress bar width between 0 and 100 percent.
    progress_width = min(percent_used, 100)

    # Choose a helpful message based on the percent used.
    insight = get_budget_insight(percent_used)

    # Return one dictionary with everything the template needs to show the result.
    return {
        # List of validation messages.
        "errors": errors,

        # Monthly income as a number.
        "monthly_income": monthly_income,

        # Enabled expense categories and their amounts.
        "selected_expenses": selected_expenses,

        # Combined expense total.
        "total_expenses": total_expenses,

        # Income minus expenses.
        "remaining_money": remaining_money,

        # Percent of monthly income spent.
        "percent_used": percent_used,

        # Progress bar width for the template.
        "progress_width": progress_width,

        # Helpful spending insight for the user.
        "insight": insight,
    }


# Create plain text lines for the budget summary.
def create_summary_lines(result):
    # Start with the main totals.
    lines = [
        "Expense Tracker Summary",
        "-----------------------",
        f"Monthly income: {format_money(result['monthly_income'])}",
        f"Total expenses: {format_money(result['total_expenses'])}",
        f"Money remaining: {format_money(result['remaining_money'])}",
        f"Income used: {result['percent_used']}%",
        "",
        "Expense breakdown:",
    ]

    # Add each selected expense to the summary.
    for expense in result["selected_expenses"]:
        lines.append(f"- {expense['label']}: {format_money(expense['amount'])}")

    # Show a helpful message if no expense categories were selected.
    if not result["selected_expenses"]:
        lines.append("- No expenses selected.")

    # Give the finished list of lines back to the caller.
    return lines


# Escape special characters so text is safe inside a PDF string.
def escape_pdf_text(value):
    # Backslashes and parentheses have special meaning in PDF content streams.
    return str(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


# Build a simple PDF file from summary lines.
def create_pdf_bytes(lines):
    # Store the commands that draw text onto the PDF page.
    text_commands = ["BT", "/F1 12 Tf", "72 760 Td", "16 TL"]

    # Add each summary line as a separate line of PDF text.
    for line in lines:
        text_commands.append(f"({escape_pdf_text(line)}) Tj")
        text_commands.append("T*")

    # End the PDF text block.
    text_commands.append("ET")

    # Encode the text drawing commands as PDF stream bytes.
    content_stream = "\n".join(text_commands).encode("latin-1", errors="replace")

    # Define the core PDF objects.
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /Length "
        + str(len(content_stream)).encode("ascii")
        + b" >>\nstream\n"
        + content_stream
        + b"\nendstream",
    ]

    # Start the PDF file with its header.
    pdf = bytearray(b"%PDF-1.4\n")

    # Track where each object starts so the PDF can find them later.
    offsets = [0]

    # Write each PDF object into the file.
    for index, pdf_object in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(pdf_object)
        pdf.extend(b"\nendobj\n")

    # Mark where the cross-reference table begins.
    xref_start = len(pdf)

    # Write the cross-reference table.
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")

    # Write one offset row for each object.
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))

    # Write the PDF trailer and finish the file.
    pdf.extend(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode(
            "ascii"
        )
    )

    # Return the finished PDF as bytes.
    return bytes(pdf)


# Build a text file from summary lines.
def create_text_bytes(lines):
    # Join the summary lines with line breaks and encode them for download.
    return "\n".join(lines).encode("utf-8")


# Create a downloadable summary file from the submitted budget form.
@app.route("/download-summary", methods=["POST"])
def download_summary():
    # Calculate the budget using the current form values.
    result = calculate_budget(request.form)

    # If the form has errors, show the normal page with those errors.
    if result["errors"]:
        return render_template(
            "index.html",
            categories=EXPENSE_CATEGORIES,
            form=request.form,
            result=result,
        )

    # Turn the budget result into readable summary lines.
    summary_lines = create_summary_lines(result)

    # Read the selected download format from the dropdown.
    download_format = request.form.get("download_format", "pdf")

    # Return a text file if the user selected TXT.
    if download_format == "txt":
        text_bytes = create_text_bytes(summary_lines)

        return Response(
            text_bytes,
            mimetype="text/plain",
            headers={"Content-Disposition": "attachment; filename=expense-summary.txt"},
        )

    # Otherwise return a PDF file.
    return Response(
        create_pdf_bytes(summary_lines),
        mimetype="application/pdf",
        headers={"Content-Disposition": "attachment; filename=expense-summary.pdf"},
    )


# Connect the home page URL to this function.
@app.route("/", methods=["GET", "POST"])
def index():
    # Start with no result when the page first loads.
    result = None

    # If the user submitted the form, calculate the budget.
    if request.method == "POST":
        result = calculate_budget(request.form)

    # Render the HTML page and pass it the data it needs.
    return render_template(
        # Use the main page template.
        "index.html",

        # Send the category list so the template can build the form.
        categories=EXPENSE_CATEGORIES,

        # Send the submitted form data so fields can stay filled in after submit.
        form=request.form,

        # Send the calculated summary, or None on the first page load.
        result=result,
    )


# Run the app only when this file is executed directly.
if __name__ == "__main__":
    # Start the local Flask development server with helpful debug messages.
    app.run(debug=True)
