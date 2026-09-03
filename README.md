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

The current version does not add persistent globals or custom registered events to new saves. Saves made with this version can therefore be loaded after the mod is disabled.

The original release added `FGA_LastTimeScaleCounter` and a saved `FGA_UpdateLogTiming` frame handler. Saves made with that release may retain those entries. Use `tools/faster_game_acceleration_save_cleanup.py` to create a cleaned copy before loading such a save without the mod:

```powershell
py .\tools\faster_game_acceleration_save_cleanup.py ".\input save" ".\output save"
```

The input save is never overwritten. Keep it as a backup until the cleaned copy has been tested.

## Compatibility

Designed for **Caribbean Legend: Age of Pirates 1.2**.
