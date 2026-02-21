# Virtual Keyboard (PyQt5 + pynput)

A beginner-friendly desktop app for Windows with:
- A floating keyboard button on the right side of the screen
- Always-on-top behavior
- Expand/collapse virtual keyboard window
- Dark modern UI styling
- Key simulation using `pynput`

## Features

- Floating launcher button (`⌨`) on the right side of the screen
- Clicking launcher opens full virtual keyboard window
- Keyboard includes:
  - `A-Z`
  - `0-9`
  - `Enter`
  - `Backspace`
  - `Space`
- Hide button collapses keyboard back to launcher
- Uses `pynput.keyboard.Controller` to simulate real key presses

## Project Files

- `main.py` - application source code
- `requirements.txt` - dependencies

## Run Locally

1. Open PowerShell in project folder.
2. (Optional) Create and activate virtual environment.
3. Install dependencies:

```powershell
pip install -r requirements.txt
```

4. Start app:

```powershell
python main.py
```

## Build `.exe` with PyInstaller

Run this command in the project root:

```powershell
pyinstaller --noconfirm --onefile --windowed --name KeyboardGod main.py
```

After build finishes, your executable is here:

- `dist\KeyboardGod.exe`

### Notes for Windows 7/10/11

- Use a Python version supported by your target OS.
  - For best Windows 7 compatibility, Python 3.8 is commonly used.
  - Windows 10/11 work well with newer Python versions.
- Build on the same Windows version you plan to deploy to when possible.
- If Defender/SmartScreen flags unsigned binaries, this is expected for unsigned custom apps.

## Optional: Custom Icon for `.exe`

If you have `app.ico`:

```powershell
pyinstaller --noconfirm --onefile --windowed --icon app.ico --name KeyboardGod main.py
```

## Troubleshooting

- If key input is blocked in some admin windows, run app as Administrator.
- If keyboard is not visible, check if another always-on-top app is covering it.
- If PyInstaller build fails, update pip tools:

```powershell
python -m pip install --upgrade pip setuptools wheel
```
