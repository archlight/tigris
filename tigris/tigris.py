import os
import urllib
import webapp2
import logging
import json
import re
import time

from webapp2 import Route
from applib import *


    

class MainPage(BaseHandler):

    def get(self):
        self.render_template('landing.html')

class CodeCompute(BaseHandler):
    url = "https://tigris-1242.appspot.com/zipline"
    #url = "http://localhost:8089/zipline"

    @user_required
    def post(self):
        d = json.loads(self.request.body)

        modules, _ = self._parse(d["code"])
        script = re.sub("from\s+tigris.*?\\n", "", d["code"])

        code = "\n\n".join([m.script for m in self._query_by_names(modules)])
        code = code + "\n\n" + script

        #logging.info(code)
        d["code"] = code
        
        # result = urlfetch.fetch(self.url, 
        #                         payload=json.dumps(d), 
        #                         method=urlfetch.POST, 
        #                         headers = {"Content-Type":"application/json"})
        # if result.status_code == 200:
        #     self.response.headers['Content-Type'] = 'application/json'
        #     self.response.out.write(result.content)
        # else:
        #     self.response.out.write(result.content)

        rpc = urlfetch.create_rpc()
        urlfetch.make_fetch_call(rpc, self.url, 
            payload=json.dumps(d), 
            method=urlfetch.POST, 
            headers={"Content-Type":"application/json"},
            follow_redirects=False)

        try:
            result = rpc.get_result()
            if result.status_code == 200:
                self.response.headers['Content-Type'] = 'application/json'
                self.response.out.write(result.content)
            else:
                self.response.out.write(result.content)
        except urlfetch.DownloadError:
            self.response.out.write(urlfetch.DownloadError.message())

class CodeSpace(BaseHandler):


    def _params(self, maxium):
        params = {}
        params['modules'] = [t for t in self._query_list(maxium, True) if t.author != self.user.name]
        params['codelist'] = self._query_list(maxium)
        fid = self.request.get("id", 0)

        item = self._query_item(int(fid))
        params['item'] = item if item else CodeBase()

        return params

    @user_required
    def get(self):
        maxium = self.request.get('max', 20)
        self.render_template('code.html', self._params(maxium))

    @user_required
    def post(self):
        d = json.loads(self.request.body)
        d["author"] = self.user.name
        fid = hash('.'.join([d["author"], d["filename"]]))

        if d["filename"]:
            self.response.headers['Content-Type'] = 'application/json'

            item = self._query_item(fid)
            clone = False

            if item:
                if str(item.fid) == d["fid"]:
                    if item.author == d["author"]:
                        m = self._save(item, d)
                        self.response.out.write(json.dumps({"info":m.modules, "fid":str(m.fid)}))
                    else:
                        clone = True
                else:
                    self.response.out.write(json.dumps({"error":"name exists"}))
            
            if not item or clone:
                d["fid"] = str(fid)
                code = self._create(d)
                d = code.to_dict()
                d["date"] = d["date"].strftime("%Y-%m-%d")
                d["fid"] = str(d["fid"])
                self.response.out.write(json.dumps(d))
                


config = {
  'webapp2_extras.auth': {
    'user_model': 'models.User',
    'user_attributes': ['name']
  },
  'webapp2_extras.sessions': {
    'secret_key': 'VpY4neuMXF'
  }
}

app = webapp2.WSGIApplication([
    webapp2.Route('/', MainPage, name='home'),
    webapp2.Route('/code', CodeSpace, name='code'),
    webapp2.Route('/compute', CodeCompute, name='compute'),
    webapp2.Route('/login', LoginHandler, name='login'),
    webapp2.Route('/signup', SignupHandler, name='signup'),
    webapp2.Route('/logout', LogoutHandler, name='logout'),
    webapp2.Route('/<type:v|p>/<user_id:\d+>-<signup_token:.+>',
      handler=VerificationHandler, name='verification')
], debug=False, config=config)
