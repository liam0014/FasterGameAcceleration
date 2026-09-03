# Faster Game Acceleration

A simple game-speed mod for **Caribbean Legend: Age of Pirates** that increases the maximum acceleration settings while keeping on-screen messages readable.

## Changes

* **Sea:** ×8 → **×16**
* **Sea Battle:** ×6 → **×12**
* **World Map:** ×5 → **×6**
* **Land:** ×3 *(unchanged)*

## Readable Messages at High Speed

Most acceleration mods increase the game speed without adjusting the UI timing.

As a result, log messages and notifications can disappear almost instantly when playing at high acceleration.

Faster Game Acceleration compensates their display time for the current game speed, allowing messages and notifications to remain visible for a reasonable amount of real-world time even at **×16 acceleration**.

## Save Compatibility

The **current version is safe to add or remove during a playthrough**. It does not add persistent globals or custom registered events to new saves, so saves made while this version is installed can still be loaded after the mod is disabled.

### Important: saves made with the original version

The original release created a save-game dependency. It added the global variable `FGA_LastTimeScaleCounter` and registered an `FGA_UpdateLogTiming` frame handler, both of which could be written into a save. Trying to load an affected save after removing the old mod could therefore produce script errors or prevent the save from loading correctly.

The old release is preserved in the [`legacy/save-dependent-version`](https://github.com/liam0014/FasterGameAcceleration/tree/legacy/save-dependent-version) branch for reference, but it is not recommended for normal use.

You only need the cleanup tool if a save was created or resaved while the original, save-dependent version was installed. Saves used only with the current version do not need cleaning.

## Cleaning an old save

The included `tools/faster_game_acceleration_save_cleanup.py` script creates a cleaned copy of an affected save. It removes only:

* `FGA_LastTimeScaleCounter`
* The saved `FGA_UpdateLogTiming` event handler

The save's other script data, metadata and screenshot are preserved. The tool refuses to overwrite its input file and stops with an error if it cannot process the save safely.

### Windows instructions

1. Install [Python 3](https://www.python.org/downloads/) if it is not already installed. During installation, enable the option to add Python to `PATH`.
2. Download this repository using **Code → Download ZIP**, then extract the ZIP.
3. Keep an untouched backup of the affected save.
4. Open the extracted `FasterGameAcceleration-main` folder in File Explorer.
5. Click the File Explorer address bar, type `powershell`, and press **Enter**. PowerShell will open in that folder.
6. Run the following command, replacing the two example paths with the real input and output save paths:

```powershell
py .\tools\faster_game_acceleration_save_cleanup.py "C:\path\to\Affected Save" "C:\path\to\Affected Save - FGA cleaned"
```

Use a new name for the output save. Paths containing spaces must remain inside quotation marks. If Windows does not recognise `py`, try the same command with `python` instead:

```powershell
python .\tools\faster_game_acceleration_save_cleanup.py "C:\path\to\Affected Save" "C:\path\to\Affected Save - FGA cleaned"
```

A successful conversion reports `FasterGameAcceleration save cleanup completed`, followed by the removed variable and handler counts. An affected save will normally report:

```text
Removed variables: FGA_LastTimeScaleCounter
Removed legacy handlers: 1
```

Keep the original save as a backup until the cleaned copy has loaded successfully with Faster Game Acceleration disabled. If the tool reports an error, do not replace or delete the original save.

## Compatibility

Designed for **Caribbean Legend: Age of Pirates 1.2**.
