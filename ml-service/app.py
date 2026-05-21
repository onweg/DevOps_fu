import logging

from flask import Flask

from config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def create_app() -> Flask:
    app = Flask(__name__)
    app.config.from_object(Config)

    from routes.generate import generate_bp
    from routes.train    import train_bp
    from routes.predict  import predict_bp
    from routes.health   import health_bp

    app.register_blueprint(generate_bp)
    app.register_blueprint(train_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(health_bp)

    return app


if __name__ == "__main__":
    application = create_app()
    application.run(host="0.0.0.0", port=5001, debug=application.config["DEBUG"])
