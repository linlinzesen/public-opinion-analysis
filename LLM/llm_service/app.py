"""独立演示入口：python -m llm_service.app"""

from flask import Flask, jsonify

from .api import create_llm_blueprint


def create_app() -> Flask:
    app = Flask(__name__)
    app.json.ensure_ascii = False
    app.register_blueprint(create_llm_blueprint())

    @app.get("/health")
    def health():
        return jsonify({"success": True, "service": "llm_service"})

    return app


if __name__ == "__main__":
    create_app().run(host="0.0.0.0", port=5001, debug=True)
