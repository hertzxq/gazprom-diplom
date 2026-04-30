"""Download and install xlrd by extracting the .whl (zip) directly into site-packages."""
import io
import json
import os
import site
import ssl
import time
import zipfile
import urllib.request

PROXY = "http://modeler_9GpcwY:SzoNPsLnreT2@89.40.105.65:11812"

# Setup proxy + skip SSL verification (proxy may interfere)
proxy_handler = urllib.request.ProxyHandler({"https": PROXY, "http": PROXY})
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
https_handler = urllib.request.HTTPSHandler(context=ctx)
opener = urllib.request.build_opener(proxy_handler, https_handler)
urllib.request.install_opener(opener)

# Find site-packages
sp = None
for p in site.getsitepackages():
    if "site-packages" in p:
        sp = p
        break
if not sp:
    sp = os.path.join(os.path.dirname(os.__file__), "site-packages")

print(f"Target: {sp}")

# Step 1: Get the correct download URL from PyPI JSON API
print("Resolving download URL from PyPI...")
try:
    api_req = urllib.request.Request(
        "https://pypi.org/pypi/xlrd/2.0.1/json",
        headers={"User-Agent": "pip/23.0", "Accept": "application/json"},
    )
    api_resp = urllib.request.urlopen(api_req, timeout=30)
    info = json.loads(api_resp.read())
    whl_url = None
    for url_info in info["urls"]:
        if url_info["filename"].endswith(".whl"):
            whl_url = url_info["url"]
            break
    if not whl_url:
        # fallback to sdist
        whl_url = info["urls"][0]["url"]
    print(f"Found URL: {whl_url}")
except Exception as e:
    print(f"PyPI API failed ({e}), using hardcoded URL")
    whl_url = "https://files.pythonhosted.org/packages/a6/0c/c2a72d51fe56e08a08acc85d13013558a2d793028ae7385448a6ccdfae64/xlrd-2.0.1-py2.py3-none-any.whl"

# Step 2: Download the .whl file (chunked for slow proxy)
print(f"Downloading xlrd...")
req = urllib.request.Request(whl_url, headers={"User-Agent": "pip/23.0"})
resp = urllib.request.urlopen(req, timeout=120)
chunks = []
while True:
    chunk = resp.read(4096)
    if not chunk:
        break
    chunks.append(chunk)
    print(f"\r  Downloaded {sum(len(c) for c in chunks)} bytes...", end="", flush=True)
data = b"".join(chunks)
print(f"\n  Total: {len(data)} bytes")

# Step 3: Extract zip into site-packages
time.sleep(2)  # give antivirus a moment
with zipfile.ZipFile(io.BytesIO(data)) as zf:
    zf.extractall(sp)
    print(f"Extracted {len(zf.namelist())} files into {sp}")

# Verify
import importlib
importlib.invalidate_caches()
import xlrd
print(f"xlrd {xlrd.__version__} installed successfully!")
