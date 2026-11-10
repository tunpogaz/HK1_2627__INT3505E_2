from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Module-level proxy extensions
db = SQLAlchemy()
migrate = Migrate()

