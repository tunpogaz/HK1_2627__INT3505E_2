from a2wsgi import ASGIMiddleware
from Week7.design_first.app import create_app

connexion_app = create_app()
# In Connexion 3.x, the top-level application is an ASGI app wrapped in ConnexionMiddleware.
# For WSGI runners like standard Gunicorn sync workers, ASGIMiddleware adapts it cleanly:
app = ASGIMiddleware(connexion_app)

