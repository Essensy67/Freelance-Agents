"""Command-line entry point for Freelance Agents."""

import asyncio

from freelance_agents.application import Application


def main() -> None:
    """Run the Freelance Agents application."""
    asyncio.run(Application().run())


if __name__ == "__main__":
    main()
