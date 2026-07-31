from freelance_agents.core.events import Event, EventBus


async def test_event_is_delivered_to_subscriber() -> None:
    event_bus = EventBus()
    received: list[Event] = []

    async def handler(event: Event) -> None:
        received.append(event)

    event_bus.subscribe("work.created", handler)
    event = Event(name="work.created", payload={"source": "test"})

    await event_bus.publish(event)

    assert received == [event]


async def test_event_is_delivered_to_multiple_subscribers() -> None:
    event_bus = EventBus()
    calls: list[str] = []

    async def first_handler(event: Event) -> None:
        calls.append(f"first:{event.name}")

    async def second_handler(event: Event) -> None:
        calls.append(f"second:{event.name}")

    event_bus.subscribe("work.created", first_handler)
    event_bus.subscribe("work.created", second_handler)

    await event_bus.publish(Event(name="work.created", payload={}))

    assert calls == ["first:work.created", "second:work.created"]


async def test_publishing_without_subscribers_is_allowed() -> None:
    event_bus = EventBus()

    await event_bus.publish(Event(name="unhandled.event", payload={}))
