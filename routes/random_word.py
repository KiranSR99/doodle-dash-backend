import random
from flask import Blueprint, jsonify

# Define blueprint
game_bp = Blueprint('game', __name__)

# Master word list
WORDS = [
    'apple', 'axe', 'banana', 'bird', 'butterfly', 'cat', 'cup',
    'envelope', 'fish', 'flower', 'hand', 'leaf', 'light bulb',
    'moon', 'mountain', 'rain', 'star', 't-shirt', 'tree', 'wheel'
]

# Utility function to get unique random words
def get_random_words(n):
    if n > len(WORDS):
        raise ValueError(f"Requested {n} words, but only {len(WORDS)} are available.")
    return random.sample(WORDS, n)

# API to get words for multiple rounds
@game_bp.route('/round-words', methods=['GET'])
def get_round_words():
    try:
        num_rounds = 5  # Fixed for now, can be made dynamic via query params
        words = get_random_words(num_rounds)
        return jsonify({
            'rounds': [
                {'round': i + 1, 'word': word} for i, word in enumerate(words)
            ]
        }), 200
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
