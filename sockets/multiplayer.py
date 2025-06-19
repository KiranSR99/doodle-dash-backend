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
        updated_players = [p for p in players if p['id'] != sid]
        if len(updated_players) < len(players):
            room['players'] = updated_players
            emit('player_disconnected', {'room_code': code}, room=code)
            if not updated_players:
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
            'creator': request.sid  # 🆕 Store creator's sid
        }
        join_room(room_code)
        print(f"[SUCCESS] Room {room_code} created by {name} (sid: {request.sid})")
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
        print(f"[SUCCESS] {name} joined room {room_code} (sid: {request.sid})")

        emit('room_joined', get_public_room_data(rooms[room_code]), room=request.sid)
        emit('both_players_ready', get_public_room_data(rooms[room_code]), room=room_code)

    @socketio.on('leave_room')
    def leave_current_room(data):
        room_code = data.get('room_code')
        if not room_code or room_code not in rooms:
            return send_error('Invalid room code')

        players = rooms[room_code]['players']
        updated_players = [p for p in players if p['id'] != request.sid]
        if len(updated_players) < len(players):
            rooms[room_code]['players'] = updated_players
            leave_room(room_code)
            emit('player_left', get_public_room_data(rooms[room_code]), room=room_code)
            print(f"[INFO] Player left room {room_code} (sid: {request.sid})")
            if not updated_players:
                del rooms[room_code]
                print(f"[INFO] Deleted empty room {room_code}")
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

        if request.sid != room['creator']:
            return send_error('Only the room creator can start the game.')

        try:
            words = random.sample(WORDS, 5)
            room['words'] = words
            room['current_round'] = 0

            emit('start_round', {
                'round': 1,
                'word': words[0]
            }, room=room_code)

            print(f"[GAME STARTED] Room: {room_code}, Word: {words[0]}")
        except ValueError:
            send_error('Not enough words to start the game.')

    @socketio.on('next_round')
    def handle_next_round(data):
        room_code = data.get('room_code')
        if room_code not in rooms:
            return send_error('Room not found.')

        room = rooms[room_code]
        current_round = room.get('current_round', 0)
        words = room.get('words', [])

        if not words:
            return send_error('Game has not started yet.')

        if current_round + 1 >= len(words):
            emit('game_over', {}, room=room_code)
            print(f"[GAME OVER] Room: {room_code}")
        else:
            room['current_round'] += 1
            next_word = words[room['current_round']]
            emit('start_round', {
                'round': room['current_round'] + 1,
                'word': next_word
            }, room=room_code)
            print(f"[NEXT ROUND] Room: {room_code}, Word: {next_word}")

    print("[INFO] Multiplayer events registered successfully")
