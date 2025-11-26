from flask import Flask
from .config import Config
from .services.retrieval import EllenkiRetrievalService
from .services.recommender import CourseRecommender
from .services.llm_client import LLMClient

retrieval_service = None
recommender = None
llm_client = None


def create_app():
    global retrieval_service, recommender, llm_client

    app = Flask(__name__)
    app.config.from_object(Config)

    llm_client = LLMClient(
        base_url=app.config["OLLAMA_BASE_URL"],
        model=app.config["OLLAMA_MODEL"],
    )
    retrieval_service = EllenkiRetrievalService()
    recommender = CourseRecommender()

    from .main import bp as main_bp
    app.register_blueprint(main_bp)

    return app
