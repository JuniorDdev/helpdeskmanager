import os

from app import create_app


app = create_app()

if __name__ == "__main__":
    railway = os.getenv("PORT")
    app.run(
        host=os.getenv("APP_HOST", "0.0.0.0" if railway else "127.0.0.1"),
        port=int(railway or os.getenv("APP_PORT", "5000")),
        debug=app.config["DEBUG"],
    )
