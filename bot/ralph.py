"""
RALPH — Robert's Always-Learning, Proactive Helper.
Persistent async loop. Always on. Everything else is an interrupt.
"""
import asyncio
import logging
import random
from asyncio import PriorityQueue
from typing import Optional

from infra.utils import notify, safe_serialize, get_task_type
from bot.autonomous import _pick_background_task

logger = logging.getLogger("privy.ralph")

# Priority levels — lower number = higher priority
PRIORITY_MESSAGE = 1
PRIORITY_URGENT = 2
PRIORITY_SCHEDULED = 3
PRIORITY_BACKGROUND = 10

# Interest threshold for autonomous deep dive trigger
DEEP_DIVE_THRESHOLD = 0.7


class Ralph:
    """Persistent always-on overseer. Wraps existing systems, never replaces them."""

    def __init__(self):
        self.queue: PriorityQueue = PriorityQueue()
        self.running: bool = False
        self._current_bg_task: Optional[asyncio.Task] = None
        self._deep_dive_candidates: list[str] = []

    async def start(self):
        """Start RALPH. Call from bot startup alongside APScheduler and Telegram."""
        self.running = True
        logger.info("[ralph] Starting — persistent loop active")
        await self._main_loop()

    async def stop(self):
        self.running = False
        if self._current_bg_task:
            self._current_bg_task.cancel()
        logger.info("[ralph] Stopped")

    async def push(self, priority: int, event: dict):
        """
        Push an event to Ralph's queue.
        High-priority events (1-3) interrupt current background work.
        """
        await self.queue.put((priority, event))

        # Interrupt background work for high-priority events
        if priority <= PRIORITY_SCHEDULED and self._current_bg_task:
            logger.info(f"[ralph] Interrupting background work for priority {priority} event")
            self._current_bg_task.cancel()

    async def _main_loop(self):
        """Core loop. Check queue. Handle event. Or do background work."""
        while self.running:
            try:
                # Non-blocking check for pending events
                priority, event = self.queue.get_nowait()
                await self._handle_event(priority, event)
                self.queue.task_done()

            except asyncio.QueueEmpty:
                # Nothing pending — do background work
                await self._do_background_work()

            except Exception as e:
                logger.error(f"[ralph] main loop error: {e}")
                await asyncio.sleep(1)

    async def _do_background_work(self):
        """
        Pick and run one background task.
        Interruptible by higher-priority events via push().
        """
        task_prompt = _pick_background_task()
        logger.info(f"[ralph] Starting background work")

        try:
            from bot.autonomous import run_template_task
            from infra.db.autonomous import record_agent_action
            import yaml
            from pathlib import Path

            # Load ralph overseer context
            overseer_path = Path("templates/canonical/ralph_overseer.yaml")
            overseer = ""
            if overseer_path.exists():
                with open(overseer_path, encoding="utf-8") as f:
                    overseer = yaml.safe_load(f).get("prompt", "")

            full_prompt = f"{overseer}\n\n---\n\n{task_prompt}" if overseer else task_prompt

            self._current_bg_task = asyncio.create_task(
                run_template_task("background", prompt_override=full_prompt)
            )

            result = await asyncio.wait_for(
                self._current_bg_task,
                timeout=90  # from config/timeouts.yaml background
            )

            # Evaluate result for autonomous deep dive potential
            if result and isinstance(result, dict):
                await self._evaluate_for_deep_dive(result, task_prompt)

            # Record to agent_actions
            record_agent_action(
                task_name="ralph_background",
                result=safe_serialize(result),
                duration_ms=0
            )

        except asyncio.TimeoutError:
            logger.info("[ralph] Background task timed out — continuing")
        except asyncio.CancelledError:
            logger.info("[ralph] Background task interrupted by higher priority event")
        except Exception as e:
            logger.warning(f"[ralph] Background task error: {e}")
        finally:
            self._current_bg_task = None

    async def _evaluate_for_deep_dive(self, result: dict, task_prompt: str):
        """
        Evaluate background task result for deep dive potential.
        If interesting enough, queue an autonomous deep dive.
        """
        result_text = str(result.get("result", result.get("summary", "")))

        # Simple heuristic: result mentions "worth exploring" or is unusually long
        interesting_signals = [
            "worth exploring",
            "surprising",
            "unexpected",
            "counterintuitive",
            "interesting pattern",
            "deep dive",
        ]

        score = sum(1 for s in interesting_signals if s.lower() in result_text.lower())
        normalized = min(score / 3.0, 1.0)

        if normalized >= DEEP_DIVE_THRESHOLD:
            # Extract topic from task prompt (first 60 chars)
            topic = task_prompt[:60].strip()
            self._deep_dive_candidates.append(topic)
            logger.info(f"[ralph] Deep dive candidate added: {topic[:40]}...")

            # If 2+ candidates accumulated, trigger one
            if len(self._deep_dive_candidates) >= 2:
                candidate = self._deep_dive_candidates.pop(0)
                await self.push(PRIORITY_BACKGROUND, {
                    "type": "deep_dive",
                    "topic": candidate
                })

    async def _handle_event(self, priority: int, event: dict):
        """Route event to correct handler."""
        event_type = event.get("type")
        logger.info(f"[ralph] Handling event: {event_type} (priority {priority})")

        try:
            if event_type == "scheduled_task":
                from bot.autonomous import run_scheduled_task
                await run_scheduled_task(event.get("task_name"))

            elif event_type == "urgent_notify":
                await notify(event.get("message", ""), urgent=True)

            elif event_type == "deep_dive":
                topic = event.get("topic", "")
                if topic:
                    from bot.autonomous import run_template_task
                    logger.info(f"[ralph] Autonomous deep dive: {topic[:40]}...")
                    await asyncio.wait_for(
                        run_template_task("deep_dive", context={"topic": topic}),
                        timeout=300
                    )

            elif event_type == "background":
                # Explicit background task push — handle immediately
                await self._do_background_work()

        except Exception as e:
            logger.error(f"[ralph] Event handling error ({event_type}): {e}")


# Global Ralph instance — import and use across the bot
ralph = Ralph()
