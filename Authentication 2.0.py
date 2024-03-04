# Authentication 2.0.py

import requests
import webbrowser
import secrets
import json
from urllib.parse import urlencode, urljoin
from flask import Flask, request, redirect, session

app = Flask(__name__)
app.secret_key = '[Your_Own_Secret_Key]'  # This is just your own password to store your access tokens

# These are the Credentials. These are the only Manual Entries
client_id = "[Enter_Client_ID]"
client_secret = "[Enter_Client_Secret]"
redirect_uri = "http://localhost:5000/callback"
scope = "com.intuit.quickbooks.accounting"
token_endpoint = "https://oauth.platform.intuit.com/oauth2/v1/tokens/bearer"
base_url = "https://sandbox-quickbooks.api.intuit.com/v3/company/"
minorversion = 70

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
authorization_request_url = urljoin(authorization_url, '?' + urlencode(authorization_params))

# App URL
app_url = 'http://127.0.0.1:5000'

# Automatically open the web browser
webbrowser.open(app_url)


# Store tokens in a file
def store_tokens(access_token, refresh_token):
    with open('tokens.json', 'w') as f:
        tokens_data = {'access_token': access_token, 'refresh_token': refresh_token}
        json.dump(tokens_data, f)


# Retrieve stored tokens from a file
def get_stored_tokens():
    try:
        with open('tokens.json', 'r') as f:
            tokens_data = json.load(f)
            return tokens_data.get('access_token'), tokens_data.get('refresh_token')
    except FileNotFoundError:
        return None, None


# Update the stored access token in the file
def update_stored_access_token(new_access_token):
    access_token, refresh_token = get_stored_tokens()
    store_tokens(new_access_token, refresh_token)


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

    # Store realm_id in the session
    session['realm_id'] = realm_id

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

        # Print the values to the command line
        # print(f'Authorization Code: {auth_code}, Realm ID: {realm_id}, Access Token: {access_token}, Refresh Token: {refresh_token}')

        # Store tokens in a secure manner (e.g., a database)
        store_tokens(access_token, refresh_token)

        return redirect(f'{app_url}/refresh?realm_id={realm_id}')

    else:
        # Handle the error case
        print(f"Error: {response.text}")
        return f"Error: {response.text}"


# Token refresh route
@app.route('/refresh')
def refresh_token():
    # Retrieve Realm ID to Pass to API Call
    realm_id = request.args.get('realm_id')

    # Retrieve stored tokens (access token and refresh token) from a secure storage
    stored_access_token, stored_refresh_token = get_stored_tokens()

    # Request a new access token using the refresh token
    token_params = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': stored_refresh_token,
        'grant_type': 'refresh_token',
    }

    response = requests.post(token_endpoint, data=token_params)

    if response.status_code == 200:
        # Successfully obtained a new access token
        new_access_token = response.json().get('access_token')

        # Update the stored access token
        update_stored_access_token(new_access_token)

        return redirect(f'{app_url}/get_items?access_token={new_access_token}&realm_id={realm_id}')

    else:
        # Handle the error case
        print(f"Error refreshing token: {response.text}")
        return f"Error refreshing token: {response.text}"
