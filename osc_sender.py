from pythonosc import udp_client
import time

client = udp_client.SimpleUDPClient("127.0.0.1", 9000)

while True:
    client.send_message("/test", 1)
    print("enviando sinal...")
    time.sleep(1)