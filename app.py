from flask import Flask
from flask_cors import CORS
from flask_socketio import SocketIO

socketio = SocketIO(cors_allowed_origins="*")

def create_app():
    app = Flask(__name__)
    CORS(app)
    
    # Register blueprints
    from routes.predict import predict_bp
    app.register_blueprint(predict_bp, url_prefix="/api")
    
    socketio.init_app(app)
    
    from sockets.multiplayer import register_multiplayer_events
    register_multiplayer_events(socketio)
    
    return app

app = create_app()

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True)
