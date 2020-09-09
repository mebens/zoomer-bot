import secrets
import time

# just a small script to generate that quick shot of youtube URLs flying past
 
for i in range(10000):
    print(secrets.token_urlsafe(11))
    time.sleep(0.01)

