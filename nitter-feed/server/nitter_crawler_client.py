import logging
import re
import functools
import operator
import aiohttp
import asyncio
import arrow
import random
from bs4 import BeautifulSoup

from conf import NITTER_INSTANCE_LIST_UPDATE_INTERVAL

mylog = logging.getLogger('nittercrawler')

def log_aiohttp_response(response):
    mylog.debug(f'{response.request_info.method} {response.url} {response.status} {response.reason}')

class NitterCrawlerClient:

    async def _fetch_live_nitter_instances_list(self, session: aiohttp.ClientSession) -> list[str]:
        mylog.info('updating list of nitter instances')

        async with session.get('https://raw.githubusercontent.com/xnaas/nitter-instances/master/history/summary.json') as response:
            data = await response.json(content_type='text/plain')
            log_aiohttp_response(response)

            return [ entry['name'] for entry in data if entry['status'] == 'up']


    async def _fetch_user_timeline_by_explicit_instance(self, user: str, instance:str, max_items: int, session: aiohttp.ClientSession) -> list[dict]:
        items = []

        processed_count = 0
        async with session.get(f'https://{instance}/{user}') as response:
            page_content = await response.text()
            log_aiohttp_response(response)
            mylog.debug('user (%s) retrieving page', user)

            soup = BeautifulSoup(page_content, 'html.parser')
            node_timeline = soup.find('div', class_='timeline')
            mylog.debug('user (%s) node_timeline', user)
            node_timeline_items = node_timeline.find_all('div', class_='timeline-item')
            for item in node_timeline_items:

                if processed_count >= max_items:
                    break

                # ignore pinned tweets
                if item.find('div',class_='pinned'):
                    continue
                if 'unavailable' in item['class']:
                    continue

                relative_twitter_link = item.find('a',class_='tweet-link')['href']
                url = 'https://twitter.com' + relative_twitter_link
                mylog.debug('user (%s)   timeline item:   url=%s', user,url)

                m = re.search('status/([0-9]+).*', relative_twitter_link)
                tweet_id = int(m.group(1)) if m else None
                mylog.debug('user (%s)   timeline item:   tweet_id=%d', user,tweet_id)

                fullname =  item.find('a',class_='fullname')['title']
                mylog.debug('user (%s)   timeline item:   fullname=%s', user,fullname)

                username =  item.find('a',class_='username')['title']
                mylog.debug('user (%s)   timeline item:   username=%s', user,username)

                timestamp = item.find('span',class_='tweet-date').a['title']
                timestamp = arrow.get( timestamp, 'MMM D, YYYY · h:mm A ZZZ')
                mylog.debug('user (%s)   timeline item:   timestamp=%s', user,str(timestamp))
                
                text = item.find('div',class_='tweet-content').decode_contents()
                text = text.replace('href="/','href="https://twitter.com/')
                mylog.debug('user (%s)   timeline item:   text=%s', user,text)

                d={
                    'id': tweet_id,
                    'timestamp': timestamp.isoformat(),
                    'url': url,
                    'fullname': fullname,
                    'username': username,
                    'text': text,
                    }
                items.append(d)
                processed_count += 1

            return items


    async def _fetch_user_timeline(self, user: str, max_items: int, session: aiohttp.ClientSession) -> list[dict]:
        items = []
        instance = random.choice(self._instance_list)
        mylog.info('fetching timeline [%s] using Nitter instance %s', user, instance)
        
        ts_fetch_start = asyncio.get_event_loop().time()

        try:
            items = await asyncio.wait_for(self._fetch_user_timeline_by_explicit_instance(user=user,  instance=instance, max_items=max_items, session=session), 10)
        except Exception as e:
            
            if isinstance(e, asyncio.exceptions.TimeoutError):
                mylog.info('instance %s seems too slow to respond and is temporarily ignored', instance)
            else:
                mylog.info('instance %s is causing problems and is temporarily ignored  (error: %s)', instance, str(e))

            # remove the instance from the instance list (can still be re-added next time list is updated)
            self._instance_list = [x for x in self._instance_list if x != instance]

        mylog.info('completed timeline %20s %30s   %.1f seconds', user, instance, (asyncio.get_event_loop().time() - ts_fetch_start))

        return items


    async def _filter_bad_and_slow_instances(self, instances: list[str], session: aiohttp.ClientSession) -> list[str]:

        mylog.info('testing for non working or slow nitter instances')

        async def fetch_benchmarking_wrapper(**kwargs) -> str:
            await asyncio.wait_for(self._fetch_user_timeline_by_explicit_instance(**kwargs),10)
            return kwargs['instance']
        
        tasks = [asyncio.create_task(fetch_benchmarking_wrapper(user='elonmusk',instance=inst,max_items=1,session=session))  for inst in instances]

        tasks_results = await asyncio.gather(*tasks,return_exceptions=True)

        #print(tasks_results)

        ok_instances = [result for result in tasks_results if not isinstance(result, Exception)]

        failed_instances = [inst for inst in instances if inst not in ok_instances]

        mylog.info('blacklisted following instances:')
        mylog.info(' '.join(failed_instances))

        return ok_instances
        



    def __init__(self):
        self._instance_list = []
        self._instance_list_timestamp = 0


    async def collect_user_top_tweets(self, usernames:list[str], session: aiohttp.ClientSession) -> list[dict]:
        """ polls for top tweets from each user feed """

        async def update_instance_list():
            instance_list = await self._fetch_live_nitter_instances_list(session)
            instance_list = await self._filter_bad_and_slow_instances(instance_list, session)
            self._instance_list = instance_list
            self._instance_list_timestamp = asyncio.get_event_loop().time()

        if len(self._instance_list) == 0 or ( asyncio.get_event_loop().time() > self._instance_list_timestamp + NITTER_INSTANCE_LIST_UPDATE_INTERVAL):
            await update_instance_list()

        if len(self._instance_list):
            tasks = [asyncio.create_task(self._fetch_user_timeline(username,1,session))  for username in usernames]
            tasks_results = await asyncio.gather(*tasks,return_exceptions=False)
            combined_result = functools.reduce(operator.add, tasks_results)
            return combined_result
        else:
            return []



