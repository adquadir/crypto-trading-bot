import websocket
import os

proxy_host = os.getenv('PROXY_HOST')
proxy_port = os.getenv('PROXY_PORT')
proxy_user = os.getenv('PROXY_USER')
proxy_pass = os.getenv('PROXY_PASS')

ws_url = 'wss://fstream.binance.com/ws/btcusdt@trade'

proxy_auth = f'{proxy_user}:{proxy_pass}' if proxy_user and proxy_pass else None

try:
    ws = websocket.create_connection(
        ws_url,
        http_proxy_host=proxy_host,
        http_proxy_port=int(proxy_port) if proxy_port else None,
        http_proxy_auth=(proxy_user, proxy_pass) if proxy_user and proxy_pass else None,
        timeout=10
    )
    print('WebSocket connection established!')
    print('Receiving a message...')
    print(ws.recv())
    ws.close()
except Exception as e:
    print(f'WebSocket connection failed: {e}') 