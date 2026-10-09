"""Entry point.

    python app.py                 # development server on http://localhost:5050
    gunicorn app:app              # production (Render / Railway)
"""
import config
from api import create_app

app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=config.API_PORT, debug=False)
