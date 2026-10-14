
import sqlite3
from pathlib import Path


# Find the project root directory.
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Store the database inside the database folder.
DATABASE_PATH = PROJECT_ROOT / "database" / "wastewise.db"


def get_connection():
    """Create and return a connection to the SQLite database."""
    connection = sqlite3.connect(DATABASE_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    """Create all required tables if they do not already exist."""
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    connection = get_connection()

    try:
        # Store daily restaurant food-waste entries.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS daily_entries (
                date TEXT PRIMARY KEY,
                meals_prepared INTEGER NOT NULL
                    CHECK (meals_prepared >= 0),
                meals_sold INTEGER NOT NULL
                    CHECK (meals_sold >= 0),
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CHECK (meals_sold <= meals_prepared)
            )
        """)

        # Store days when the restaurant is closed or on holiday.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS day_statuses (
                date TEXT PRIMARY KEY,
                status TEXT NOT NULL
                    CHECK (status IN ('closed', 'holiday')),
                note TEXT DEFAULT '',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Store the restaurant's waste-reduction goal.
        # The fixed ID of 1 allows one saved goal at a time.
        connection.execute("""
            CREATE TABLE IF NOT EXISTS waste_goals (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                target_percent INTEGER NOT NULL
                    CHECK (target_percent BETWEEN 1 AND 90),
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        connection.commit()

    finally:
        connection.close()


if __name__ == "__main__":
    initialize_database()
    print("WasteWise database initialized successfully.")
