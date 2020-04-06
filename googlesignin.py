from oauth2client.client import flow_from_clientsecrets
from oauth2client.client import FlowExchangeError
import httplib2
import json
import requests

class GoogleSignin(object):
    
    def __init__(self, 
                    auth_code,
                    state,
                    client_id,
                    client_secrets_filename,
                    redirect_uri,
                    tokeninfo_url,
                    userinfo_url,
                    disconnect_url):
        self.auth_code = auth_code
        self.state = state
        self.client_id = client_id
        self.client_secrets_filename = client_secrets_filename
        self.redirect_uri = redirect_uri
        self.tokeninfo_url = tokeninfo_url
        self.userinfo_url = userinfo_url
        self.disconnect_url = disconnect_url    

    def signin(self, state):
        self.verifyStateToken(state)
        self.getCredentials()
        token = self.getValidatedToken()
        self.validateTokenUser(token)
        self.validateTokenApp(token)
        userInfo = self.getUserInfo()
        return { 
                 "access_token": self.credentials.access_token,
                 "source_id": self.gplus_id,
                 "username": userInfo['name'],
                 "picture": userInfo['picture'],
                 "email": userInfo['email']
                }

    def signout(self, access_token):
        url = (self.disconnect_url + '?token=%s') % access_token
        h = httplib2.Http()
        result = h.request(url, 'GET')[0]
        if result['status'] != '200':
            raise GoogleSigninError('Signout error. Failed to revoke token for the user.')

    def verifyStateToken(self, state):
        if state != self.state:
            raise GoogleSigninError('Invalid state parameter.')

    def getCredentials(self):
        try:
            # Upgrade the authorization code into a credentials object
            oauth_flow = flow_from_clientsecrets(self.client_secrets_filename, scope='')
            oauth_flow.redirect_uri = self.redirect_uri
            self.credentials = oauth_flow.step2_exchange(self.auth_code)
        except FlowExchangeError as error:
            raise GoogleSigninError('Cannot exchange credentials: %s', error)

    def getValidatedToken(self):
        access_token = self.credentials.access_token
        url = (self.tokeninfo_url + '?access_token=%s' % access_token)
        h = httplib2.Http()
        result = json.loads(h.request(url, 'GET')[1])
        # If there was an error in the access token info, abort.
        if result.get('error') is not None:
            raise GoogleSigninError('Invalid token: %s', result.get('error'))
        return result
    
    def validateTokenUser(self, token):
        self.gplus_id = self.credentials.id_token['sub']
        if token['user_id'] != self.gplus_id:
            raise GoogleSigninError("Token's user ID doesn't match given user ID.")

    def validateTokenApp(self, token):
        if token['issued_to'] != self.client_id:
            raise GoogleSigninError("Token's client ID does not match app's.")

    def getUserInfo(self):
        params = {'access_token': self.credentials.access_token, 'alt': 'json'}
        answer = requests.get(self.userinfo_url, params=params)
        return answer.json()

class GoogleSigninError(Exception):
    pass