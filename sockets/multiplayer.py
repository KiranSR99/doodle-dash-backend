from flask import request
from flask_socketio import join_room, leave_room, emit
import random
import string
import time
import threading

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
            # Check if the leaving player was the creator
            leaving_player = next((p for p in players if p['id'] == sid), None)
            
            # Handle mid-game disconnection
            if room['status'] == 'in_progress':
                handle_mid_game_disconnection(code, leaving_player, updated)
            elif room['status'] in ['finished', 'post_game', 'rematch_pending']:
                handle_post_game_disconnection(code, leaving_player, updated)
            else:
                # Normal lobby disconnection
                if leaving_player and room['creator'] == leaving_player['name'] and updated:
                    room['creator'] = updated[0]['name']
                    emit('creator_changed', {'new_creator': room['creator']}, room=code)

            room['players'] = updated
            emit('player_disconnected', {'room_code': code}, room=code)

            if not updated:
                del rooms[code]
                print(f"[INFO] Deleted empty room {code}")

def handle_mid_game_disconnection(room_code, leaving_player, remaining_players):
    """Handle player leaving during active game"""
    room = rooms[room_code]
    
    if remaining_players:
        # End game immediately for remaining player
        remaining_player = remaining_players[0]
        
        # Calculate remaining player's final score
        scores = room.get('score_progress', {})
        remaining_score = sum(scores.get(remaining_player['id'], []))
        
        # Set new creator if leaving player was creator
        if room['creator'] == leaving_player['name']:
            room['creator'] = remaining_player['name']
            emit('creator_changed', {'new_creator': room['creator']}, room=room_code)
        
        # Send game abandoned notification
        emit('game_abandoned', {
            'message': f"{leaving_player['name']} left the game",
            'your_score': remaining_score,
            'you_win': True
        }, room=remaining_player['id'])
        
        room['status'] = 'abandoned'
        clean_game_data(room)

def handle_post_game_disconnection(room_code, leaving_player, remaining_players):
    """Handle player leaving after game ends"""
    room = rooms[room_code]
    
    if remaining_players:
        remaining_player = remaining_players[0]
        
        # Set new creator if leaving player was creator
        if room['creator'] == leaving_player['name']:
            room['creator'] = remaining_player['name']
            emit('creator_changed', {'new_creator': room['creator']}, room=room_code)
        
        # Force remaining player back to lobby
        force_return_to_lobby(room_code)

def clean_game_data(room):
    """Clean up game-specific data from room"""
    room.pop('words', None)
    room.pop('round_progress', None)
    room.pop('score_progress', None)
    room.pop('lobby_returns', None)
    room.pop('post_game_timer', None)
    room.pop('rematch_requests', None)
    room.pop('rematch_requester', None)

def reset_room_to_lobby(room_code):
    """Reset room to lobby state"""
    room = rooms[room_code]
    room['status'] = 'waiting' if len(room['players']) < 2 else 'ready'
    clean_game_data(room)

def force_return_to_lobby(room_code):
    """Force all players back to lobby"""
    reset_room_to_lobby(room_code)
    emit('forced_return_to_lobby', {
        'message': 'Returned to lobby automatically'
    }, room=room_code)

def check_post_game_timers():
    """Background task to check for expired post-game timers"""
    current_time = time.time()
    expired_rooms = []
    
    for room_code, room in rooms.items():
        if 'post_game_timer' in room and current_time > room['post_game_timer']:
            expired_rooms.append(room_code)
    
    for room_code in expired_rooms:
        if room_code in rooms:  # Double check room still exists
            force_return_to_lobby(room_code)

def get_public_room_data(room):
    return {
        'room_code': room['room_code'],
        'players': room['players'],
        'status': room['status'],
        'creator': room['creator']
    }

