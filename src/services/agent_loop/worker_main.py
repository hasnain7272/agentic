import asyncio
import logging
import os
import sys

root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
if root not in sys.path:
    sys.path.insert(0, root)

from src.infrastructure.db.session import AsyncSessionLocal, init_db
from src.infrastructure.queue.redis_streams_broker import get_streams_broker
from src.services.agent_loop.brain import BrainWorker
from src.services.agent_loop.tool_worker import ToolWorker

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("worker")


async def _run_task_worker(brain: BrainWorker):
    broker = await get_streams_broker()
    logger.info("[Worker] Subscribing to task_queue...")
    
    async def handle(message):
        logger.info(f"[Brain] Processing: {message.data.get('task_id', 'unknown')}")
        async with AsyncSessionLocal() as db:
            await brain.process_task_event(message.data, db)
    
    await broker.subscribe("task_queue", "brain-workers", handle)


async def _run_tool_worker(tool_worker: ToolWorker):
    broker = await get_streams_broker()
    logger.info("[Worker] Subscribing to execution_queue...")
    
    async def handle(message):
        logger.info(f"[ToolWorker] Processing: {message.data.get('tool', 'unknown')}")
        async with AsyncSessionLocal() as db:
            await tool_worker.process_tool_event(message.data, db)
    
    await broker.subscribe("execution_queue", "tool-workers", handle)


async def start_worker(init_database: bool = True):
    if init_database:
        await init_db()
    
    brain = BrainWorker()
    tool_worker = ToolWorker()

    logger.info("Worker runtime started (PID: %s)", os.getpid())
    
    # Run as separate tasks, not gather (gather cancels on error)
    task1 = asyncio.create_task(_run_task_worker(brain))
    task2 = asyncio.create_task(_run_tool_worker(tool_worker))
    
    try:
        await asyncio.gather(task1, task2)
    except asyncio.CancelledError:
        logger.info("Worker cancelled")
        task1.cancel()
        task2.cancel()


if __name__ == "__main__":
    asyncio.run(start_worker())