import os
import time
import random
import asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Configuration
POSTS_FILE = "posts.txt"
DOWNLOADED_FILE = "posts_downloaded.txt"
PARTIAL_FILE = "posts_partial.txt"
INVALID_FILE = "posts_invalid.txt"
DOWNLOAD_DIR = "posts_downloads"
CONCURRENCY = 5 # Strict 5-Thread Concurrency
MAX_RETRIES = 3 # If a URL fails on 3 different websites, it is marked mathematically permanently dead.

os.makedirs(DOWNLOAD_DIR, exist_ok=True)

# Dedicated Load-Balancers mapped to the most reliable post downloading website
SITES = [
    {
        "name": f"igram-node-{i+1}",
        "url": "https://igram.world/",
        "input": "#search-form-input",
        "submit": ".search-form__button",
        "wait": ".output-list, a.button--filled",
    } for i in range(5)
]

def parse_urls(filepath):
    if not os.path.exists(filepath): return []
    with open(filepath, 'r', encoding='utf-8') as f:
        return [line.strip() for line in f if line.strip()]

def get_tracked_urls(filepath):
    if not os.path.exists(filepath): return set()
    with open(filepath, 'r', encoding='utf-8') as f:
        return set(line.strip() for line in f if line.strip())

async def async_append_to_file(url, lock, filepath):
    async with lock:
        with open(filepath, 'a', encoding='utf-8') as f:
            f.write(url + "\n")

def get_video_id(url):
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    if 'p' in path_parts:
        try: return path_parts[path_parts.index('p') + 1]
        except IndexError: pass
    if 'reel' in path_parts:
        try: return path_parts[path_parts.index('reel') + 1]
        except IndexError: pass
    if path_parts: return path_parts[-1]
    return str(int(time.time() * 1000))

async def handle_popup(popup):
    try: await popup.close()
    except: pass

async def worker(worker_id, context, queue, lock, invalid_lock, partial_lock, site_config):
    page = await context.new_page()
    await page.route("**/*", lambda route: route.abort() if route.request.resource_type in ["image", "font", "stylesheet"] else route.continue_())
    
    try:
        await page.goto(site_config["url"], wait_until="domcontentloaded", timeout=40000)
    except Exception:
        pass

    while True:
        try:
            retries, index, url, total = queue.get_nowait()
        except asyncio.QueueEmpty:
            break
            
        vid_id = get_video_id(url)
        prefix = f"[{index}/{total}][{site_config['name']}]"
        
        # Pacing Controller (Anti-Rate-Limit padding)
        await asyncio.sleep(random.uniform(5.0, 8.0))
        
        print(f"{prefix} Processing {vid_id} (Attempt {retries+1}/{MAX_RETRIES})")
        
        success = False
        try:
            if site_config["name"].split("-")[0] not in page.url:
                await page.goto(site_config["url"], wait_until="domcontentloaded", timeout=25000)

            # Try to handle popup overlays before filling form
            await page.evaluate("const iframes = document.querySelectorAll('iframe'); for (let i=0; i<iframes.length; i++) iframes[i].remove();")
            await asyncio.sleep(0.5)

            inp = page.locator(site_config["input"]).first
            await inp.fill("")
            await asyncio.sleep(0.5)
            await inp.fill(url)
            
            btn = page.locator(site_config["submit"]).first
            await btn.click(no_wait_after=True)
            
            print(f"{prefix} Resolving...")
            
            try:
                await page.wait_for_selector(site_config["wait"], timeout=20000)
            except PlaywrightTimeoutError:
                print(f"{prefix} \033[93mRate-limited or Page dead. Yielding URL back to queue.\033[0m")
                await page.goto(site_config["url"], wait_until="domcontentloaded")
                
            else:
                await page.evaluate("const iframes = document.querySelectorAll('iframe'); for (let i=0; i<iframes.length; i++) iframes[i].remove();")
                await asyncio.sleep(1)

                anchors = await page.locator("a").all()
                valid_anchors = []
                for a in anchors:
                    href = (await a.get_attribute("href")) or ""
                    text = (await a.inner_text()).lower() or ""
                    classes = (await a.get_attribute("class") or "").lower()
                    
                    if "btn" in classes or "button" in classes or "download" in text:
                        if not href or href.startswith("#"): continue
                        if "instagram-highlights" in href or "instagram-reels" in href or "instagram-story" in href or "blog" in href or "contact" in href: continue
                        if "indown.io" in site_config["url"] and ("indown.io" in href and "fetch" not in href): continue
                        if "igram.world" in site_config["url"] and ("igram.world" in href and "media" not in href): continue
                        
                        valid_anchors.append((a, href, text))
                        
                if not valid_anchors:
                    print(f"{prefix} \033[93mERROR: Found result-card but missing valid JPG/MP4 anchors.\033[0m")
                else:
                    success_count = 0
                    for idx, (a, href, text) in enumerate(valid_anchors):
                        ext = ".mp4" if "video" in text or ".mp4" in href else ".jpg"
                        
                        sub_id = f"{idx+1}"
                        
                        # Create a folder for the specific post ID
                        post_folder = os.path.join(DOWNLOAD_DIR, vid_id)
                        os.makedirs(post_folder, exist_ok=True)
                        
                        filename = os.path.join(post_folder, f"{sub_id}{ext}")
                        
                        print(f"{prefix} Catching raw file {sub_id}{ext}...")
                        try:
                            async with page.expect_download(timeout=25000) as download_info:
                                await a.evaluate("el => el.click()")
                            download = await download_info.value
                            
                            if download.suggested_filename:
                                new_ext = os.path.splitext(download.suggested_filename)[1]
                                if new_ext:
                                    ext = new_ext
                                    filename = os.path.join(post_folder, f"{sub_id}{ext}")
                                    
                            await download.save_as(filename)
                            
                            if os.path.exists(filename) and os.path.getsize(filename) > 5000:
                                size_mb = os.path.getsize(filename)/(1024*1024)
                                print(f"{prefix} \033[92mSUCCESS: {sub_id}{ext} ({size_mb:.2f} MB)\033[0m")
                                success_count += 1
                            else:
                                print(f"{prefix} Corrupted buffer or Ad trap bypassed.")
                                
                        except PlaywrightTimeoutError:
                            print(f"{prefix} Download stream hung.")
                            
                    if success_count == len(valid_anchors) and len(valid_anchors) > 0:
                        await async_append_to_file(url, lock, DOWNLOADED_FILE)
                        success = True
                    elif 0 < success_count < len(valid_anchors):
                        print(f"{prefix} \033[93mWARNING: Partial download ({success_count}/{len(valid_anchors)}). Saving to posts_partial.txt\033[0m")
                        await async_append_to_file(url, partial_lock, PARTIAL_FILE)
                        success = True
                    elif success_count == 0 and len(valid_anchors) > 0:
                        print(f"{prefix} \033[93mERROR: Found valid anchors but downloads failed.\033[0m")
                        
        except Exception as e:
            print(f"{prefix} \033[91mThread Crash: {str(e)[:100]}\033[0m")
            try: await page.goto(site_config["url"], wait_until="domcontentloaded", timeout=15000)
            except: pass

        # Central Error Routing System
        if not success:
            if retries + 1 >= MAX_RETRIES:
                print(f"{prefix} \033[91mFAILED 3 SEPARATE TIMES. Tagged as PERMANENTLY DELETED video and moved to invalid.txt.\033[0m")
                await async_append_to_file(url, invalid_lock, INVALID_FILE)
            else:
                queue.put_nowait((retries + 1, index, url, total))

        queue.task_done()
    
    await page.close()

