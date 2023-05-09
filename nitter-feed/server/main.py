import argparse
import logging
import asyncio
from aiohttp import web, ClientSession, WSMsgType
from contextvars import ContextVar
from nitter_crawler_client import NitterCrawlerClient
from log import set_global_log_level
from conf import NITTER_POLL_INTERVAL

server_log = logging.getLogger('server')
cv_last_tweet_id = ContextVar('last_tweet_id', default=0)

async def handler_feed_configure(request: web.Request):
    """ set subs """

    data = await request.json()
    usernames = data['usernames']
    if isinstance(usernames,list):
        server_log.info('feed: configure: usernames=%s', usernames)
        request.app['feed_configuration']['usernames'] = usernames
        return web.json_response(dict(message='ok'),status=200)
    else:
        return web.json_response(dict(message='malformed username list'),status=400)


async def handler_feed_status(request: web.Request):
    """ return list of subs """
    pass


async def handler_feed_ws(request: web.Request):

    server_log.info('feed: opening websocket connection')

    ws = web.WebSocketResponse()
    await ws.prepare(request)

    nitter:NitterCrawlerClient = request.app['Nitter']

    async with ClientSession(raise_for_status=True) as session:

        poll_loop_running = True

        async def update_loop():

            while poll_loop_running:
                server_log.debug('feed: next poll iteration')

                usernames = request.app['feed_configuration']['usernames']

                # polls for top tweets from user feed
                run_result = await nitter.collect_user_top_tweets(usernames,session)

                # compare each tweet id with maximum id from last iteration to send only new tweets on this iteration
                if cv_last_tweet_id.get() != 0:
                    for entry in run_result:
                        if cv_last_tweet_id.get() < entry['id']:
                            await ws.send_json(entry)
                    for entry in run_result:
                        cv_last_tweet_id.set(max(cv_last_tweet_id.get(),entry['id']))
                else:
                    for entry in run_result:
                        cv_last_tweet_id.set(max(cv_last_tweet_id.get(),entry['id']))
                await asyncio.sleep(NITTER_POLL_INTERVAL)

        asyncio.ensure_future(update_loop())

        async for _ in ws:
            pass

        poll_loop_running = False


    server_log.info('feed: closed websocket connection')

    return ws

async def make_app():

    parser = argparse.ArgumentParser()
    parser.add_argument('--logging', type=str, default='info', help='Set minimum global logging level (debug|info|warning|error). Default: info')
    args = parser.parse_args()
    set_global_log_level(args.logging)


    app = web.Application()

    app['feed_configuration'] = dict(usernames=[])
    app['Nitter'] = NitterCrawlerClient()

    app.router.add_get('/feed/ws',handler_feed_ws)
    app.router.add_get('/feed/status',handler_feed_status)
    app.router.add_put('/feed/configure',handler_feed_configure)
    
    return app


if __name__ == '__main__':
    web.run_app(make_app())