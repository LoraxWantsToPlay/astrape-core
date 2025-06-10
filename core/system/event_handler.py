import asyncio
from listen.events import EventType

class EventQueue:
    def __init__(self):
        self.queue = asyncio.Queue()

    async def put(self, event: EventType):
        await self.queue.put(event)

    async def get(self) -> EventType:
        return await self.queue.get()

    def empty(self) -> bool:
        return self.queue.empty()

async def process_event_async(even_type, orchestrator):
    if even_type == EventType.EMERGENCY:
        await orchestrator.execute_emergency_protocol()
    elif even_type == EventType.WAKE:
        orchestrator.set_state("awake")
    elif even_type == EventType.SLEEP:
        orchestrator.set_state("asleep")
    elif even_type == EventType.SHUTDOWN:
        exit(0)
    else:
        orchestrator.logger.warning(f"Unknown event: {even_type}")
