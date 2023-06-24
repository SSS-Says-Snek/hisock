import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join("..", "..")))

import hisock
import random
import time

print(hisock.__file__)

client = hisock.ThreadedHiSockClient(("192.168.1.131", 8888))

@client.on("large_load")
def on_large_load(data: bytes):
    print(len(data), "recv")

client.start()

e = bytes([random.randint(97, 122) for _ in range(500000)])

try: 
    while True:
        random_idx = random.randint(len(e) - 10000, len(e))
        client.send("large_load", e[:random_idx])

        print(random_idx, "sent")
        time.sleep(1 / 60)
finally:
    client.close()