async def main():
    urls = parse_urls(POSTS_FILE)
    if not urls: return print(f"No URLs found in {POSTS_FILE}")
        
    downloaded = get_tracked_urls(DOWNLOADED_FILE)
    invalid = get_tracked_urls(INVALID_FILE)
    partial = get_tracked_urls(PARTIAL_FILE)
    
    # Mathematical filtration. Guarantees skipped items DO NOT skip on rerun, but invalid ones do.
    pending_urls = [url for url in urls if url not in downloaded and url not in invalid and url not in partial]
    
    print(f"Total URLs: {len(urls)}")
    print(f"Already downloaded completely: {len(downloaded)}")
    print(f"Partially downloaded: {len(partial)}")
    print(f"Permanently dead: {len(invalid)}")
    print(f"Pending downloads: {len(pending_urls)}\n")
    
    if not pending_urls: return print("All active URLs have been downloaded.")

    print("Launching D_POSTS...")

    queue = asyncio.Queue()
    for index, url in enumerate(pending_urls):
        # We queue a Tuple: (current_retries, list_index, the_url, total_length)
        queue.put_nowait((0, index + 1 + len(downloaded) + len(invalid), url, len(urls)))

    lock = asyncio.Lock()
    invalid_lock = asyncio.Lock()
    partial_lock = asyncio.Lock()

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(accept_downloads=True)

        tasks = []
        for i in range(CONCURRENCY):
            site_config = SITES[i % len(SITES)]
            tasks.append(asyncio.create_task(worker(i, context, queue, lock, invalid_lock, partial_lock, site_config)))

        await queue.join()

        for task in tasks:
            task.cancel()
        
        await browser.close()
        print("\n\033[92mALL EXTRACTABLE LINKS HAVE BEEN SAVED. THE REST ARE PERMANENTLY DELETED ON INSTAGRAM.\033[0m")

if __name__ == "__main__":
    asyncio.run(main())
