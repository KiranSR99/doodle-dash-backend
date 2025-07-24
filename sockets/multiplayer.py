from flask import request
from flask_socketio import join_room, leave_room, emit
import random
import string

rooms = {}

WORDS = [
    'apple', 'axe', 'banana', 'bird', 'butterfly', 'cat', 'cup',
    'envelope', 'fish', 'flower', 'hand', 'leaf', 'light bulb',
    'moon', 'mountain', 'rain', 'star', 't-shirt', 'tree', 'wheel'
]

# === Utility Functions ===

def generate_room_code(length=6):
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))

def send_error(message):
    emit('error', {'message': message}, room=request.sid)

def find_and_remove_player(sid):
    for code, room in list(rooms.items()):
        players = room['players']
        updated = [p for p in players if p['id'] != sid]
        if len(updated) < len(players):
            room['players'] = updated
            emit('player_disconnected', {'room_code': code}, room=code)
            if not updated:
                del rooms[code]
                print(f"[INFO] Deleted empty room {code}")

def get_public_room_data(room):
    return {
        'room_code': room['room_code'],
        'players': room['players'],
        'status': room['status'],
        'creator': room['creator']
    }

# === Socket.IO Multiplayer Logic ===

def register_multiplayer_events(socketio):

    @socketio.on('connect')
    def handle_connect():
        print(f"[DEBUG] New client connected: {request.sid}")

    @socketio.on('disconnect')
    def handle_disconnect():
        find_and_remove_player(request.sid)
        print(f"[DEBUG] Client disconnected: {request.sid}")
        print(f"[DEBUG] Current rooms: {rooms}")

    @socketio.on('create_room')
    def create_room(data):
        name = data.get('name')
        if not name:
            return send_error('Name is required.')

        room_code = generate_room_code()
        rooms[room_code] = {
            'room_code': room_code,
            'players': [{'id': request.sid, 'name': name}],
            'status': 'waiting',
            'creator': name
        }
        join_room(room_code)
        emit('room_created', get_public_room_data(rooms[room_code]), room=request.sid)

    @socketio.on('join_room')
    def join_existing_room(data):
        room_code = data.get('room_code')
        name = data.get('name')
        if not room_code or not name:
            return send_error('Room code and name are required.')
        if room_code not in rooms:
            return send_error('Room does not exist.')
        if len(rooms[room_code]['players']) >= 2:
            return send_error('Room is full.')

        rooms[room_code]['players'].append({'id': request.sid, 'name': name})
        join_room(room_code)
        rooms[room_code]['status'] = 'ready' if len(rooms[room_code]['players']) == 2 else 'waiting'
        emit('room_joined', get_public_room_data(rooms[room_code]), room=request.sid)
        emit('both_players_ready', get_public_room_data(rooms[room_code]), room=room_code)

    @socketio.on('leave_room')
    def leave_current_room(data):
        room_code = data.get('room_code')
        if not room_code or room_code not in rooms:
            return send_error('Invalid room code')

        players = rooms[room_code]['players']
        updated = [p for p in players if p['id'] != request.sid]
        if len(updated) < len(players):
            rooms[room_code]['players'] = updated
            leave_room(room_code)
            emit('player_left', get_public_room_data(rooms[room_code]), room=room_code)
            if not updated:
                del rooms[room_code]
        else:
            send_error('You are not part of this room')

    @socketio.on('get_room_data')
    def handle_get_room_data(data):
        room_code = data.get('room_code')
        if room_code in rooms:
            emit('room_data', get_public_room_data(rooms[room_code]), room=request.sid)
        else:
            send_error('Room not found')

    # === Game Logic ===

    @socketio.on('start_game')
    def handle_start_game(data):
        room_code = data.get('room_code')
        if room_code not in rooms:
            return send_error('Room not found.')

        room = rooms[room_code]
        creator = room['creator']
        creator_sid = next((p['id'] for p in room['players'] if p['name'] == creator), None)

        if request.sid != creator_sid:
            return send_error('Only the creator can start the game.')

        try:
            words = random.sample(WORDS, 5)
            room['words'] = words
            room['round_progress'] = {}
            room['score_progress'] = {}
            emit('game_started', {}, room=room_code)
        except ValueError:
            send_error('Not enough words to start the game.')

    @socketio.on('next_round')
    def handle_next_round(data):
        room_code = data.get('room_code')
        if room_code not in rooms:
            return send_error('Room not found.')

        room = rooms[room_code]
        sid = request.sid

        if 'words' not in room:
            return send_error('Game not initialized.')

        progress = room.setdefault('round_progress', {})
        current_round = progress.get(sid, 0)
        words = room['words']

        if current_round >= len(words):
            emit('game_over', {}, room=sid)
        else:
            word = words[current_round]
            progress[sid] = current_round + 1
            emit('start_round', {
                'round': current_round + 1,
                'word': word
            }, room=sid)

    @socketio.on('submit_score')
    def handle_submit_score(data):
        room_code = data.get('room_code')
        score = data.get('score')
        if not room_code or room_code not in rooms or score is None:
            return send_error('Invalid score or room.')

        sid = request.sid
        room = rooms[room_code]

        # Store score
        scores = room.setdefault('score_progress', {})
        previous = scores.get(sid, [])
        previous.append(score)
        scores[sid] = previous

        # Find player name from ID
        player_name = next((p['name'] for p in room['players'] if p['id'] == sid), 'Unknown')

        # Round progress
        progress = room.get('round_progress', {})
        current_round = progress.get(sid, 0)
        total_rounds = len(room.get('words', []))

        emit('player_progress', {
            'player_id': sid,
            'player_name': player_name,
            'round': current_round,
            'total_rounds': total_rounds,
            'score': sum(previous)
        }, room=room_code)

        # Check if both players are finished
        all_done = all(progress.get(p['id'], 0) >= total_rounds for p in room['players'])
        if all_done:
            final_scores = {
                p['id']: {
                    'name': p['name'],
                    'score': sum(room['score_progress'].get(p['id'], []))
                }
                for p in room['players']
            }
            emit('game_over', {
                'final_scores': final_scores
            }, room=room_code)


    print("[INFO] Multiplayer events registered successfully")
