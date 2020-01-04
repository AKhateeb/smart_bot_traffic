from flask import Flask, render_template, request, Response
import os, json, random, requests, time, logging
from requests.exceptions import ProxyError

# from itertools import cycle
from threading import Lock, Thread

import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
# disable some warnings of avoiding SSL

app = Flask(__name__)
app.logger.setLevel(logging.ERROR)

log = logging.getLogger('werkzeug')
log.disabled = True

ADS_DIR = "static/ads-images" # relative path
LIMIT = 50
MAX_ATTEMPTS = 10
CONN_ERR_SLEEP = 3

global total_visits, proxy_pool

total_visits = []
lock = Lock()

def get_proxies_from_file():
    all_ips = []
    with open("IPs.txt", 'r') as f:
        all_ips = f.readlines()
    validated_ips = [ip.strip() for ip in all_ips]
    return validated_ips

def get_free_proxies(limit=20):
    url = 'https://free-proxy-list.net/'
    from lxml.html import fromstring
    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = set()
    for i in parser.xpath('//tbody/tr')[:limit]:
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
            proxies.add(proxy)
    return proxies


# proxy_pool = cycle(get_free_proxies())
# proxy_pool = list(get_free_proxies())
proxy_pool = list(get_proxies_from_file())

@app.route("/")
def home():
    return render_template("home.html")
    # return "Hello, World!"
    
@app.route("/get_visits")
def get_visits():
    # total_visits = random.randint(1, 55)
    response_data = {} 
    with lock:
        response_data['succeeded_ips'] = list(set(total_visits))[:LIMIT] # list(set(total_visits))
        response_data['n_succeeded'] = min(len(total_visits), LIMIT)
        if response_data['n_succeeded'] >= LIMIT:
            with open("visits_output.txt", "w") as f:
                f.write("\n".join(total_visits))
    return Response(response=json.dumps(response_data), status=200)

def do_visit(proxy, url, index, attempts = 1):
    if attempts > MAX_ATTEMPTS: # don't stop but try another IP
        # proxy = next(proxy_pool)
        return
        
    try:
        # if attempts == 1:
        #     time.sleep(index*2)
        # print(f"[{index}].{attempts} Requesting from [{proxy.ljust(14)}] ...")
        response = requests.get(
            url,
            verify=False, # to avoid SSLError
            proxies={"http": proxy, "https": proxy}, )
        if response.status_code == 200:
            print(f"[{proxy.ljust(14)}] ----> SUCCEEDED, No:{index}.{attempts}")
            with lock:
                total_visits.append(proxy)
    
    except ProxyError:
        proxy = random.choice(proxy_pool)
        do_visit(proxy, url, index, attempts +1)
        print(f"Trying a new Proxy, No.{index}.{attempts}")
        time.sleep(1*random.random())

    except Exception as exp:
        print(exp.__class__.__name__)
        print(f"[{proxy.ljust(14)}] ----> FAILED, No:{index}.{attempts}")
        time.sleep(CONN_ERR_SLEEP*attempts)
        do_visit(proxy, url, index, attempts +1)
    return

@app.route("/start_bot")
def start_bot():
    result = {}
    result['ads_list'] = [img for img in os.listdir(ADS_DIR) if img.split(".")[-1].lower() in ['png', 'jpg', 'gif'] and not img.startswith("default")]
    # result['ads_list'] = [os.path.join(ADS_DIR, ad_img) for ad_img in os.listdir(ADS_DIR)]
    url = request.args.get("url")
    print(url)
    if isinstance(url, str) and not url.startswith("http"):
        url = "http://" + url.split("//")[0]
    try: 
        check_url = requests.get(url) # returns True or raise an Exception
        if not check_url: raise Exception
    except: 
        print("Invalid URL: ", url)
        return Response(response="Invalid URL", status=400)

    with lock:
        global total_visits
        total_visits = []

    # proxy_pool = cycle(get_free_proxies())

    for i in range(1, LIMIT+10):
        #Get a proxy from the pool
        proxy = random.choice(proxy_pool)
        visit = Thread(target=do_visit, name="t_" + str(i), args=(proxy, url, i), daemon=True)
        visit.start()
    result['n_workers'] = LIMIT
    
    return Response(response=json.dumps(result), status=200)

if __name__ == "__main__":
    app.run(debug=True)