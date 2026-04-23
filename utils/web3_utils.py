import requests
import os
import json
from web3 import Web3

# --- Configuration (Demo Placeholders) ---
# For actual use, user should set these in Environment Variables
PINATA_API_KEY = os.environ.get('PINATA_API_KEY', 'MOCK_PINATA_KEY')
PINATA_SECRET_KEY = os.environ.get('PINATA_SECRET_KEY', 'MOCK_PINATA_SECRET')
POLYGON_RPC_URL = os.environ.get('POLYGON_RPC_URL', 'https://rpc-amoy.polygon.technology')
WALLET_PRIVATE_KEY = os.environ.get('WALLET_PRIVATE_KEY', '0x_MOCK_PRIVATE_KEY')
WALLET_ADDRESS = os.environ.get('WALLET_ADDRESS', '0x_MOCK_WALLET_ADDRESS')

w3 = Web3(Web3.HTTPProvider(POLYGON_RPC_URL))

def upload_to_ipfs(data):
    """
    Uploads JSON metadata to Pinata IPFS.
    """
    if PINATA_API_KEY == 'MOCK_PINATA_KEY':
        print("Warning: Mocking IPFS Upload (No Pinata Key)")
        return "Qm_MOCK_IPFS_HASH_FOR_CRIME_ALERT"

    url = "https://api.pinata.cloud/pinning/pinJSONToIPFS"
    headers = {
        'pinata_api_key': PINATA_API_KEY,
        'pinata_secret_api_key': PINATA_SECRET_KEY,
        'Content-Type': 'application/json'
    }
    
    response = requests.post(url, json=data, headers=headers)
    if response.status_code == 200:
        return response.json()['IpfsHash']
    else:
        print(f"IPFS Error: {response.text}")
        return None

def log_alert_on_chain(ipfs_hash, user_id="Guest"):
    """
    Logs the IPFS hash onto Polygon as a transaction.
    """
    if WALLET_PRIVATE_KEY == '0x_MOCK_PRIVATE_KEY':
        print("Warning: Mocking Blockchain Transaction (No Private Key)")
        return "0x_MOCK_POLYGON_TX_HASH_123456789"

    try:
        # Simple data-store transaction (logging message in 'input' field)
        nonce = w3.eth.get_transaction_count(WALLET_ADDRESS)
        
        # Prepare data to be stored securely
        data_to_store = w3.to_hex(text=f"SOS_ALERT:{ipfs_hash}:USER:{user_id}")
        
        tx = {
            'nonce': nonce,
            'to': WALLET_ADDRESS, # Send to self to log data
            'value': w3.to_wei(0, 'ether'),
            'gas': 21000 + (len(data_to_store) * 16), # Simple data gas estimate
            'gasPrice': w3.eth.gas_price,
            'data': data_to_store,
            'chainId': 80002 # Polygon Amoy Testnet
        }
        
        signed_tx = w3.eth.account.sign_transaction(tx, WALLET_PRIVATE_KEY)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        return w3.to_hex(tx_hash)
    except Exception as e:
        print(f"Blockchain Error: {e}")
        return None
