import traceback
import types
from json import dumps
from typing import Any, Optional, Union, List

import discord
from discord.ext import commands

from utils import CustomContext


def _serialize_user(user: Union[discord.User, discord.Member]) -> dict:
    return {
        "id": user.id,
        "username": user.name,
        "avatar": user.avatar,
        "discriminator": user.discriminator,
        "publicFlags": user.public_flags.value,
        "bot": user.bot,
        "system": user.system,
        "nick": getattr(user, "nick", None),
        "_guild_id": getattr(user, "guild", None) and user.guild.id
    }


def _serialize_channel(channel: discord.TextChannel) -> dict:
    return {
        "id": channel.id,
        "parent_id": channel.category_id,
        "position": channel.position,
        "type": channel._type,
        "nsfw": channel.nsfw,
        "topic": channel.topic
    }


def _serialize_guild(guild: discord.Guild) -> dict:
    return {
        "id": guild.id,
        "owner_id": guild.owner_id,
        "members": guild.member_count,
        "mfa_level": guild.mfa_level,
        "unavailable": guild.unavailable,
        "name": guild.name,
        "features": guild.features,
        "premium_tier": guild.premium_tier,
        "preferred_locale": guild.preferred_locale
    }


def _serialize_attachments(message: discord.Message):
    if not message.attachments:
        return []

    return [{
        "content_type": attachment.content_type,
        "filename": attachment.filename,
        "id": attachment.id,
        "height": attachment.height,
        "width": attachment.width,
        "proxy_url": attachment.proxy_url,
        "size": attachment.size,
        "url": attachment.url,
        "spoiler": attachment.is_spoiler()
    } for attachment in message.attachments]


def _serialize_stickers(message: discord.Message) -> list:
    return [
        {
            "id": x.id,
            "name": x.name,
            "description": x.description,
            "pack": x.pack_id,
            "image": x.image,
            "preview_image": x.preview_image,
            "tags": x.tags,
            "format": x.format.value
        } for x in message.stickers
    ]


def _serialize_reference(message: discord.Message) -> Optional[dict]:
    return message.reference.to_dict() if message.reference else None


def _serialize_message(message: discord.Message) -> dict:
    return {
        "id": message.id,
        "webhook_id": message.webhook_id,
        "content": message.content,
        "pinned": message.pinned,
        "flags": message.flags.value,
        "mention_everyone": message.mention_everyone,
        "mentions": message.raw_mentions,
        "channel_mentions": message.raw_channel_mentions,
        "role_mentions": message.raw_role_mentions,
        "reference": _serialize_reference(message),
        "stickers": _serialize_stickers(message),
        "embeds": [e.to_dict() for e in message.embeds],
        "author": _serialize_user(message.author),
        "channel": _serialize_channel(message.channel),
        "guild": message.guild and _serialize_guild(message.guild),
        "tts": message.tts,
        "attachments": _serialize_attachments(message)
    }


def serialize_context(ctx: commands.Context) -> dict:
    return {
        "message": _serialize_message(ctx.message),
        "args": [default_serialization(x) for x in ctx.args if not isinstance(x, commands.Context)],
        "kwargs": {x: default_serialization(y) for x, y in ctx.kwargs.items()},
        "prefix": ctx.prefix,
        "invoked_with": ctx.invoked_with,
        "command": ctx.command and ctx.command.qualified_name
    }


VALID_SERIALIZATIONS = {
    int: int,
    str: str,
    bool: bool,
    discord.Message: _serialize_message,
    discord.User: _serialize_user,
    discord.Member: _serialize_user,
    discord.TextChannel: _serialize_channel,
    discord.Guild: _serialize_guild,
    commands.Context: serialize_context,
    CustomContext: serialize_context
}


def default_serialization(obj: Any) -> Union[dict, str]:
    if type(obj) in VALID_SERIALIZATIONS:
        return VALID_SERIALIZATIONS[type(obj)](obj)

    if type(obj) is types.ModuleType:
        return f"<module {obj.__package__ or obj.__name__}>"

    return f"{obj!r}"


def serialize_tb_frame(frame: types.TracebackType) -> dict:
    return {
        "filename": frame.tb_frame.f_code.co_filename,
        "function": frame.tb_frame.f_code.co_name,
        "lineno": frame.tb_lineno
    }


def serialize_traceback(frame: types.TracebackType) -> List[dict]:
    frames = []
    current = frame
    frames.append(serialize_tb_frame(current))

    while current.tb_next is not None:
        current = current.tb_next
        frames.append(serialize_tb_frame(current))

    return frames


class Serialized:
    def __init__(self, error: Exception, ctx: CustomContext):
        self.error = str(error)
        self.traceback = "".join(traceback.format_exception(type(error), error, error.__traceback__))
        self.frames = serialize_traceback(error.__traceback__)
        self.context = serialize_context(ctx)

        self.filename = self.frames[-1]["filename"]
        self.function = self.frames[-1]["function"]

    def to_dict(self) -> dict:
        return {
            "error": self.error,
            "traceback": self.traceback,
            "frames": self.frames,
            "context": [self.context],
            "filename": self.filename,
            "function": self.function
        }
