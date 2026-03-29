from unittest.mock import AsyncMock

import pytest

from nanobot.bus.queue import MessageBus
from nanobot.channels.discord import DiscordChannel, DiscordConfig


@pytest.mark.asyncio
async def test_discord_ignores_messages_from_unmapped_channels() -> None:
    channel = DiscordChannel(
        DiscordConfig(
            enabled=True,
            token="x",
            allow_from=["*"],
            allow_channel_ids=["allowed-channel"],
        ),
        MessageBus(),
    )
    channel._handle_message = AsyncMock()

    await channel._handle_message_create(
        {
            "id": "m1",
            "channel_id": "other-channel",
            "author": {"id": "u1", "bot": False},
            "content": "hello",
        }
    )

    channel._handle_message.assert_not_called()


@pytest.mark.asyncio
async def test_discord_handles_messages_from_allowed_channels() -> None:
    channel = DiscordChannel(
        DiscordConfig(
            enabled=True,
            token="x",
            allow_from=["*"],
            allow_channel_ids=["allowed-channel"],
        ),
        MessageBus(),
    )
    channel._handle_message = AsyncMock()
    channel._start_typing = AsyncMock()

    await channel._handle_message_create(
        {
            "id": "m1",
            "channel_id": "allowed-channel",
            "author": {"id": "u1", "bot": False},
            "content": "hello",
        }
    )

    channel._handle_message.assert_awaited_once()
