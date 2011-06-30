import os
import json
import cgi
import math

from datetime import datetime
from datetime import timedelta

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
    
class FetchPage(webapp.RequestHandler):
    def __init__(self):
        super(FetchPage, self).__init__()
        
    def fetch_data(self, token, metrica_id, period, report_url, results=100):
        rng = period[1] - period[0] + timedelta(1)
        fetch_url = report_url + metrica_id + '&oauth_token=' + token
        
        for _ in xrange(5):
            res = urlfetch.fetch(url=fetch_url + "&per_page=" + str(results) + "&date1=" + period[0].strftime('%Y%m%d') + "&date2=" + period[1].strftime('%Y%m%d'), deadline=10)
            if res.status_code == 200:
                return res
        
        return False

class IndexPage(webapp.RequestHandler):
    def get(self):
        token = '38fd93c7c7b24d939bc4af23a87a7c02'
        counters = memcache.get(token)
        if counters is None:
            fetch_url = 'http://api-metrika.yandex.ru/counters.json?oauth_token=' + token
            result = urlfetch.fetch(url=fetch_url, deadline=3600)
            if result.status_code == 200:
                counters = json.loads(result.content)["counters"]
                memcache.add(token, counters, 3600) # TTL 3600 __seconds__
            else:
                counters = 'Oops, lookl like you don\'t have permission to access counters'
        path = os.path.join(os.path.dirname(__file__), 'index.html')
        self.response.out.write(template.render(path, {'counters' : counters,}))
        
class FetchDates(FetchPage):
    def format_date(self, date):
        return '%(d)s.%(m)s' % {'m': date[4:6], 'd': date[6:8]}
    def post(self):
        token = '38fd93c7c7b24d939bc4af23a87a7c02'
        metrica_id = cgi.escape(self.request.get('counter'))
        period = [datetime.strptime(cgi.escape(self.request.get('date_1')), "%Y-%m-%d"), datetime.strptime(cgi.escape(self.request.get('date_2')), "%Y-%m-%d")]
        rng = period[1] - period[0] + timedelta(1)
        
        fetch_url = 'http://api-metrika.yandex.ru/stat/traffic/summary.json?id=' + metrica_id + '&oauth_token=' + token
        
        #res1 = urlfetch.fetch(url=fetch_url + "&per_page=100&date1=" + period[0].strftime('%Y%m%d') + "&date2=" + period[1].strftime('%Y%m%d'), deadline=10)
        res1 = self.fetch_data(token, metrica_id, period, 'http://api-metrika.yandex.ru/stat/traffic/summary.json?id=')
        data1 = map(lambda x: { "date": self.format_date(x["date"]), "visits": x["visits"] }, json.loads(res1.content)["data"])
        
        res2 = urlfetch.fetch(url=fetch_url + "&per_page=100&date1=" + (period[0] - rng).strftime('%Y%m%d') + "&date2=" + (period[1] - rng).strftime('%Y%m%d'), deadline=10)
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
                0
            dates.append(entry)
            
        mean = sum(visits) / float(len(visits))
        st_deviation = math.sqrt(sum(map(lambda x: (x - mean)**2, visits)) / float(len(visits)))
        
        self.response.out.write(json.dumps({"dates": dates, "standard_deviation": st_deviation, "mean": mean}))
        
        

        
class FetchPages(webapp.RequestHandler):
    def post(self):
        token = '38fd93c7c7b24d939bc4af23a87a7c02'
        metrika_id = cgi.escape(self.request.get('counter'))
        period = [datetime.strptime(cgi.escape(self.request.get('date_1')), "%Y-%m-%d"), datetime.strptime(cgi.escape(self.request.get('date_2')), "%Y-%m-%d")]
        rng = period[1] - period[0] + timedelta(1)
        
        fetch_url = 'http://api-metrika.yandex.ru/stat/content/popular.json?id=' + metrika_id + '&oauth_token=' + token
        
        pages = []
        
        res1 = urlfetch.fetch(url=fetch_url + "&per_page=20&date1=" + period[0].strftime('%Y%m%d') + "&date2=" + period[1].strftime('%Y%m%d'), deadline=10)
        data1 = json.loads(res1.content)["data"]
        res2 = urlfetch.fetch(url=fetch_url + "&per_page=100&date1=" + (period[0] - rng).strftime('%Y%m%d') + "&date2=" + (period[1] - rng).strftime('%Y%m%d'), deadline=10)
        data2 = make_url_tuple(json.loads(res2.content)["data"])

        
        for i in xrange(len(data1)):
            entry = {}
            row = data1[i]
            entry["url"] = row["url"]
            entry["page_views"] = row["page_views"]
            entry["former_page_views"] = data2[row["url"]]
            entry["entrances"] = int(row["entrance_percent"] * row["page_views"])
            entry["exits"] = int(row["exit_percent"] * row["page_views"])
            if data2.has_key(row["url"]):
                e = data2[row["url"]]
                entry["former_page_views"] = e["page_views"]
                delta = e["place"] - i
                sign = ""
                if delta > 0:
                    sign = "+"
                elif delta == 0:
                    delta = "="
                    sign = ""
                entry["delta_place"] = sign + str(delta)
            else:
                entry["former_page_views"] = 0
                entry["delta_place"] = "-"
            pages.append(entry)
        
        self.response.out.write(json.dumps(pages))
        
application = webapp.WSGIApplication(
                                    [('/', IndexPage),
                                     ('/pages', FetchPages),
                                     ('/dates', FetchDates)],
                                    debug=True)
                                    
def main():
    run_wsgi_app(application)
    
if __name__ == "__main__":
    main()