import logging
import time

import aiohttp
import disnake
import toml

from disnake.ext import commands

from . import __cogs__
from .statefile import StateFile


logger = logging.getLogger(__name__)


class Steambot(commands.Bot):
    def __init__(self, config_file):
        intents = disnake.Intents(bans=True, emojis=True, guilds=True, members=True,
                                  messages=True, reactions=True, voice_states=False)
        super().__init__(command_prefix='.', help_command=None, intents=intents)
        # enable slash commands

        self.config = toml.load(open(config_file))
        self.state = StateFile(self.config['bot']['state_file'])

        timeout = aiohttp.ClientTimeout(total=60)
        self.session = aiohttp.ClientSession(loop=self.loop, timeout=timeout)

        # load cogs
        for module in __cogs__:
            logger.info(f'Loading extension: {module}')
            self.load_extension('steambot.' + module)

        # set by on_ready
        self.start_time = None
        self.main_guild = None
        # admin ids, set via config, but can be changed at runtime
        self.admins = set(self.config['bot']['admins'])
        self.admins.add(self.config['bot']['owner'])

        self.contrib_role = None
        self.contributors = set()

    async def on_ready(self):
        logger.info('Steambot ready!')
        logger.info(f'Name: {self.user} (ID: {self.user.id})')

        self.start_time = time.time()
        self.main_guild = self.get_guild(self.config['bot']['main_guild'])
        self.contrib_role = self.main_guild.get_role(self.config['bot']['publish_role'])
        if self.contrib_role:
            for user in self.contrib_role.members:
                self.contributors.add(user.id)

    def is_admin(self, user: disnake.Member):
        if user.id in self.admins:
            return True
        return False

    def is_contributor(self, user: disnake.User):
        if user.id in self.admins:
            return True
        elif user.id in self.contributors:
            return True
        return False

    @staticmethod
    def is_private(channel: disnake.TextChannel):
        # DMs
        if isinstance(channel, disnake.abc.PrivateChannel):
            return True
        # Guild channels
        if channel.guild.default_role in channel.overwrites:
            if not channel.overwrites[channel.guild.default_role].pair()[0].read_messages:
                return True
        return False

    async def on_command_error(self, context, exception):
        """Swallow some errors we don't care about"""
        if isinstance(exception, commands.errors.CommandNotFound):
            return
        elif isinstance(exception, commands.errors.MissingRequiredArgument):
            return
        raise exception

    async def close(self):
        logger.info('Cleaning up on close()...')
        await super().close()
        await self.session.close()

    def run(self):
        return super().run(self.config['bot']['token'], reconnect=True)
