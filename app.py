from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO
from routes.predict import predict_bp
from routes.random_word import game_bp

socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Register blueprints
    app.register_blueprint(predict_bp, url_prefix="/api")
    app.register_blueprint(game_bp, url_prefix="/api")
    
    socketio.init_app(app)
    
    from sockets.multiplayer import register_multiplayer_events
    register_multiplayer_events(socketio)
    
    return app

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
