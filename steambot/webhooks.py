import asyncio
import logging

from aiohttp import web
from disnake.ext.commands import Cog

logger = logging.getLogger(__name__)


class Webhooks(Cog):
    def __init__(self, bot, config):
        self.bot = bot
        self.config = config
        self.server = None

    async def http_server(self):
        # Note: Authentication for webhooks is handled by nginx, not the bot
        app = web.Application()
        app.router.add_post('/github', self.github_handler)
        runner = web.AppRunner(app)
        await runner.setup()
        self.server = web.TCPSite(runner, 'localhost', self.config['port'])

        # Silence access logging to console/logfile
        logging.getLogger('aiohttp.access').setLevel(logging.WARNING)
        # wait for bot to be ready, then start and find the channels
        await self.bot.wait_until_ready()

        logger.info(f'Start listening on localhost:{self.config["port"]}')
        await self.server.start()

    async def github_handler(self, request):
        event = request.headers['X-GitHub-Event']
        body = await request.json()

        # Filter for steam workflow, then notify Steam Cog
        if event == 'workflow_run':
            if body['action'] == 'completed':
                run = body['workflow_run']
                if run['workflow_id'] == self.config['workflow_id']:
                    logger.info('GitHub workflow run completed, poking steamworks...')
                    if run['status'] == 'completed':
                        steam_cog = self.bot.get_cog('Steamworks')
                        self.bot.loop.create_task(steam_cog.build_update(run))
        else:
            logger.debug(f'Unhandled github event: {event}')

        return web.Response(text='OK')

    def cog_unload(self):
        if self.server:
            asyncio.create_task(self.server.stop())


def setup(bot):
    if bot.config.get('webhooks', {}).get('enabled', False):
        logger.info('Enabling Webhooks cog...')
        wh = Webhooks(bot, bot.config['webhooks'])
        bot.add_cog(wh)
        bot.loop.create_task(wh.http_server())
