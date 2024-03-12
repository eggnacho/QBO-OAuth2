# UpdateItems.py

import requests
import webbrowser
import secrets
import json
import csv
import time
from datetime import datetime, timezone, timedelta
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

        return redirect(f'{app_url}/get_and_update_items?access_token={new_access_token}&realm_id={realm_id}')

    else:
        # Handle the error case
        print(f"Error refreshing token: {response.text}")
        return f"Error refreshing token: {response.text}"


##############################################################################################
# Get Items Starts Here

# New Flask route for performing the API request
@app.route('/get_items')
def get_items():
    # Get realm_id and access_token from the query parameters or session
    realm_id = request.args.get('realm_id')
    access_token = request.args.get('access_token')

    if not realm_id or not access_token:
        return 'Realm ID or Access Token not provided in the request parameters.', 400

    # Call the API function with the obtained tokens
    api_response = make_items_api_request(realm_id, access_token)

    if api_response and 'error' in api_response:
        return f"Error in API call: {api_response['error']['code']}, {api_response['error']['message']}", 500

    else:
        # Display the API response data
        return f'''
                   <h1>Get Items API Response</h1>
                   <br />
                   <a href="{urljoin(app_url, '/download_items')}?realm_id={realm_id}">Download Items Data</a>
                   <br />
                   <pre>{json.dumps(api_response, indent=2)}</pre>


               '''


# Function to make the Get Items API call
def make_items_api_request(realm_id, access_token):
    try:
        # Set the headers for the request
        query = "select * from Item"

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
                items = data['QueryResponse'].get('Item', [])

                if items:
                    # Specify the CSV file path
                    csv_file_path = f'{realm_id}_items_data.csv'

                    # Specify the order of columns
                    columns = [
                        'FullyQualifiedName', 'domain', 'Id', 'Name', 'TrackQtyOnHand', 'Type',
                        'PurchaseCost', 'QtyOnHand', 'IncomeAccountRef_name', 'IncomeAccountRef_value',
                        'AssetAccountRef_name', 'AssetAccountRef_value', 'Taxable',
                        'MetaData_CreateTime', 'MetaData_LastUpdatedTime', 'sparse', 'Active',
                        'SyncToken', 'InvStartDate', 'UnitPrice', 'ExpenseAccountRef_name',
                        'ExpenseAccountRef_value', 'PurchaseDesc', 'Description',
                    ]

                    # Write the data to the CSV file
                    with open(csv_file_path, 'w', newline='', encoding='utf-8') as csv_file:
                        csv_writer = csv.writer(csv_file)

                        # Write the header row
                        csv_writer.writerow(columns)

                        # Write each item as a row in the CSV file
                        for item in items:
                            # Get the Id and SyncToken from the item
                            item_id = str(item.get('Id', ''))
                            sync_token = int(item.get('SyncToken', 0))

                            # Update the last_sync_tokens dictionary
                            last_sync_tokens[item_id] = sync_token

                            # Handle the case where 'Description' is missing
                            item['Description'] = item.get('Description', '')

                            # Handle nested fields
                            asset_account_ref = item.get('AssetAccountRef', {})
                            income_account_ref = item.get('IncomeAccountRef', {})
                            expense_account_ref = item.get('ExpenseAccountRef', {})

                            # Write the values in the specified order
                            row_values = [
                                str(item.get('FullyQualifiedName', '')),
                                str(item.get('domain', '')),
                                str(item.get('Id', '')),
                                str(item.get('Name', '')),
                                str(item.get('TrackQtyOnHand', '')),
                                str(item.get('Type', '')),
                                str(item.get('PurchaseCost', '')),
                                str(item.get('QtyOnHand', '')),
                                str(income_account_ref.get('name', '')),
                                str(income_account_ref.get('value', '')),
                                str(asset_account_ref.get('name', '')),
                                str(asset_account_ref.get('value', '')),
                                str(item.get('Taxable', '')),
                                str(item.get('MetaData', {}).get('CreateTime', '')),
                                str(item.get('Active', '')),
                                str(item.get('InvStartDate', '')),
                                str(item.get('UnitPrice', '')),
                                str(expense_account_ref.get('name', '')),
                                str(expense_account_ref.get('value', '')),
                                str(item.get('PurchaseDesc', '')),
                                str(item.get('Description', '')),
                            ]
                            csv_writer.writerow(row_values)

                    # Save the last_sync_tokens to the file after processing
                    with open(last_sync_tokens_file, 'w') as file:
                        json.dump(last_sync_tokens, file)

                    print(f"Data exported to CSV file: {csv_file_path}")

                else:
                    print("No items data in the response.")
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


@app.route('/download_items')
def download_items():
    # Get realm_id from the query parameters or session
    realm_id = request.args.get('realm_id')

    if not realm_id:
        return 'Realm ID not provided in the request parameters.', 400

    # Specify the CSV file path based on realm_id
    csv_file_path = f'{realm_id}_items_data.csv'

    # Download the file
    return send_file(csv_file_path, as_attachment=True)


# Get Items ends here

###############################################################################################
# Update Items

# Assuming you have a CSV file named 'items.csv' with headers matching the JSON response
csv_file_path = 'items.csv'

# Initialize a dictionary to store the last used SyncToken for each item
last_sync_tokens = {}

# Path to the file where the last_sync_tokens will be saved
last_sync_tokens_file = 'last_sync_tokens.json'

