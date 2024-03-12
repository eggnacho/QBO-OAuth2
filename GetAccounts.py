# GetAccounts.py

import requests
import webbrowser
import secrets
import json
import csv
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

        return redirect(f'{app_url}/get_accounts?access_token={new_access_token}&realm_id={realm_id}')

    else:
        # Handle the error case
        print(f"Error refreshing token: {response.text}")
        return f"Error refreshing token: {response.text}"


##############################################################################################
# Start API Calls Here

# New Flask route for performing the API request
@app.route('/get_accounts')
def get_accounts():
    # Get realm_id and access_token from the query parameters or session
    realm_id = request.args.get('realm_id')
    access_token = request.args.get('access_token')

    if not realm_id or not access_token:
        return 'Realm ID or Access Token not provided in the request parameters.', 400

    # Call the API function with the obtained tokens
    api_response = make_api_request(realm_id, access_token)

    if api_response and 'error' in api_response:
        return f"Error in API call: {api_response['error']['code']}, {api_response['error']['message']}", 500
    else:
        return 'API request completed.'


# Function to make the API call
def make_api_request(realm_id, access_token):
    try:
        # Set the headers for the request
        query = "select * from Account"

        # Construct the complete URL for the API call
        api_url = f"{base_url}{realm_id}/query?query={query}&minorversion={minorversion}"

        # Set the headers for the request
        api_headers = {
            'Accept': 'application/json',  # Specify that you want JSON responses
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {access_token}'
        }

        # Make the GET request
        response = requests.get(api_url, headers=api_headers)
        response.raise_for_status()  # Raise an HTTPError for bad responses (4xx and 5xx)

        # Check if the response content is empty
        if not response.content:
            return {'error': {'code': 500, 'message': 'Empty response content'}}

        try:
            # Attempt to parse the response as JSON
            data = response.json()
            print("API Response:", data)

            # Check if the 'QueryResponse' key is present in the JSON data
            if 'QueryResponse' in data:
                accounts = data['QueryResponse'].get('Account', [])

                if accounts:
                    # Specify the CSV file path
                    csv_file_path = 'accounts_data.csv'

                    # Specify the order of columns
                    columns = [
                        'Name', 'SubAccount', 'FullyQualifiedName', 'AccountType', 'AccountSubType', 'Id',
                        'Classification'
                    ]

                    # Write the data to the CSV file
                    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csv_file:
                        csv_writer = csv.writer(csv_file)

                        # Write the header row
                        csv_writer.writerow(columns)

                        # Write each account as a row in the CSV file
                        for account in accounts:

                            # Write the values in the specified order
                            row_values = [
                                account.get('Name', ''), account.get('SubAccount', ''),
                                account.get('FullyQualifiedName', ''), account.get('AccountType', ''),
                                account.get('AccountSubType', ''), account.get('Id', ''),
                                account.get('Classification', ''),
                            ]
                            csv_writer.writerow(row_values)

                    print(f"Data exported to CSV file: {csv_file_path}")
                else:
                    print("No accounts data in the response.")
            else:
                print("Unexpected JSON format in the response.")

            return data
        except json.JSONDecodeError as json_err:
            print(f"Error decoding JSON response: {json_err}")
            print("Response Content:", response.content.decode('utf-8'))
            return {'error': {'code': 500, 'message': 'Error decoding JSON response'}}

    except requests.exceptions.HTTPError as http_err:
        return {'error': {'code': response.status_code, 'message': str(http_err)}}
    except Exception as err:
        return {'error': {'code': 500, 'message': str(err)}}




if __name__ == '__main__':
    print('Starting the application...')
    print(f'Open this URL in your web browser: {app_url}')
    app.run(debug=False)
