import os
import sys
import win32com.client

def create_desktop_shortcut():
    print("Creating desktop shortcut for Sound IQ...")
    try:
        desktop = os.path.join(os.environ['USERPROFILE'], 'Desktop')
        shortcut_path = os.path.join(desktop, "Sound IQ.lnk")
        
        target = sys.executable
        workdir = os.path.dirname(os.path.abspath(__file__))
        app_script = os.path.join(workdir, "app.py")
        
        target_w = target.lower().replace("python.exe", "pythonw.exe")
        if os.path.exists(target_w):
            target = target_w
            
        arguments = f'"{app_script}"'
        
        shell = win32com.client.Dispatch("WScript.Shell")
        shortcut = shell.CreateShortcut(shortcut_path)
        shortcut.Targetpath = target
        shortcut.WorkingDirectory = workdir
        shortcut.Arguments = arguments
        shortcut.Description = "Sound IQ - Local AI Sound Library"
        
        ico_path = os.path.join(workdir, "soundiq_logo.ico")
        if os.path.exists(ico_path):
            shortcut.IconLocation = ico_path
        else:
            png_path = os.path.join(workdir, "soundiq_logo.png")
            if os.path.exists(png_path):
                shortcut.IconLocation = png_path
            
        shortcut.save()
        print(f"Shortcut created successfully at: {shortcut_path}")
        return True
    except Exception as e:
        print(f"Error creating shortcut: {e}")
        return False

if __name__ == "__main__":
    create_desktop_shortcut()
