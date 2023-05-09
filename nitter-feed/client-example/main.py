import asyncio
import aiohttp
import logging

logging.basicConfig(level=logging.DEBUG)

async def main():

    SERVER = 'http://localhost:8080'

    async with aiohttp.ClientSession() as session:

        logging.info('configuring server')
        data = {
            'usernames': ['NYTimes','CNN','CNBC' ]
        }
        async with session.put(SERVER+'/feed/configure', json=data) as resp:
            logging.info(resp.status)
            logging.info(await resp.json())

        logging.info('opening websocket')

        async with session.ws_connect(SERVER+'/feed/ws') as ws:
            try:
                async for msg in ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = msg.json()
                        print(data)
                        print()
            except asyncio.exceptions.CancelledError:
                logging.info('interrupt received, closing websocket')
                await ws.close()
        

if __name__ == '__main__':
    asyncio.run(main())
