import requests
import time
import json
import os
import itertools
import string

# --- SETTINGS ---
SAFE_DELAY = 15 
BATCH_SIZE = 50 
CHARSET = string.ascii_lowercase + string.digits + "._"
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

STATE_FILE = "state.json"

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"current_length": 4, "last_index": -1}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def notify_hit(username, reason=""):
    # PRIVACY MODE: We ONLY send to Discord. No local file logging.
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={
                "content": f"🚀 **[!] ALERT:** `{username}` is available! Grab it: https://www.instagram.com/accounts/emailsignup/"
            })
        except Exception as e:
            print(f"Failed to send Discord notification: {e}")
    else:
        print(f"!!! HIT FOUND: {username} !!! (But no Discord webhook set)")

def is_valid_ig_username(username):
    if username.startswith('.') or username.endswith('.'):
        return False
    if '..' in username:
        return False
    return True

def check_availability(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return False, "Taken"
        
        api_url = "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/"
        session = requests.Session()
        session.get("https://www.instagram.com/accounts/emailsignup/", headers=headers)
        
        api_headers = {
            "User-Agent": headers["User-Agent"],
            "X-IG-App-ID": "936619743392459",
            "X-ASBD-ID": "129477",
            "X-CSRFToken": session.cookies.get("csrftoken", "missing"),
            "Referer": "https://www.instagram.com/accounts/emailsignup/",
            "X-Requested-With": "XMLHttpRequest"
        }
        
        # Salt the email to avoid cached responses
        data = {
            "email": f"h_u_n_t_{int(time.time())}@gmail.com",
            "username": username,
            "first_name": "Hunt",
            "opt_into_hashtags": "false"
        }
        
        api_resp = session.post(api_url, data=data, headers=api_headers, timeout=10)
        result = api_resp.json()
        
        if "errors" in result and result["errors"]:
            return False, f"API Errors"
            
        if result.get("status") != "ok":
            return False, f"Not Available"

        return True, "Available"
            
    except Exception as e:
        return False, f"Error"

def run_batch():
    state = load_state()
    length = state["current_length"]
    start_idx = state["last_index"] + 1
    
    print(f"Starting batch (Public Mode - Discord Alerts Only) | Length {length}, Index {start_idx}")
    
    combinations = itertools.product(CHARSET, repeat=length)
    iterator = itertools.islice(combinations, start_idx, None)
    
    checked_count = 0
    current_idx = start_idx
    
    for combo in iterator:
        username = "".join(combo)
        
        if is_valid_ig_username(username):
            print(f"[{checked_count+1}/{BATCH_SIZE}] Checking: {username}...", end="", flush=True)
            is_avail, reason = check_availability(username)
            if is_avail:
                print(" AVAILABLE! 🚀")
                notify_hit(username, reason)
            else:
                print(" Taken.")
            
            checked_count += 1
            time.sleep(SAFE_DELAY)
        
        current_idx += 1
        if checked_count >= BATCH_SIZE:
            break
            
    total_combos = len(CHARSET) ** length
    if current_idx >= total_combos:
        state["current_length"] += 1
        state["last_index"] = -1
    else:
        state["last_index"] = current_idx - 1
        
    save_state(state)

if __name__ == "__main__":
    run_batch()
