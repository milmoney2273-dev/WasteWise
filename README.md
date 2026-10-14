
# WasteWise 🌱
### Smarter kitchens. Less waste. Greater impact.

WasteWise is a food-waste tracking and analysis web application designed to help restaurants monitor meal waste, understand trends, and set waste-reduction goals.

## Features

- Daily meal tracking
- Automatic food-waste calculations
- Calendar for holidays and closed days
- Monthly and yearly analysis
- Dashboard statistics and Smart Insights
- Food-waste trend chart
- Waste-reduction goals with progress tracking
- CSV export for spreadsheet analysis

## Technology Stack

- Python
- Flask
- SQLite
- HTML
- CSS
- JavaScript

## How It Works

WasteWise calculates meals wasted automatically:

**Meals wasted = Meals prepared − Meals sold**

It also estimates potential people fed using the project's calculation:

**Potential people fed = Meals wasted × 2**

## Run Locally

1. Install Python.
2. Open the project folder in a terminal.
3. Create a virtual environment:

   `python -m venv .venv`

4. Activate it on Windows:

   `.venv\Scripts\Activate.ps1`

5. Install Flask:

   `python -m pip install flask`

6. Start the application:

   `python backend/app.py`

7. Open `http://127.0.0.1:5000/` in your browser.

## Project Structure

- `backend/` — Flask application
- `database/` — Database setup
- `index.html` — Dashboard
- `entry.html` — Daily entries
- `calendar.html` — Calendar
- `monthly.html` — Monthly analysis
- `yearly.html` — Yearly analysis
- `style.css` — Styling

## Future Improvements

- Online deployment
- More detailed reporting
- Additional usability improvements

## Project Status

Core features implemented. Testing and deployment preparation are ongoing.
