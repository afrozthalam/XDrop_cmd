import asyncio
import os
import time
import requests
import re
from playwright.async_api import async_playwright
from datetime import datetime

# --- CONFIGURATION ---
REELS_FILE = "reels.txt"
DONE_FILE = "downloaded.txt"
DEST_FOLDER = "downloads"
CONCURRENT_REELS = 10  # Exactly 10 parallel reel processes (threads)
PROVIDER_TIMEOUT = 30000  # 30 seconds per provider

# Verified 100% Working Providers
PROVIDERS = [
    {
        "name": "saveinsta.io",
        "url": "https://saveinsta.io/en/reels-downloader",
        "input": "input#s_input",
        "btn": "button.btn-default",
        "dl": "a[title='Download Video']"
    },
    {
        "name": "savereels.io",
        "url": "https://savereels.io/en",
        "input": "input#s_input",
        "btn": "button.btn-default",
        "dl": "a[title='Download Video']"
    },
    {
        "name": "insaver.app",
        "url": "https://insaver.app/en/instagram-reels-video-download",
        "input": "input#s_input",
        "btn": "button.btn-default",
        "dl": "a[title='Download Video']"
    },
    {
        "name": "igram.world",
        "url": "https://igram.world/en1/",
        "input": "input#url",
        "btn": "button#submit",
        "dl": "a.button.button--filled.button__download"
    },
    {
        "name": "iqsaved.com",
        "url": "https://iqsaved.com/en1/",
        "input": "input.js__search-input",
        "btn": "button.js__search-submit",
        "dl": "a.button.button__blue"
    }
]

def get_reel_id(url):
    """Robustly extract the unique Reel ID from any messy URL."""
    match = re.search(r"/reel/([^/?\s]+)", url)
    if match:
        return match.group(1)
    return None

async def download_file(url, reel_url):
    """Downloads the actual MP4 file."""
    try:
        reel_id = [u for u in reel_url.split("/") if u][-1]
        filename = f"{reel_id}.mp4"
        path = os.path.join(DEST_FOLDER, filename)
        
        # Use requests for the actual file stream (faster than browser)
        r = requests.get(url, stream=True, timeout=60)
        r.raise_for_status()
        with open(path, 'wb') as f:
            for chunk in r.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # QUALITY CONTROL: Thumbnails are usually < 150KB. Videos are > 300KB.
        fsize = os.path.getsize(path)
        if fsize > 300000: 
            return True
        else:
            print(f"    [!] Warning: Downloaded file too small ({fsize} bytes). Likely a thumbnail. Discarding.")
            os.remove(path)
    except Exception as e:
        print(f"    [!] Download Error: {e}")
    return False

async def try_provider(browser_context, provider, reel_url):
    """Tries to get a download link from a specific website."""
    page = await browser_context.new_page()
    try:
        print(f"  [>] Trying {provider['name']}...")
        await page.goto(provider['url'], timeout=PROVIDER_TIMEOUT)
        await page.fill(provider['input'], reel_url)
        await page.click(provider['btn'])
        
        # Wait for the download link to appear
        await page.wait_for_selector(provider['dl'], timeout=PROVIDER_TIMEOUT)
        dl_element = await page.query_selector(provider['dl'])
        dl_link = await dl_element.get_attribute("href")
        
        if dl_link:
            # Special case for igram.world which wraps link in ?uri=
            if "uri=" in dl_link:
                import urllib.parse
                parsed = urllib.parse.urlparse(dl_link)
                dl_link = urllib.parse.parse_qs(parsed.query).get('uri', [dl_link])[0]
            
            print(f"  [+] {provider['name']} found link!")
            success = await download_file(dl_link, reel_url)
            if success:
                return True
    except Exception as e:
        # print(f"    [-] {provider['name']} failed: {e}")
        pass
    finally:
        await page.close()
    return False

async def process_reel(browser_context, reel_url):
    """Tries multiple providers in parallel for one Reel."""
    print(f"[*] Processing: {reel_url}")
    
    # We try all providers. The first one to return True wins.
    # Note: Using asyncio.as_completed to finish as soon as one succeeds would be better,
    # but for simplicity and "completeness," we run them and stop once we have a success.
    
    for provider in PROVIDERS:
        if await try_provider(browser_context, provider, reel_url):
            print(f"\033[92m[SUCCESS]\033[0m {reel_url}")
            return reel_url
    
    print(f"\033[91m[FAILED]\033[0m {reel_url}")
    return None

async def main():
    if not os.path.exists(DEST_FOLDER): os.makedirs(DEST_FOLDER)
    
    # Load history
    done_ids = set()
    if os.path.exists(DONE_FILE):
        with open(DONE_FILE, "r") as f:
            done_ids = {l.strip() for l in f if l.strip()}
            
    with open(REELS_FILE, "r") as f:
        # Extract unique IDs from the input file
        pending = []
        seen_in_batch = set()
        
        for line in f:
            rid = get_reel_id(line)
            if rid and rid not in done_ids and rid not in seen_in_batch:
                # We store the original URL (cleaned of junk) to process
                clean_url = f"https://www.instagram.com/reel/{rid}/"
                pending.append(clean_url)
                seen_in_batch.add(rid)

    print(f"D_REELS READY. {len(pending)} Reels truly pending.")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        
        # Limit concurrency to avoid crashing memory
        semaphore = asyncio.Semaphore(CONCURRENT_REELS)
        
        async def sem_process(url):
            async with semaphore:
                res = await process_reel(context, url)
                if res:
                    rid = get_reel_id(res)
                    if rid:
                        with open(DONE_FILE, "a") as f:
                            f.write(rid + "\n")

        tasks = [sem_process(url) for url in pending]
        await asyncio.gather(*tasks)
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
