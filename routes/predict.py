from flask import Blueprint, request, jsonify
from PIL import Image, ImageOps
import numpy as np
import base64
import io
from tensorflow.keras.models import load_model

predict_bp = Blueprint('predict_bp', __name__)

model = load_model('model/DoodleDashModel.keras')
class_names = ['apple', 'axe', 'banana', 'bird', 'butterfly', 'cat', 'cup', 'envelope', 'fish', 'flower',
            'hand', 'leaf', 'light bulb', 'moon', 'mountain', 'rain', 'star', 't-shirt', 'tree', 'wheel']

@predict_bp.route('/predict', methods=['POST'])
def predict():
    try:
        data = request.get_json()
        img_base64 = data.get('image')
        
        if not img_base64:
            return jsonify({'error': 'Image not provided'}), 400
        
        # Decode the base64 image
        img_bytes = base64.b64decode(img_base64)
        img = Image.open(io.BytesIO(img_bytes)).convert('L')
        
        # Invert the image (black drawing on white background -> white drawing on black background)
        img = ImageOps.invert(img)
        
        # Resize to 28x28 to match model input requirements
        img = img.resize((28, 28), Image.Resampling.LANCZOS)
        
        # Convert to numpy array and normalize
        img_array = np.array(img).astype('float32') / 255.0
        
        # Reshape for model input (batch_size, height, width, channels)
        img_array = img_array.reshape(1, 28, 28, 1)
        
        # Make prediction
        predictions = model.predict(img_array, verbose=0)[0]
        
        # Get top 3 predictions
        top_indices = predictions.argsort()[-3:][::-1]
        results = [
            {"label": class_names[i], "confidence": float(predictions[i])}
            for i in top_indices
        ]
        
        return jsonify({'predictions': results})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500