# BWS Tracker — Mobile App  v1.0
Water Gallon Delivery Tracker  |  Built with Python + Kivy

---

## What's Inside

| File             | Purpose                                  |
|------------------|------------------------------------------|
| `main.py`        | Full application (UI + database + logic) |
| `buildozer.spec` | Android / iOS build configuration        |
| `requirements.txt` | Python dependencies                    |

---

## Option A — Run on Desktop First (Test before building)

### 1. Install Python 3.11+
Download from https://python.org

### 2. Install dependencies

**Windows:**
```
pip install kivy reportlab
```

**Mac / Linux:**
```
pip3 install kivy reportlab
```

### 3. Run the app
```
python main.py          # Windows
python3 main.py         # Mac / Linux
```

The app will open in a window. This is exactly how it looks on a phone.

---

## Option B — Build Android APK

### Requirements
- Ubuntu / Debian Linux (or WSL2 on Windows)
- Python 3.11+
- Java JDK 17+

### Step 1 — Install Buildozer
```bash
pip3 install buildozer cython
sudo apt-get install -y \
    git zip unzip openjdk-17-jdk \
    python3-pip autoconf libtool \
    pkg-config zlib1g-dev libncurses5-dev \
    libncursesw5-dev libtinfo5 cmake \
    libffi-dev libssl-dev
```

### Step 2 — Build
```bash
cd bws_tracker_mobile
buildozer android debug
```

First build downloads Android SDK/NDK automatically (~2–4 GB, takes 20–40 min).
Subsequent builds are fast (~2 min).

### Step 3 — Install on phone
Connect your Android phone via USB with USB Debugging enabled, then:
```bash
buildozer android deploy run
```

Or copy the `.apk` from `bin/` to your phone and open it.

The APK file will be at:
```
bin/bwstracker-1.0-arm64-v8a_armeabi-v7a-debug.apk
```

---

## Option C — Build iOS App

> Requires: macOS, Xcode 14+, Apple Developer account ($99/year)

```bash
pip3 install kivy-ios
toolchain build python3 kivy
toolchain create BWS-Tracker .
open BWS-Tracker-ios/BWS-Tracker.xcodeproj
```

Then build and run from Xcode.

---

## App Features

- **Add Orders** — Customer name, gallon type (Round / Slim / Both), refill or borrow, water price, deposit, delivery time
- **View Orders** — Filter by any date, see all orders with totals strip
- **Daily Metrics** — Gross water sales, container deposits, combined cash inflow
- **Export CSV** — Structured spreadsheet saved to Downloads
- **Export PDF** — Professional receipt with blue header and totals (requires ReportLab)
- **Customer List** — All registered customers

### Data Storage
- Database: `water_tracker.db` (auto-created on first launch)
- Android: stored in app's private data directory
- Exports: saved to `/storage/emulated/0/Download/` on Android, current folder on desktop

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `kivy` not found | Run `pip install kivy` |
| Black screen on launch | Check Python version is 3.11+ |
| Build fails on first run | Let it finish — first build downloads ~2 GB |
| PDF export unavailable | Run `pip install reportlab` |
| Android file permission denied | Allow "Files and media" in app settings |
