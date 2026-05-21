import logging

from flask import Flask

import db
from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)

    from routes.status    import status_bp
    from routes.dashboard import dashboard_bp
    from routes.data      import data_bp
    from routes.analysis  import analysis_bp
    from routes.services  import services_bp
    from routes.logs      import logs_bp

    app.register_blueprint(status_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(data_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(services_bp)
    app.register_blueprint(logs_bp)

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5000, debug=application.config["DEBUG"])
