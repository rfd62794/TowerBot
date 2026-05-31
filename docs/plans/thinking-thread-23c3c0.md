# Thinking Thread — Rotating Status Messages

Add `_thinking_thread()` to `bot/transport.py` so slow responses show a rotating status message instead of silent typing.

## Changes — `bot/transport.py` only

**Add at module level:**
```python
THINKING_MESSAGES = [
    "⚙️ Working...",
    "💭 Still thinking...",
    "🔍 Checking sources...",
    "⚙️ Processing...",
    "💭 Almost there...",
    "🔄 Pulling it together...",
]
```

**Add coroutine:**
```python
async def _thinking_thread(chat_id, bot, stop_event):
    await asyncio.sleep(2)          # grace period — fast replies show nothing
    if stop_event.is_set():
        return
    msg = await bot.send_message(chat_id, THINKING_MESSAGES[0])
    i = 1
    while not stop_event.is_set():
        await asyncio.sleep(3)
        if stop_event.is_set():
            break
        try:
            await bot.edit_message_text(THINKING_MESSAGES[i % len(THINKING_MESSAGES)], chat_id, msg.message_id)
            i += 1
        except Exception:
            pass
    try:
        await bot.delete_message(chat_id, msg.message_id)
    except Exception:
        pass
```

**Update `handle_message()`:**
- Create `_thinking_thread` task alongside `_keep_typing`
- Pass same `stop` event (already set in `finally`)
- Cancel both tasks in `finally`

## Tests — `tests/test_transport.py` (+3)

| Test | What it checks |
|------|---------------|
| `test_thinking_thread_skips_on_fast_response` | stop_event set before 2s grace → `send_message` never called |
| `test_thinking_thread_sends_and_rotates` | after 2s send_message called; after 5s edit_message_text called |
| `test_thinking_thread_deletes_on_completion` | after stop_event set, delete_message called |

## Count
298 + 3 = **301 tests**
