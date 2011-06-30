import os
import cgi
import math
import logging

from datetime import datetime
from datetime import timedelta

from django.utils import simplejson  as json

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app
from google.appengine.ext.webapp import template
from google.appengine.api import urlfetch
from google.appengine.api import memcache

def make_url_tuple(tuple):
    res = {}
    l = len(tuple)
    for j in xrange(l):
        entry = {}
        entry["place"] = j
        entry["page_views"] = tuple[j]["page_views"]
        res[tuple[j]["url"]] = entry
    return res
    
class Fetcher(webapp.RequestHandler):
    def __init__(self):
        super(Fetcher, self).__init__()
        self.token = None #00
        self.id = None
        self.url = None
        
    def fetch_data(self, period, results=100):
        fetch_url = self.url + self.id + '&oauth_token=' + self.token
        
        for _ in xrange(5):
            try:
                res = urlfetch.fetch(url=fetch_url + "&per_page=" + str(results) + "&date1=" + period[0].strftime('%Y%m%d') + "&date2=" + period[1].strftime('%Y%m%d'), deadline=10)
                if res.status_code == 200:
                    return res
            except urlfetch.DownloadError:
                logging.error("Download timeout")
                pass
            except:
                logging.error("Error while fetching data")
                pass
        
        counter_name = urlfetch.fetch(url='http://api-metrika.yandex.ru/counter/' + self.id + '.json&oauth_token=' + self.token, deadline=10)
        if counter_name.status_code == 200:
            path = os.path.join(os.path.dirname(__file__), 'missing_data.html')
            self.response.out.write(template.render(path, {'identity' : counter_name, 'data1': period[0].strftime('%Y-%m-%d'), 'data2': period[1].strftime('%Y%m%d')}))
        else:
            path = os.path.join(os.path.dirname(__file__), 'missing_data.html')
            self.response.out.write(template.render(path, {'identity' : self.id, 'data1': period[0].strftime('%Y-%m-%d'), 'data2': period[1].strftime('%Y%m%d')}))

        return None
        
class FetchDates(Fetcher):
    def format_date(self, date):
        return '%(d)s.%(m)s' % {'m': date[4:6], 'd': date[6:8]}
    def post(self):
        self.token = cgi.escape(self.request.get('token')) #11
        self.id = cgi.escape(self.request.get('counter'))
        self.url = 'http://api-metrika.yandex.ru/stat/traffic/summary.json?id='
        
        period = [datetime.strptime(cgi.escape(self.request.get('date_1')), "%Y-%m-%d"), datetime.strptime(cgi.escape(self.request.get('date_2')), "%Y-%m-%d")]
        rng = period[1] - period[0] + timedelta(1)
        
        res1 = self.fetch_data(period)
        if not res1:
            return
        data1 = map(lambda x: { "date": self.format_date(x["date"]), "visits": x["visits"] }, json.loads(res1.content)["data"])
        
        res2 = self.fetch_data(map(lambda x: x - rng, period))
        if not res2:
            return
        data2 = map(lambda x: { "visits": x["visits"] }, json.loads(res2.content)["data"])
        
        dates = []
        visits = []
        data2_length = len(data2)
        
        for i in xrange(len(data1)):
            entry = {}
            row = data1[i]
            entry["date"] = row["date"]
            entry["visits"] = row["visits"]
            visits.append(row["visits"])
            if data2_length - i > 0:
                entry["former_visits"] = data2[i]["visits"]
                visits.append(data2[i]["visits"])
            else:
                entry["former_visits"] = 0
            dates.append(entry)
            
        mean = sum(visits) / float(len(visits))
        
        self.response.out.write(json.dumps({"dates": dates, "mean": mean}))
        
        

        
class FetchPages(Fetcher):
    def post(self):
        self.token = cgi.escape(self.request.get('token')) #22
        self.id = cgi.escape(self.request.get('counter'))
        self.url = 'http://api-metrika.yandex.ru/stat/content/popular.json?id='
        
        period = [datetime.strptime(cgi.escape(self.request.get('date_1')), "%Y-%m-%d"), datetime.strptime(cgi.escape(self.request.get('date_2')), "%Y-%m-%d")]
        rng = period[1] - period[0] + timedelta(1)
        pages = []
        
        res1 = self.fetch_data(period, 20)
        if not res1:
            return 
        data1 = json.loads(res1.content)["data"]
        
        res2 = self.fetch_data(map(lambda x: x - rng, period))
        if not res2:
            return
        data2 = make_url_tuple(json.loads(res2.content)["data"])

        for i in xrange(len(data1)):
            entry = {}
            row = data1[i]
            entry["url"] = row["url"]
            entry["page_views"] = row["page_views"]
            entry["entrances"] = row['entrance'] 
            entry["exits"] = row['exit'] 
            if data2.has_key(row["url"]):
                e = data2[row["url"]]
                entry["former_page_views"] = e["page_views"]
                delta = e["place"] - i
                sign = ""
                if delta > 0:
                    sign = "+"
                elif delta == 0:
                    delta = "="
                entry["delta_place"] = sign + str(delta)
            else:
                entry["former_page_views"] = 0
                entry["delta_place"] = "-"
            pages.append(entry)
        
        self.response.out.write(json.dumps(pages))
        
class FetchCounters(webapp.RequestHandler):
    def post(self):
        token = cgi.escape(self.request.get('token'))
        counters = memcache.get(token)
        if counters is None:
            fetch_url = 'http://api-metrika.yandex.ru/counters.json?oauth_token=' + token
            result = urlfetch.fetch(url=fetch_url, deadline=3600)
            if result.status_code == 200:
                counters = json.loads(result.content)["counters"]
                memcache.add(token, counters, 3600) # TTL 3600 __seconds__
            else:
                counters = 'Oops, looks like you don\'t have permission to access counters'
        
        self.response.out.write(json.dumps(counters))
    
class IndexPage(webapp.RequestHandler):
    def get(self):
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, {}))
        
application = webapp.WSGIApplication(
                                    [('/', IndexPage),
                                     ('/pages', FetchPages),
                                     ('/dates', FetchDates),
                                     ('/counters', FetchCounters)],
                                    debug=True)
                                    
def main():
    run_wsgi_app(application)
    
if __name__ == "__main__":
    main()