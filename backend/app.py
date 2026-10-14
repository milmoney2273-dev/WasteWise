
from datetime import date
from pathlib import Path
import sys
import sqlite3
import csv
import io

from flask import Flask, jsonify, request, send_from_directory, Response


# Locate the main Waste Management project folder
BASE_DIR = Path(__file__).resolve().parent.parent

# Allow Python to find database/db.py
sys.path.insert(0, str(BASE_DIR))

from database.db import get_connection, initialize_database


# Serve the existing website through Flask
app = Flask(__name__, static_folder=str(BASE_DIR), static_url_path="")

# Make sure all database tables exist
initialize_database()


# --------------------------------------------------
# DASHBOARD
# --------------------------------------------------

@app.route("/")
def home():
    return send_from_directory(BASE_DIR, "index.html")


@app.route("/api/health")
def health():
    return jsonify({"status": "ok"})


# --------------------------------------------------
# DAILY ENTRIES
# --------------------------------------------------

def format_entry(row):
    meals_prepared = row["meals_prepared"]
    meals_sold = row["meals_sold"]
    meals_wasted = meals_prepared - meals_sold

    return {
        "date": row["date"],
        "meals_prepared": meals_prepared,
        "meals_sold": meals_sold,
        "meals_wasted": meals_wasted,
        "wasted": meals_wasted,
        "prepared": meals_prepared,
        "sold": meals_sold,
        "potential_people_fed": meals_wasted * 2
    }


@app.route("/api/entries", methods=["GET"])
def get_entries():
    month = request.args.get("month")
    connection = get_connection()

    try:
        if month:
            try:
                if len(month) != 7:
                    raise ValueError
                date.fromisoformat(month + "-01")
            except ValueError:
                return jsonify({
                    "error": "Month must use YYYY-MM format."
                }), 400

            rows = connection.execute(
                """
                SELECT date, meals_prepared, meals_sold
                FROM daily_entries
                WHERE date LIKE ?
                ORDER BY date DESC
                """,
                (month + "-%",)
            ).fetchall()
        else:
            rows = connection.execute(
                """
                SELECT date, meals_prepared, meals_sold
                FROM daily_entries
                ORDER BY date DESC
                """
            ).fetchall()

        return jsonify([format_entry(row) for row in rows])

    finally:
        connection.close()


@app.route("/api/entries", methods=["POST"])
def save_entry():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Send entry data as JSON."
        }), 400

    entry_date = data.get("date")
    meals_prepared = data.get("meals_prepared")
    meals_sold = data.get("meals_sold")

    if not isinstance(entry_date, str):
        return jsonify({
            "error": "A valid date is required."
        }), 400

    try:
        date.fromisoformat(entry_date)
    except ValueError:
        return jsonify({
            "error": "Date must be a real date in YYYY-MM-DD format."
        }), 400

    if (
        type(meals_prepared) is not int
        or type(meals_sold) is not int
    ):
        return jsonify({
            "error": "Meals prepared and meals sold must be whole numbers."
        }), 400

    if meals_prepared < 0 or meals_sold < 0:
        return jsonify({
            "error": "Meal counts cannot be negative."
        }), 400

    if meals_sold > meals_prepared:
        return jsonify({
            "error": "Meals sold cannot exceed meals prepared."
        }), 400

    connection = get_connection()

    try:
        # A closed or holiday date cannot also have a meal entry.
        existing_status = connection.execute(
            "SELECT date FROM day_statuses WHERE date = ?",
            (entry_date,)
        ).fetchone()

        if existing_status:
            return jsonify({
                "error": (
                    "This date is marked closed or holiday. "
                    "Remove that status before saving a meal entry."
                )
            }), 409

        connection.execute(
            """
            INSERT INTO daily_entries
                (date, meals_prepared, meals_sold)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                meals_prepared = excluded.meals_prepared,
                meals_sold = excluded.meals_sold,
                updated_at = CURRENT_TIMESTAMP
            """,
            (entry_date, meals_prepared, meals_sold)
        )

        connection.commit()

        row = connection.execute(
            """
            SELECT date, meals_prepared, meals_sold
            FROM daily_entries
            WHERE date = ?
            """,
            (entry_date,)
        ).fetchone()

        return jsonify({
            "message": "Daily entry saved successfully.",
            "entry": format_entry(row)
        }), 200

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Could not save daily entry")
        return jsonify({
            "error": "A database error occurred while saving the entry."
        }), 500

    finally:
        connection.close()


# --------------------------------------------------
# CLOSED / HOLIDAY STATUSES
# --------------------------------------------------