# Load last_sync_tokens from the file if it exists
try:
    with open(last_sync_tokens_file, 'r') as file:
        last_sync_tokens = json.load(file)
except FileNotFoundError:
    pass

# Function to read item data from CSV
def read_item_data_from_csv(csv_file):
    with open(csv_file, newline='', encoding='utf-8') as csvfile:
        reader = csv.DictReader(csvfile)
        return list(reader)


# Function to update an item
@app.route('/update_items')
def update_item():
    # Retrieve parameters from the request
    access_token = request.args.get('access_token')
    realm_id = request.args.get('realm_id')

    headers = {
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'text/plain',
        'Accept': 'application/json',
        'Content-Type': 'application/json',

    }

    # Read item data from CSV
    item_data_from_csv = read_item_data_from_csv(csv_file_path)

    for csv_item in item_data_from_csv:
        item_id_to_update = csv_item['Id']

        # Get the last used SyncToken for the item, default to 0 if not found
        last_sync_token = last_sync_tokens.get(item_id_to_update, 0)

        # Increment the SyncToken for the item
        new_sync_token = last_sync_token

        # Update the last used SyncToken for the item
        last_sync_tokens[item_id_to_update] = new_sync_token

        # Replace the original line with the following code
        current_datetime = datetime.now(timezone(timedelta(hours=-8)))  # Adjust the timezone offset as needed
        formatted_last_updated_time = current_datetime.strftime("%Y-%m-%dT%H:%M:%S%z")

        # Manually insert the colon in the timezone offset
        formatted_last_updated_time = f"{formatted_last_updated_time[:-2]}:{formatted_last_updated_time[-2:]}"

        # Include SyncToken from CSV in the json_response
        # True/False values must be all lower case
        json_response = {
            "FullyQualifiedName": csv_item['FullyQualifiedName'],
            "domain": csv_item['domain'],
            "Id": csv_item['Id'],
            "Name": csv_item['Name'],
            "TrackQtyOnHand": csv_item['TrackQtyOnHand'],
            "Type": csv_item['Type'],
            "PurchaseCost": csv_item['PurchaseCost'],
            "QtyOnHand": csv_item['QtyOnHand'],
            "IncomeAccountRef": {
                "value": csv_item['IncomeAccountRef_value']
            },
            "AssetAccountRef": {
                "value": csv_item['AssetAccountRef_value']
            },
            "Taxable": csv_item['Taxable'],
            "MetaData": {
                "CreateTime": csv_item['MetaData_CreateTime'],
                "LastUpdatedTime": formatted_last_updated_time
            },
            "sparse": 'true',
            "Active": csv_item['Active'],
            "SyncToken": new_sync_token,
            "InvStartDate": csv_item['InvStartDate'],
            "UnitPrice": csv_item['UnitPrice'],
            "ExpenseAccountRef": {
                "value": csv_item['ExpenseAccountRef_value'],
            },
            "PurchaseDesc": csv_item['PurchaseDesc'],
            "Description": csv_item['Description']
        }

        update_item_endpoint = f"{realm_id}/item/?minorversion={minorversion}"

        url = urljoin(base_url, update_item_endpoint)

        # Print URL
        print(f"{url}")

        # Print the full request body
        print(f"Request Body for Item ID {item_id_to_update}: {json.dumps(json_response, indent=2)}")

        # Make the POST request for updating the item
        response = requests.post(url, headers=headers, data=json.dumps(json_response))

        if response.status_code == 200:
            # Successfully updated the item
            print(f"Item with ID {item_id_to_update} updated successfully: {response.json()}")
        else:
            # Handle the error case
            print(f"Error updating item with ID {item_id_to_update}: {response.text}")

    # You can add more logic or redirect as needed
    return f'''
                          <h1>Item Updated Successfully</h1>
                          <br />
                          <pre>{json.dumps(json_response, indent=2)}</pre>


                      '''

# New route for getting and updating items
@app.route('/get_and_update_items')
def get_and_update_items():
    # Get realm_id and access_token from the query parameters or session
    realm_id = request.args.get('realm_id')
    access_token = request.args.get('access_token')

    if not realm_id or not access_token:
        return 'Realm ID or Access Token not provided in the request parameters.', 400

    # Call the API function with the obtained tokens to get items for updating last_sync_tokens
    api_response = make_items_api_request(realm_id, access_token)

    if api_response and 'error' in api_response:
        return f"Error in API call: {api_response['error']['code']}, {api_response['error']['message']}", 500

    # Update last_sync_tokens based on the obtained items data
    update_last_sync_tokens(api_response)

    # Call the function to update items using data from the CSV file
    update_response = update_item()

    # You can customize the response based on the results of the API calls
    return f'''
        <h1>Update Items</h1>
        <br />
        <pre>{update_response}</pre>
    '''

# Function to update last_sync_tokens based on the obtained items data
def update_last_sync_tokens(api_response):
    try:
        items = api_response.get('QueryResponse', {}).get('Item', [])

        for item in items:
            item_id = str(item.get('Id', ''))
            sync_token = int(item.get('SyncToken', 0))
            last_sync_tokens[item_id] = sync_token

        # Save the updated last_sync_tokens to the file after processing
        with open(last_sync_tokens_file, 'w') as file:
            json.dump(last_sync_tokens, file)

        print("last_sync_tokens updated successfully.")
    except Exception as e:
        print(f"Error updating last_sync_tokens: {str(e)}")

if __name__ == '__main__':
    print('Starting the application...')
    app.run(debug=False)
