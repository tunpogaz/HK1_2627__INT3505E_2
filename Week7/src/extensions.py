from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

# Khai báo ở module-level, không kèm app; factory sẽ gọi db.init_app(app) (Slide 15)
db = SQLAlchemy()
migrate = Migrate()