@app.route("/api/day-statuses", methods=["GET"])
def get_day_statuses():
    month = request.args.get("month")

    if not month:
        return jsonify({
            "error": "Month is required in YYYY-MM format."
        }), 400

    try:
        if len(month) != 7:
            raise ValueError
        date.fromisoformat(month + "-01")
    except ValueError:
        return jsonify({
            "error": "Month must use YYYY-MM format."
        }), 400

    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT date, status, note
            FROM day_statuses
            WHERE date LIKE ?
            ORDER BY date
            """,
            (month + "-%",)
        ).fetchall()

        return jsonify([
            {
                "date": row["date"],
                "status": row["status"],
                "note": row["note"]
            }
            for row in rows
        ])

    finally:
        connection.close()


@app.route("/api/day-statuses", methods=["POST"])
def save_day_status():
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Send status data as JSON."
        }), 400

    status_date = data.get("date")
    day_status = data.get("status")
    note = data.get("note", "")

    if not isinstance(status_date, str):
        return jsonify({
            "error": "A valid date is required."
        }), 400

    try:
        date.fromisoformat(status_date)
    except ValueError:
        return jsonify({
            "error": "Date must use YYYY-MM-DD format."
        }), 400

    if day_status not in ("closed", "holiday"):
        return jsonify({
            "error": "Status must be closed or holiday."
        }), 400

    if not isinstance(note, str):
        return jsonify({
            "error": "Note must be text."
        }), 400

    connection = get_connection()

    try:
        # Don't allow a closure status to conflict with a saved meal entry.
        existing = connection.execute(
            "SELECT date FROM daily_entries WHERE date = ?",
            (status_date,)
        ).fetchone()

        if existing:
            return jsonify({
                "error": (
                    "This date already has a meal entry. "
                    "Update or remove that entry first."
                )
            }), 409

        connection.execute(
            """
            INSERT INTO day_statuses (date, status, note)
            VALUES (?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                status = excluded.status,
                note = excluded.note
            """,
            (status_date, day_status, note.strip())
        )

        connection.commit()

        return jsonify({
            "message": "Day status saved successfully.",
            "date": status_date,
            "status": day_status,
            "note": note.strip()
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Could not save day status")
        return jsonify({
            "error": "A database error occurred."
        }), 500

    finally:
        connection.close()


@app.route("/api/day-statuses/<status_date>", methods=["DELETE"])
def delete_day_status(status_date):
    try:
        date.fromisoformat(status_date)
    except ValueError:
        return jsonify({
            "error": "Date must use YYYY-MM-DD format."
        }), 400

    connection = get_connection()

    try:
        cursor = connection.execute(
            "DELETE FROM day_statuses WHERE date = ?",
            (status_date,)
        )

        connection.commit()

        if cursor.rowcount == 0:
            return jsonify({
                "error": "No day status found for this date."
            }), 404

        return jsonify({
            "message": "Day status removed."
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Could not remove day status")
        return jsonify({
            "error": "A database error occurred."
        }), 500

    finally:
        connection.close()


# --------------------------------------------------
# SMART INSIGHTS
# --------------------------------------------------

@app.route("/api/insights", methods=["GET"])
def get_insights():
    connection = get_connection()

    try:
        rows = connection.execute(
            """
            SELECT date, meals_prepared, meals_sold
            FROM daily_entries
            ORDER BY date ASC
            """
        ).fetchall()

    finally:
        connection.close()

    if not rows:
        return jsonify({
            "message": "Add daily entries to generate smart insights.",
            "total_recorded_days": 0,
            "total_meals_wasted": 0,
            "average_waste_per_day": 0,
            "highest_waste_day": None,
            "trend": "insufficient_data",
            "percentage_change": None,
            "recommendations": [
                "Record daily meals prepared and sold to begin analysing waste."
            ]
        })

    entries = []

    for row in rows:
        prepared = row["meals_prepared"]
        sold = row["meals_sold"]
        wasted = prepared - sold

        entries.append({
            "date": row["date"],
            "prepared": prepared,
            "sold": sold,
            "wasted": wasted
        })

    total_days = len(entries)
    total_wasted = sum(entry["wasted"] for entry in entries)
    average_waste = round(total_wasted / total_days, 1)

    highest_day = max(entries, key=lambda entry: entry["wasted"])

    recommendations = []

    if average_waste > 0:
        recommendations.append(
            "Compare meals prepared with meals sold and adjust future "
            "preparation to better match demand."
        )
    else:
        recommendations.append(
            "No recorded meal waste was found. Keep tracking daily entries "
            "to monitor future performance."
        )

    percentage_change = None

    if total_days >= 2:
        midpoint = total_days // 2

        earlier_entries = entries[:midpoint]
        later_entries = entries[midpoint:]

        earlier_average = sum(
            entry["wasted"] for entry in earlier_entries
        ) / len(earlier_entries)

        later_average = sum(
            entry["wasted"] for entry in later_entries
        ) / len(later_entries)

        if earlier_average > 0:
            percentage_change = round(
                (
                    (later_average - earlier_average)
                    / earlier_average
                ) * 100,
                1
            )
        elif later_average == 0:
            percentage_change = 0.0

        if later_average > earlier_average:
            trend = "increasing"
            recommendations.append(
                "Average waste is higher in the later recorded entries. "
                "Review recent meal demand and preparation quantities."
            )

        elif later_average < earlier_average:
            trend = "decreasing"
            recommendations.append(
                "Average waste is lower in the later recorded entries. "
                "Review which preparation practices may be helping."
            )

        else:
            trend = "stable"
            recommendations.append(
                "Average waste is unchanged between the two groups "
                "of recorded entries. Look for opportunities to reduce it."
            )

    else:
        trend = "insufficient_data"
        recommendations.append(
            "Record more daily entries to identify a meaningful waste trend."
        )

    return jsonify({
        "total_recorded_days": total_days,
        "total_meals_wasted": total_wasted,
        "average_waste_per_day": average_waste,
        "highest_waste_day": highest_day,
        "trend": trend,
        "percentage_change": percentage_change,
        "recommendations": recommendations
    })


# --------------------------------------------------
# WASTE-REDUCTION GOALS
# --------------------------------------------------

@app.route("/api/goals", methods=["GET"])
def get_waste_goal():
    """Retrieve the saved waste-reduction goal."""
    connection = get_connection()

    try:
        row = connection.execute(
            """
            SELECT target_percent, updated_at
            FROM waste_goals
            WHERE id = 1
            """
        ).fetchone()

        if row is None:
            return jsonify({
                "target_percent": None,
                "updated_at": None
            })

        return jsonify({
            "target_percent": row["target_percent"],
            "updated_at": row["updated_at"]
        })

    except sqlite3.Error:
        app.logger.exception("Could not retrieve waste-reduction goal")
        return jsonify({
            "error": "A database error occurred while retrieving the goal."
        }), 500

    finally:
        connection.close()


@app.route("/api/goals", methods=["POST"])
def save_waste_goal():
    """Save or update the waste-reduction goal."""
    data = request.get_json(silent=True)

    if not isinstance(data, dict):
        return jsonify({
            "error": "Send goal data as JSON."
        }), 400

    target_percent = data.get("target_percent")

    if (
        type(target_percent) is not int
        or not 1 <= target_percent <= 90
    ):
        return jsonify({
            "error": "Target must be a whole number between 1 and 90."
        }), 400

    connection = get_connection()

    try:
        connection.execute(
            """
            INSERT INTO waste_goals (id, target_percent, updated_at)
            VALUES (1, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(id) DO UPDATE SET
                target_percent = excluded.target_percent,
                updated_at = CURRENT_TIMESTAMP
            """,
            (target_percent,)
        )

        connection.commit()

        return jsonify({
            "message": "Waste-reduction goal saved successfully.",
            "target_percent": target_percent
        })

    except sqlite3.Error:
        connection.rollback()
        app.logger.exception("Could not save waste-reduction goal")
        return jsonify({
            "error": "A database error occurred while saving the goal."
        }), 500

    finally:
        connection.close()


# --------------------------------------------------
# START SERVER
# --------------------------------------------------

# --------------------------------------------------
# CSV EXPORT
# --------------------------------------------------

@app.route("/api/export/csv", methods=["GET"])
def export_csv():
    connection = get_connection()

    try:
        entries = connection.execute("""
            SELECT
                date,
                meals_prepared,
                meals_sold,
                meals_prepared - meals_sold AS meals_wasted
            FROM daily_entries
            ORDER BY date ASC
        """).fetchall()
    finally:
        connection.close()

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        "Date",
        "Meals Prepared",
        "Meals Sold",
        "Meals Wasted"
    ])

    for entry in entries:
        writer.writerow([
            entry["date"],
            entry["meals_prepared"],
            entry["meals_sold"],
            entry["meals_wasted"]
        ])

    return Response(
        "\ufeff" + output.getvalue(),
        mimetype="text/csv",
        headers={
            "Content-Disposition":
                "attachment; filename=wastewise_report.csv"
        }
    )

if __name__ == "__main__":
    app.run(debug=True)
