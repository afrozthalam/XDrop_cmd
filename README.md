# XDrop_CMD

A lightweight, concurrent command-line utility suite for downloading Instagram Reels, Posts, and Carousels. By utilizing asynchronous browser automation via Playwright and multi-threaded scraping, `XDrop_CMD` bypasses ad traps and rate limits to download media locally.

---

## Features

### 1. Reels Downloader (`d_reels.py`)
- **Multi-Source Scraping:** Sequentially tries 5 different working third-party downloader sites (e.g., `saveinsta.io`, `savereels.io`, etc.) until a valid download link is retrieved.
- **10x Concurrency:** Processes up to 10 Reels concurrently.
- **Fast Downloading:** Intercepts and downloads the video files using standard HTTP requests (streaming) instead of running slow downloads through the browser instance.
- **Quality Control:** Filters out preview thumbnails (discards files under 300 KB) to ensure only full video files are saved.

### 2. Post & Carousel Downloader (`d_posts.py`)
- **Multi-Slide Carousels:** Automatically identifies and downloads all images and videos from carousel posts.
- **5x Concurrency:** Employs 5 concurrent browser workers.
- **Bandwidth Optimization:** Automatically blocks fonts, images, and stylesheets from loading during parsing to speed up execution.
- **Ad & Popup Bypass:** Injects custom Javascript to strip intrusive iframe ad overlays.
- **Status Routing:** Automatically categorizes URLs into Successful (`posts_downloaded.txt`), Partial (`posts_partial.txt`), or Permanently Dead (`posts_invalid.txt`) after 3 failed attempts.

---

## Prerequisites

Before running the scripts, make sure you have Python 3 and the required dependencies installed:

```bash
pip install playwright requests
playwright install chromium
```

---

## Project Structure & File Setup

For the scripts to locate your target URLs, set up the following files in the project root directory:

1. **Reels Input:** Put your Instagram Reel URLs in `reels.txt` (one URL per line).
2. **Posts Input:** Put your Instagram Post/Carousel URLs in `posts.txt` (one URL per line).
   > *Note: If your local input file is named `saved posts.txt`, rename it to `posts.txt` so the script can find it.*

---

## Usage

### Downloading Reels
Run the following command to download Reels:
```bash
python d_reels.py
```
- **Output:** Media files will be saved in the `downloads/` directory.
- **Tracking:** Successfully downloaded Reel IDs are stored in `downloaded.txt` so they are skipped on subsequent runs.

### Downloading Posts & Carousels
Run the following command to download Posts and Carousels:
```bash
python d_posts.py
```
- **Output:** Sub-folders for each post ID will be created in `posts_downloads/` containing the slide images/videos.
- **Tracking:** Results are tracked in `posts_downloaded.txt`, `posts_partial.txt`, and `posts_invalid.txt`.

---

## Credits
- Developed by **Parrot**
- Powered by [Playwright for Python](https://github.com/microsoft/playwright-python)
