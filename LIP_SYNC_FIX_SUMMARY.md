# Lip Sync Fix - Summary

## Problem
Lip sync was not working - no mouth movement visible when robot speaks.

## Root Cause
The queue processing logic in `robo.py` had a critical flaw:

**Old Logic Flow:**
1. Check if `viseme_timer == 0` → process phoneme
2. Increment timer
3. When timer expires, only check if queue is done
4. **BUG**: Never processes next phoneme after first one!

The issue was that the code only processed phonemes when `viseme_timer == 0`, but after the first phoneme, the timer was incremented and never reset to 0 until the next `set_phoneme()` call. However, `set_phoneme()` was only called when `viseme_timer == 0`, creating a deadlock.

## Solution

### 1. Fixed Queue Processing Logic (`robo.py` lines 291-310)
**Changed from:**
```python
if viseme_timer == 0:  # Only when exactly 0
    process_phoneme()
    
if viseme_timer < viseme_duration:
    increment_timer()
else:
    check_if_done()  # Doesn't process next!
```

**To:**
```python
if viseme_timer >= viseme_duration:  # Check expiration first
    if queue_has_more:
        process_next_phoneme()  # Process next one
    else:
        finish_lip_sync()
else:
    increment_timer()  # Keep current viseme
```

### 2. Fixed Initial State (`voice_robot.py` lines 193-197)
- Set `viseme_timer = 999` to trigger immediate processing of first phoneme
- Set `viseme_duration = 0` so first check succeeds
- First `set_phoneme()` call sets proper duration and resets timer

## How It Works Now

1. **Setup Phase** (in background thread):
   - Generate TTS audio
   - Create phoneme queue from text
   - Enable lip sync
   - Initialize timer to trigger first phoneme

2. **Processing Phase** (in main loop):
   - Each frame, `robot.update()` is called
   - Check if current viseme timer has expired
   - If expired and queue has more: process next phoneme
   - If expired and queue is empty: finish lip sync
   - Otherwise: increment timer and keep current viseme

3. **Rendering Phase** (in main loop):
   - `robot.draw_face()` is called
   - `draw_mouth()` checks `lip_sync_enabled`
   - If enabled: calls `draw_mouth_viseme()` with current viseme
   - Mouth shape changes based on viseme (A, E, I, O, U, MBP, etc.)

## Expected Behavior

When you press 'T' to talk:
1. Robot records audio
2. Converts to text
3. Gets AI reply
4. **Lip sync activates** - mouth should move
5. Each character maps to a viseme (mouth shape)
6. Mouth changes shape as robot speaks
7. Lip sync deactivates when speech completes

## Testing

Run the program and press 'T'. You should see:
- Debug message: `🔊 Lip sync: enabled=True, queue=X chars...`
- Mouth shapes changing (A=wide open, E=horizontal, O=round, etc.)
- Debug output every 0.5 seconds showing current viseme

## Files Modified

1. **robo.py** - Fixed queue processing logic
2. **voice_robot.py** - Fixed initial state setup
3. **LIP_SYNC_ANALYSIS.md** - Analysis document (for reference)

## Technical Details

- **FPS**: 60 frames per second
- **Phoneme Duration**: Calculated as `(audio_duration / text_length) * FPS`, clamped to 4-12 frames
- **Viseme Types**: A, E, I, O, U, MBP, FV, TD, KG, NNG, L, R, WQ, SZ, CHSH, SILENCE, OPEN
- **Thread Safety**: Queue setup in background thread, processing in main thread (works because Python GIL ensures atomic operations on simple data structures)
