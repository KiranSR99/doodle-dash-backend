from flask import Blueprint, request, jsonify
from PIL import Image, ImageOps
import numpy as np
import base64
import io
from tensorflow.keras.models import load_model
import os

# ==============================
# Blueprint
# ==============================
predict_bp = Blueprint('predict_bp', __name__)

# ==============================
# Load Keras Model
# ==============================
keras_model = load_model('model/DoodleDashModel.keras')
keras_class_names = [
    'apple', 'axe', 'banana', 'bird', 'butterfly', 'cat', 'cup', 'envelope',
    'fish', 'flower', 'hand', 'leaf', 'light bulb', 'moon', 'mountain', 'rain',
    'star', 't-shirt', 'tree', 'wheel'
]

# ==============================
# Load Scratch CNN Model
# ==============================
from train_cnn import OptimizedCNN  # ensure train_cnn.py is in project root or use relative import

scratch_model = OptimizedCNN()
scratch_model.load('model/scratch_cnn_model.npz')
scratch_class_names = [
    'butterfly', 'envelope', 'fish', 'flower', 'leaf', 'mountain', 'star', 'tree'
]

# ==============================
# Image preprocessing
# ==============================
def preprocess_image(img_base64, target_size=(28,28), invert=True):
    """
    Convert base64 image to normalized numpy array for CNN input
    """
    img_bytes = base64.b64decode(img_base64)
    img = Image.open(io.BytesIO(img_bytes)).convert('L')
    if invert:
        img = ImageOps.invert(img)
    img = img.resize(target_size, Image.Resampling.LANCZOS)
    img_array = np.array(img).astype('float32') / 255.0
    return img_array

# ==============================
# Keras Prediction Endpoint
# ==============================
@predict_bp.route('/predict', methods=['POST'])
def predict_keras():
    try:
        data = request.get_json()
        img_base64 = data.get('image')
        if not img_base64:
            return jsonify({'error': 'Image not provided'}), 400

        img_array = preprocess_image(img_base64)
        img_array = img_array.reshape(1, 28, 28, 1)  # Keras expects (batch, height, width, channels)

        predictions = keras_model.predict(img_array, verbose=0)[0]
        top_indices = predictions.argsort()[-3:][::-1]

        results = [{"label": keras_class_names[i], "confidence": float(predictions[i])} for i in top_indices]

        return jsonify({'predictions': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

# ==============================
# Scratch CNN Prediction Endpoint
# ==============================
@predict_bp.route('/predict/scratch', methods=['POST'])
def predict_scratch():
    try:
        data = request.get_json()
        img_base64 = data.get('image')
        if not img_base64:
            return jsonify({'error': 'Image not provided'}), 400

        # Preprocess
        img_array = preprocess_image(img_base64, target_size=(28,28), invert=True)
        img_array = img_array.reshape(1, 28, 28)  # shape (batch, height, width) for scratch CNN

        # Forward pass
        probs = scratch_model.forward(img_array)
        probs = np.array(probs).flatten()  # ensure 1D array even if batch=1

        # Top 3 predictions
        top_indices = probs.argsort()[-3:][::-1]
        results = [{"label": scratch_class_names[i], "confidence": float(probs[i])} for i in top_indices]

        return jsonify({'predictions': results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
