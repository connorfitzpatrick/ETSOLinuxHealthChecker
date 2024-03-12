# File we will run to start application
# Imports app instance from /app package and calls run on it
from app import create_app

app = create_app()

if __name__ == '__main__':
    app.run(debug=True)
