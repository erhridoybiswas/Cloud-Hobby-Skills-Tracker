"""Route blueprints for the REST API."""
from flask import Flask

from backend.routes.analytics_routes import analytics_bp
from backend.routes.auth_routes import auth_bp
from backend.routes.file_routes import files_bp
from backend.routes.goal_routes import goals_bp
from backend.routes.post_routes import posts_bp
from backend.routes.practice_routes import practice_bp
from backend.routes.profile_routes import profile_bp
from backend.routes.skill_routes import skills_bp
from backend.routes.social_routes import social_bp


def register_blueprints(app: Flask) -> None:
    """Attach all API blueprints to the application."""
    for blueprint in (
        auth_bp,
        profile_bp,
        skills_bp,
        goals_bp,
        practice_bp,
        posts_bp,
        social_bp,
        files_bp,
        analytics_bp,
    ):
        app.register_blueprint(blueprint)