import os
import sys
import json
import time
import requests
import websocket
import threading
from dotenv import load_dotenv
from keep_alive import keep_alive

load_dotenv()

usertokens = []
for key, value in os.environ.items():
    if key.startswith("TOKEN"):
        tokens_in_var = [token.strip() for token in value.split(',')]
        usertokens.extend(tokens_in_var)

usertokens = [token for token in usertokens if token]

if not usertokens:
    print("[ERROR] No tokens found in your .env file.")
    print("Please add one or more token variables, for example: TOKEN_1=your_token")
    sys.exit()

unique_tokens = list(set(usertokens))
print(f"Found {len(unique_tokens)} unique tokens to process.")
usertokens = unique_tokens

GUILD_ID = 1417545256341209220
CHANNEL_ID = 1450093106270830610
SELF_MUTE = False
SELF_DEAF = False
STATUS = "online"

shutdown_event = threading.Event()

def process_token(token):
    headers = {"Authorization": token, "Content-Type": "application/json"}
    validate = requests.get('https://canary.discordapp.com/api/v9/users/@me', headers=headers)
    if validate.status_code != 200:
        print(f"[ERROR] Token might be invalid (ends with: ...{token[-5:]}). Status: {validate.status_code}")
        return

    userinfo = validate.json()
    username = f"{userinfo['username']}#{userinfo['discriminator']}"
    print(f"[INFO] Validated token for user: {username}")

    ws = None
    while not shutdown_event.is_set():
        try:
            ws = websocket.create_connection('wss://gateway.discord.gg/?v=9&encoding=json')
            hello = json.loads(ws.recv())
            heartbeat_interval = hello['d']['heartbeat_interval'] / 1000

            auth_payload = {"op": 2, "d": {"token": token, "properties": {"$os": "Windows 10", "$browser": "Google Chrome", "$device": "Windows"}, "presence": {"status": STATUS, "afk": False}}}
            ws.send(json.dumps(auth_payload))

            join_vc_payload = {"op": 4, "d": {"guild_id": GUILD_ID, "channel_id": CHANNEL_ID, "self_mute": SELF_MUTE, "self_deaf": SELF_DEAF}}
            ws.send(json.dumps(join_vc_payload))
            print(f"[INFO] {username} is attempting to join the voice channel.")

            last_heartbeat = time.time()
            ws.settimeout(1.0)

            while not shutdown_event.is_set():
                try:
                    ws.recv()
                except websocket.WebSocketTimeoutException:
                    pass

                if time.time() - last_heartbeat > heartbeat_interval:
                    ws.send(json.dumps({"op": 1, "d": None}))
                    last_heartbeat = time.time()

        except (websocket.WebSocketConnectionClosedException, ConnectionResetError) as e:
            if not shutdown_event.is_set():
                print(f"[WARNING] Connection lost for {username}. Reconnecting in 10s... ({e})")
                shutdown_event.wait(10)
        except Exception as e:
            if not shutdown_event.is_set():
                print(f"[ERROR] An unexpected error occurred for {username}: {e}")
                shutdown_event.wait(30)
        finally:
            if ws:
                ws.close()

    print(f"[INFO] Shutdown signal received. Disconnecting {username}...")
    try:
        ws_disconnect = websocket.create_connection('wss://gateway.discord.gg/?v=9&encoding=json')
        ws_disconnect.recv()
        auth_payload = {"op": 2, "d": {"token": token, "properties": {"$os": "Windows 10", "$browser": "Google Chrome", "$device": "Windows"}}}
        ws_disconnect.send(json.dumps(auth_payload))
        time.sleep(0.5)
        
        disconnect_vc_payload = {"op": 4, "d": {"guild_id": GUILD_ID, "channel_id": None, "self_mute": True, "self_deaf": True}}
        ws_disconnect.send(json.dumps(disconnect_vc_payload))
        ws_disconnect.close()
        print(f"[SUCCESS] {username} has been disconnected.")
    except Exception as e:
        print(f"[ERROR] Could not send disconnect message for {username}: {e}")

if __name__ == "__main__":
    keep_alive()
    os.system("clear")
    
    threads = []
    for token in usertokens:
        thread = threading.Thread(target=process_token, args=(token,))
        threads.append(thread)
        thread.start()
        time.sleep(2)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n[SHUTDOWN] Ctrl+C detected. Initiating graceful shutdown...")
        shutdown_event.set()
        for thread in threads:
            thread.join()

    print("[SHUTDOWN] All threads have been terminated. Goodbye!")
    sys.exit(0)
