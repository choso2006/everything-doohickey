import sys
import subprocess
import threading
import time
import os

try:
    import winsound
except ImportError:
    winsound = None

def _play_thread(event, mode, custom_text):
    if mode == "off":
        return
        
    try:
        # MAC SOUNDS
        if sys.platform == "darwin":
            if event == "success":
                if mode == "voice" and custom_text:
                    subprocess.Popen(["say", custom_text])
                elif mode == "cute":
                    # Mac Tink sound (soft and cute)
                    subprocess.Popen(["afplay", "/System/Library/Sounds/Tink.aiff"])
                elif mode == "pop":
                    subprocess.Popen(["afplay", "/System/Library/Sounds/Pop.aiff"])
                elif mode == "tada":
                    subprocess.Popen(["afplay", "/System/Library/Sounds/Funk.aiff"])
                else: # chime
                    subprocess.Popen(["afplay", "/System/Library/Sounds/Glass.aiff"])
                    
            elif event == "error":
                if mode == "voice":
                    subprocess.Popen(["say", "Oh no, something went wrong."])
                else:
                    subprocess.Popen(["afplay", "/System/Library/Sounds/Basso.aiff"])
            return

        # WINDOWS SOUNDS
        if winsound and sys.platform == "win32":
            if event == "success":
                if mode == "cute":
                    winsound.Beep(523, 100)
                    time.sleep(0.05)
                    winsound.Beep(659, 100)
                    time.sleep(0.05)
                    winsound.Beep(784, 200)
                elif mode == "voice" and custom_text:
                    safe_text = custom_text.replace("'", "''").replace('"', '')
                    cmd = f"Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('{safe_text}')"
                    subprocess.Popen(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                elif mode == "pop":
                    winsound.Beep(400, 60)
                elif mode == "tada":
                    winsound.PlaySound("SystemStart", winsound.SND_ALIAS | winsound.SND_ASYNC)
                else: # chime
                    winsound.PlaySound("SystemAsterisk", winsound.SND_ALIAS | winsound.SND_ASYNC)
                    
            elif event == "error":
                if mode == "cute":
                    winsound.Beep(392, 150)
                    time.sleep(0.05)
                    winsound.Beep(330, 250)
                elif mode == "voice":
                    cmd = "Add-Type -AssemblyName System.Speech; (New-Object System.Speech.Synthesis.SpeechSynthesizer).Speak('Oh no, something went wrong.')"
                    subprocess.Popen(["powershell", "-Command", cmd], creationflags=subprocess.CREATE_NO_WINDOW)
                elif mode == "pop":
                    winsound.Beep(300, 100)
                else:
                    winsound.PlaySound("SystemHand", winsound.SND_ALIAS | winsound.SND_ASYNC)
    except Exception:
        pass

def play(event, mode="chime", custom_text=""):
    """Plays a minimal sound effect based on the user's setting."""
    threading.Thread(target=_play_thread, args=(event, mode, custom_text), daemon=True).start()