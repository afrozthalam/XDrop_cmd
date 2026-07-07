# XDrop_CMD

This is a simple tool to download Instagram Reels, Photos, and Videos directly to your computer.

---

## How to Install

1. Make sure you have Python installed on your computer.
2. Open your terminal or command prompt and run these commands to install the required tools:
   ```bash
   pip install playwright requests
   playwright install chromium
   ```

---

## How to Use

### 1. Download Instagram Reels
1. Open the file `reels.txt` and paste the Instagram Reel links you want to download (one link per line).
2. Run the script:
   ```bash
   python d_reels.py
   ```
3. The downloaded videos will be saved in the `downloads` folder.
4. Already downloaded reels are listed in `downloaded.txt` so they are not downloaded again.

### 2. Download Instagram Posts (Photos & Carousels)
1. Create a file named `posts.txt` and paste the Instagram Post links you want to download (one link per line).
   *(Note: If you have a file named `saved posts.txt`, rename it to `posts.txt`)*
2. Run the script:
   ```bash
   python d_posts.py
   ```
3. The downloaded photos/videos will be saved in the `posts_downloads` folder.

---

## Credits
Created by **Afroz Alam**
