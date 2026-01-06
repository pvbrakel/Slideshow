# Pygame Slideshow

Minimal fullscreen slideshow application using Pygame.

Install (Windows):

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

Install (Raspberry pi):

```sh
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
sudo apt-get install python3-sdl2 libopenjp2-7 libegl-dev

```

Run:

```powershell
python main.py
```

Configuration is in `settings.json` (folders, interval, night-mode, transition).
