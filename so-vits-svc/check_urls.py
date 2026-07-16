import requests
import os

urls = [
    "https://hf-mirror.com/datasets/ylzz1997/rmvpe_pretrain_model/resolve/main/rmvpe.pt",
    "https://hf-mirror.com/datasets/ylzz1997/rmvpe_pretrain_model/resolve/main/fcpe.pt"
]

for url in urls:
    try:
        r = requests.head(url, allow_redirects=True, verify=False)
        print(f"URL: {url}")
        print(f"Status: {r.status_code}")
        print(f"Content-Length: {r.headers.get('Content-Length')}")
        print("-" * 20)
    except Exception as e:
        print(f"Error checking {url}: {e}")