# === Background Timer Task ===
def start_timer_thread():
    def timer_worker():
        while True:
            time.sleep(1)  # Check every second
            check_post_game_timers()
    
    timer_thread = threading.Thread(target=timer_worker, daemon=True)
    timer_thread.start()

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
        
        room = rooms[room_code]
        
        # Auto-reset room if joining a finished/abandoned game
        if room['status'] in ['finished', 'abandoned', 'post_game']:
            reset_room_to_lobby(room_code)
        
        if len(room['players']) >= 2:
            return send_error('Room is full.')

        room['players'].append({'id': request.sid, 'name': name})
        join_room(room_code)
        room['status'] = 'ready' if len(room['players']) == 2 else 'waiting'
        emit('room_joined', get_public_room_data(room), room=request.sid)
        emit('both_players_ready', get_public_room_data(room), room=room_code)

    @socketio.on('leave_room')
    def leave_current_room(data):
        room_code = data.get('room_code')
        if not room_code or room_code not in rooms:
            return send_error('Invalid room code')

        room = rooms[room_code]
        players = room['players']
        sid = request.sid

        # Filter out the leaving player
        updated_players = [p for p in players if p['id'] != sid]

        if len(updated_players) == len(players):
            return send_error('You are not part of this room')

        # Identify the leaving player
        leaving_player = next((p for p in players if p['id'] == sid), None)

        # Handle different scenarios based on room status
        if room['status'] == 'in_progress':
            handle_mid_game_disconnection(room_code, leaving_player, updated_players)
        elif room['status'] in ['finished', 'post_game', 'rematch_pending']:
            handle_post_game_disconnection(room_code, leaving_player, updated_players)
        else:
            # Normal lobby leave
            if leaving_player and room['creator'] == leaving_player['name'] and updated_players:
                room['creator'] = updated_players[0]['name']
                emit('creator_changed', {'new_creator': room['creator']}, room=room_code)

        room['players'] = updated_players
        room['status'] = 'waiting' if len(updated_players) < 2 else room['status']

        # Notify others and remove from room
        leave_room(room_code)
        emit('player_left', get_public_room_data(room), room=room_code)

        # If all players have left, delete the room
        if not updated_players:
            del rooms[room_code]

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
        
        # Validate room status
        if room['status'] not in ['ready', 'waiting']:
            return send_error('Cannot start game. Please wait or return to lobby first.')
        
        if len(room['players']) < 2:
            return send_error('Need 2 players to start the game.')

        creator = room['creator']
        creator_sid = next((p['id'] for p in room['players'] if p['name'] == creator), None)

        if request.sid != creator_sid:
            return send_error('Only the creator can start the game.')

        try:
            words = random.sample(WORDS, 5)
            room['words'] = words
            room['round_progress'] = {}
            room['score_progress'] = {}
            room['status'] = 'in_progress'
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

        if 'words' not in room or room['status'] != 'in_progress':
            return send_error('Game not in progress.')

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

        if room['status'] != 'in_progress':
            return send_error('Game is not in progress.')

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
            
            room['status'] = 'finished'
            emit('game_over', {
                'final_scores': final_scores
            }, room=room_code)

    # === Post-Game Logic ===

    @socketio.on('request_rematch')
    def handle_request_rematch(data):
        room_code = data.get('room_code')
        if room_code not in rooms:
            return send_error('Room not found.')

        room = rooms[room_code]
        sid = request.sid

        if room['status'] != 'finished':
            return send_error('Cannot request rematch. Game not finished.')

        # Set rematch state
        room['status'] = 'rematch_pending'
        room['rematch_requester'] = sid
        
        requester_name = next((p['name'] for p in room['players'] if p['id'] == sid), 'Unknown')
        
        # Notify other player
        other_players = [p['id'] for p in room['players'] if p['id'] != sid]
        for other_sid in other_players:
            emit('rematch_requested', {
                'requester': requester_name
            }, room=other_sid)

    @socketio.on('accept_rematch')
    def handle_accept_rematch(data):
        room_code = data.get('room_code')
        if room_code not in rooms:
            return send_error('Room not found.')

        room = rooms[room_code]
        
        if room['status'] != 'rematch_pending':
            return send_error('No rematch pending.')

        # Start new game immediately
        try:
            words = random.sample(WORDS, 5)
            room['words'] = words
            room['round_progress'] = {}
            room['score_progress'] = {}
            room['status'] = 'in_progress'
            room.pop('rematch_requester', None)
            
            emit('rematch_accepted', {}, room=room_code)
            emit('game_started', {}, room=room_code)
        except ValueError:
            send_error('Not enough words to start the rematch.')

    @socketio.on('decline_rematch')
    def handle_decline_rematch(data):
        room_code = data.get('room_code')
        if room_code not in rooms:
            return send_error('Room not found.')

        room = rooms[room_code]
        
        if room['status'] != 'rematch_pending':
            return send_error('No rematch pending.')

        # Return both players to lobby
        reset_room_to_lobby(room_code)
        emit('rematch_declined', {}, room=room_code)
        emit('returned_to_lobby', {}, room=room_code)

    @socketio.on('return_to_lobby')
    def handle_return_to_lobby(data):
        room_code = data.get('room_code')
        if room_code not in rooms:
            return send_error('Room not found.')

        room = rooms[room_code]
        sid = request.sid

        if room['status'] not in ['finished', 'abandoned', 'post_game']:
            return send_error('Cannot return to lobby from current game state.')

        # Track who has returned
        lobby_returns = room.setdefault('lobby_returns', set())
        lobby_returns.add(sid)
        
        # Start timer on first return
        if 'post_game_timer' not in room:
            room['post_game_timer'] = time.time() + 15  # 15 second grace period
            room['status'] = 'post_game'
        
        # Check if all players returned
        if len(lobby_returns) >= len(room['players']):
            # All returned - immediate reset
            reset_room_to_lobby(room_code)
            emit('both_returned_to_lobby', {}, room=room_code)
        else:
            # Show waiting message with countdown
            remaining_time = max(0, int(room['post_game_timer'] - time.time()))
            emit('waiting_for_other_player', {
                'remaining_time': remaining_time
            }, room=sid)

    print("[INFO] Multiplayer events registered successfully")

# Start the background timer when the module loads
start_timer_thread()