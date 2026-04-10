import requests
import time
import json
import os
import itertools
import string

# --- SETTINGS ---
# The safe delay between checks to avoid IP bans (seconds)
SAFE_DELAY = 15 
# Number of names to check per script execution
BATCH_SIZE = 50 
# Character set for generation
CHARSET = string.ascii_lowercase + string.digits + "._"

# Discord Webhook for notifications (Set this in GitHub Secrets)
DISCORD_WEBHOOK = os.getenv("DISCORD_WEBHOOK")

STATE_FILE = "state.json"
HITS_FILE = "hits.txt"

# --- LOGIC ---

def load_state():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    return {"current_length": 1, "last_index": -1}

def save_state(state):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)

def log_hit(username):
    with open(HITS_FILE, "a") as f:
        f.write(f"{username}\n")
    
    if DISCORD_WEBHOOK:
        try:
            requests.post(DISCORD_WEBHOOK, json={
                "content": f"🚀 **[!] AVAILABLE:** The username `{username}` is available on Instagram! Grab it now!"
            })
        except Exception as e:
            print(f"Failed to send Discord notification: {e}")

def is_valid_ig_username(username):
    # Instagram rules:
    # 1. No leading or trailing periods
    if username.startswith('.') or username.endswith('.'):
        return False
    # 2. No consecutive periods
    if '..' in username:
        return False
    # 3. Min length 1, Max 30 (we are searching from 1 up)
    return True

def check_availability(username):
    """
    Double-check logic: URL first, then Signup API.
    """
    url = f"https://www.instagram.com/{username}/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        # Step 1: Fast Probe
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            return False # Definitely taken
        
        # Step 2: Signup API check (The definitive verdict)
        # This endpoint is used by the web signup flow
        api_url = "https://www.instagram.com/api/v1/web/accounts/web_create_ajax/attempt/"
        api_headers = {
            "User-Agent": headers["User-Agent"],
            "X-IG-App-ID": "936619743392459", # Standard Public App ID
            "X-ASBD-ID": "129477",
            "X-CSRFToken": "missing", # Sometime optional for public check, or grabbed from cookies
            "Referer": "https://www.instagram.com/accounts/emailsignup/"
        }
        data = {
            "email": "test@gmail.com",
            "username": username,
            "first_name": "Test",
            "opt_into_hashtags": "false"
        }
        
        # We need a CSRF token for the API. We can get it by hitting the main page first.
        session = requests.Session()
        main_page = session.get("https://www.instagram.com/accounts/emailsignup/", headers=headers)
        csrf = session.cookies.get("csrftoken")
        if csrf:
            api_headers["X-CSRFToken"] = csrf

        api_resp = session.post(api_url, data=data, headers=api_headers, timeout=10)
        result = api_resp.json()
        
        # Handle "username_is_taken" in errors
        if "errors" in result and "username" in result["errors"]:
            error_details = result["errors"]["username"]
            if any(err["code"] == "username_is_taken" for err in error_details):
                return False # Taken (deactivated or active)
        
        # If no username errors and status is OK
        if result.get("status") == "ok":
            return True # TRULY AVAILABLE
            
    except Exception as e:
        print(f"Error checking {username}: {e}")
    
    return False

def run_batch():
    state = load_state()
    length = state["current_length"]
    start_idx = state["last_index"] + 1
    
    print(f"Starting batch from length {length}, index {start_idx}...")
    
    # Generate combinations for the current length
    combinations = itertools.product(CHARSET, repeat=length)
    # Skip to our start index
    # (In a real massive search, this would be slow for 5+ chars, 
    # but for 1-4 chars it's fine. For 5+ we'd use a different algorithm)
    iterator = itertools.islice(combinations, start_idx, None)
    
    checked_count = 0
    current_idx = start_idx
    
    for combo in iterator:
        username = "".join(combo)
        
        if is_valid_ig_username(username):
            print(f"[{checked_count+1}/{BATCH_SIZE}] Checking: {username} ... ", end="", flush=True)
            if check_availability(username):
                print("AVAILABLE! 🚀")
                log_hit(username)
            else:
                print("Taken.")
            
            checked_count += 1
            time.sleep(SAFE_DELAY)
        
        current_idx += 1
        
        if checked_count >= BATCH_SIZE:
            break
            
    # Update state
    # If we finished all combinations for this length
    # We need to know the total combinations for this length
    total_combos = len(CHARSET) ** length
    if current_idx >= total_combos:
        state["current_length"] += 1
        state["last_index"] = -1
    else:
        state["last_index"] = current_idx - 1
        
    save_state(state)
    print("Batch complete. State saved.")

if __name__ == "__main__":
    run_batch()
