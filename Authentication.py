# Authentication.py

import requests
import webbrowser
import secrets
from urllib.parse import urlparse, urlencode, urljoin
from flask import Flask, request, redirect


app = Flask(__name__)

# These are the Credientials. These are the only Manual Entries
client_id = "[Enter Client ID]"
client_secret = "[Enter Client Secret]]"
redirect_uri = "http://localhost:5000/callback" #Add this to redirect URIs @ https://developer.intuit.com/app/developer/dashboard
scope = "com.intuit.quickbooks.accounting"
token_endpoint = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"

# Automatically generate a random state
state = secrets.token_urlsafe(16)

# Authorization URL Parameters
authorization_params = {
    'client_id': client_id,
    'redirect_uri': redirect_uri,
    'scope': scope,
    'response_type': 'code',
    'state': state
}

# Authorization URL
authorization_url = "https://appcenter.intuit.com/connect/oauth2"

# Build Authorization Request URL
authorization_request_url = urljoin (authorization_url, '?' + urlencode(authorization_params))

# App URL
app_url = 'http://127.0.0.1:5000'

# Automatically open the web browser
webbrowser.open(app_url)

# Open Authorization Request URL
@app.route('/')
def login():
    # Redirect to the authorization URL
    return redirect(authorization_request_url)


# Callback route.
@app.route('/callback')
def callback():
    # Handle the callback after the user logs in
    auth_code = request.args.get('code')
    realm_id = request.args.get('realmId')

    # Exchange the authorization code for an access token
    token_params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'code': auth_code,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code',
    }

    response = requests.post(token_endpoint, data=token_params)

    if response.status_code == 200:
        # Successfully obtained access token
        access_token = response.json().get('access_token')
        refresh_token = response.json().get('refresh_token')
        # Print the values to the command line. Remove the # on the print code below to display returned keys in command line
        #print(f'Authorization Code: {auth_code}, Realm ID: {realm_id}, Access Token: {access_token}, Refresh Token: {refresh_token}')
        return 'Callback received. User is authenticated.'

    else:
        # Handle the error case
        print(f"Error: {response.text}")
        return f"Error: {response.text}"

if __name__ == '__main__':
    print('Starting the application...')
    app.run(debug=False)