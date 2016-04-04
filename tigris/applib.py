import os
import re
import jinja2
import webapp2
import logging


from google.appengine.api import users
from google.appengine.api import urlfetch
from google.appengine.ext import ndb
from google.appengine.ext.ndb import metadata

from webapp2_extras import auth
from webapp2_extras import sessions

from webapp2_extras.auth import InvalidAuthIdError, InvalidPasswordError

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)


class CodeBase(ndb.Model):
    fid = ndb.IntegerProperty()
    filename = ndb.StringProperty()
    author = ndb.StringProperty()
    public = ndb.BooleanProperty()
    protected = ndb.BooleanProperty()
    modules = ndb.StringProperty(repeated=True, indexed=False)
    date = ndb.DateTimeProperty(auto_now_add=True)

    script = ndb.StringProperty(indexed=False)
    docstr = ndb.StringProperty(indexed=False)

    deleted = ndb.BooleanProperty()


def user_required(handler):
    """
      Decorator that checks if there's a user associated with the current session.
      Will also fail if there's no session present.
    """

    def check_login(self, *args, **kwargs):
        auth = self.auth
        if not auth.get_user_by_session():
            self.redirect(self.uri_for('login'), abort=True)
        else:
            return handler(self, *args, **kwargs)

    return check_login


class BaseHandler(webapp2.RequestHandler):

    PROJECTED_FIELD_A = ['fid', 'filename',
                         'author', 'public', 'protected', 'date']
    PROJECTED_FIELD_B = ['fid', 'filename', 'author', 'protected', 'date']

    @webapp2.cached_property
    def auth(self):
        """Shortcut to access the auth instance as a property."""
        return auth.get_auth()

    @webapp2.cached_property
    def user_info(self):
        """Shortcut to access a subset of the user attributes that are stored
        in the session.

        The list of attributes to store in the session is specified in
          config['webapp2_extras.auth']['user_attributes'].
        :returns
          A dictionary with most user information
        """
        return self.auth.get_user_by_session()

    @webapp2.cached_property
    def user(self):
        """Shortcut to access the current logged in user.

        Unlike user_info, it fetches information from the persistence layer and
        returns an instance of the underlying model.

        :returns
          The instance of the user model associated to the logged in user.
        """
        u = self.user_info
        return self.user_model.get_by_id(u['user_id']) if u else None

    @webapp2.cached_property
    def user_model(self):
        """Returns the implementation of the user model.

        It is consistent with config['webapp2_extras.auth']['user_model'], if set.
        """
        return self.auth.store.user_model

    @webapp2.cached_property
    def session(self):
        """Shortcut to access the current session."""
        return self.session_store.get_session(backend="datastore")

    def render_template(self, view_filename, params=None):
        if not params:
            params = {}
        user = self.user
        params['user'] = user
        template = JINJA_ENVIRONMENT.get_template(view_filename)
        self.response.write(template.render(params))

    # this is needed for webapp2 sessions to work
    def dispatch(self):
            # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    def _strip(self, item):
        item.script = ""
        return item

    def _query_list(self, maxium=20, query_public=False):
        if query_public:
            query = CodeBase.query(
                CodeBase.public == True).order(-CodeBase.date)
            return query.fetch(maxium, projection=self.PROJECTED_FIELD_B)
        else:
            query = CodeBase.query(ancestor=ndb.Key(
                'CodeBase', self.user.name)).order(-CodeBase.date)
            return query.fetch(maxium, projection=self.PROJECTED_FIELD_A)

    def _query_by_names(self, names):
        if len(names):
            query = CodeBase.query()
            query = query.filter(CodeBase.filename.IN(names))
            return query.fetch()
        else:
            return []

    def _query_item(self, fid):
        query = CodeBase.query()
        query = query.filter(CodeBase.fid == fid)
        res = query.fetch(1)
        if res:
            if res[0].protected and res[0].author != self.user.name:
                res[0].script = ""
            return res[0]
        else:
            return None

    def _parse(self, script):
        modules = re.findall("from\s+(.*?)\s+import", script)
        dep = [m.split('.')[1] for m in modules if m.split('.')[0] == 'tigris']
        res = re.search('\"{3}.*?@usage.*?\"{3}', script, re.DOTALL)
        docstr = res.group(0) if res else "\n\n\n\nNo doc string Written"
        return dep, docstr

    def _create(self, d):
        k = ndb.Key('CodeBase', d["author"])
        code = CodeBase(parent=k)
        return self._save(code, d)

    def _save(self, item, d):
        d["fid"] = int(d["fid"])
        item.populate(**d)
        item.modules, item.docstr = self._parse(item.script)
        item.deleted = False
        item.put()
        return item


class LoginHandler(BaseHandler):

    def get(self):
        self._serve_page()

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        try:
            u = self.auth.get_user_by_password(username, password, remember=True,
                                               save_session=True)
            self.redirect(self.uri_for('code'))
        except (InvalidAuthIdError, InvalidPasswordError) as e:
            logging.info('Login failed for user %s because of %s',
                         username, type(e))
            self._serve_page(True)

    def _serve_page(self, failed=False):
        username = self.request.get('username')
        params = {
            'username': username,
            'failed': failed
        }
        self.render_template('login.html', params)


class LogoutHandler(BaseHandler):

    def get(self):
        self.auth.unset_session()
        self.redirect(self.uri_for('login'))


class SignupHandler(BaseHandler):

    def get(self):
        self.render_template('signup.html')

    def post(self):
        user_name = self.request.get('username')
        email = self.request.get('email')
        name = self.request.get('username')
        password = self.request.get('password')
        last_name = self.request.get('lastname')

        unique_properties = ['email_address']
        user_data = self.user_model.create_user(user_name,
                                                unique_properties,
                                                email_address=email, name=name, password_raw=password,
                                                last_name=last_name, verified=False)
        if not user_data[0]:  # user_data is a tuple
            params = {}
            params['error'] = 'Unable to create user for email %s because of \
        duplicate keys %s' % (user_name, user_data[1])
            self.render_template('signup.html', params)

            return

        self.redirect(self.uri_for('code'), abort=True)


class VerificationHandler(BaseHandler):

    def get(self, *args, **kwargs):
        user = None
        user_id = kwargs['user_id']
        signup_token = kwargs['signup_token']
        verification_type = kwargs['type']

        # it should be something more concise like
        # self.auth.get_user_by_token(user_id, signup_token)
        # unfortunately the auth interface does not (yet) allow to manipulate
        # signup tokens concisely
        user, ts = self.user_model.get_by_auth_token(int(user_id), signup_token,
                                                     'signup')

        if not user:
            logging.info('Could not find any user with id "%s" signup token "%s"',
                         user_id, signup_token)
            self.abort(404)

        # store user data in the session
        self.auth.set_session(
            self.auth.store.user_to_dict(user), remember=True)

        if verification_type == 'v':
            # remove signup token, we don't want users to come back with an old
            # link
            self.user_model.delete_signup_token(user.get_id(), signup_token)

            if not user.verified:
                user.verified = True
                user.put()

            self.display_message('User email address has been verified.')
            return
        elif verification_type == 'p':
            # supply user to the page
            params = {
                'user': user,
                'token': signup_token
            }
            self.render_template('resetpassword.html', params)
        else:
            logging.info('verification type not supported')
            self.abort(404)
