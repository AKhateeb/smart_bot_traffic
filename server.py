from flask import Flask, render_template, request, Response
import os, json, random, requests, time
from itertools import cycle
from threading import Lock, Thread
import ipaddress

app = Flask(__name__)

ADS_DIR = "static/ads-images" # relative path
LIMIT = 50
MAX_ATTEMPTS = 3

global total_visits

total_visits = []
lock = Lock()

def get_proxies_from_file():
    all_ips = []
    with open("IPs.txt", 'r') as f:
        all_ips = f.readlines()
    validated_ips = [ip.strip() for ip in all_ips]
    return validated_ips

def get_free_proxies():
    url = 'https://free-proxy-list.net/'
    from lxml.html import fromstring

    response = requests.get(url)
    parser = fromstring(response.text)
    proxies = set()
    for i in parser.xpath('//tbody/tr')[:10]:
        if i.xpath('.//td[7][contains(text(),"yes")]'):
            proxy = ":".join([i.xpath('.//td[1]/text()')[0], i.xpath('.//td[2]/text()')[0]])
            proxies.add(proxy)
    return proxies


@app.route("/")
def home():
    return render_template("home.html")
    # return "Hello, World!"
    
@app.route("/get_visits")
def get_visits():
    # total_visits = random.randint(1, 55)
    response_data = {} 
    with lock:
        response_data['succeeded_ips'] = list(set(total_visits))
        response_data['n_succeeded'] = len(total_visits)
        if response_data['n_succeeded'] == LIMIT:
            with open("visits_output.txt", "r") as f:
                f.write("\n".join(total_visits))
    return Response(response=json.dumps(response_data), status=200)

def do_visit(proxy, url, index, attempts = 1):
    if attempts > MAX_ATTEMPTS: return
    try:
        if attempts == 1:
            time.sleep(index*2)
        print(f"[{index}].{attempts} Requesting ...")
        response = requests.get(url,proxies={"http": proxy, "https": proxy})
        if response.status_code == 200:
            print("success")
            with lock:
                total_visits.append(proxy)

    except Exception as exp:
        print("Connection error, Attempts:", attempts)
        time.sleep(random.randint(3,8))
        do_visit(proxy, url, index, attempts +1)
        # print(exp)
    return

@app.route("/start_bot")
def start_bot():
    result = {}
    result['ads_list'] = [img for img in os.listdir(ADS_DIR) if img.split(".")[-1].lower() in ['png', 'jpg', 'gif']]
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
        return Response(response="Invalid URL", status=405)

    with lock:
        total_visits = []

    proxy_pool = cycle(get_proxies_from_file())
    proxy = proxy_pool.__next__()

    for i in range(1, LIMIT+1):
        #Get a proxy from the pool
        visit = Thread(target=do_visit, name="t_" + str(i), args=(proxy, url, i), daemon=True)
        visit.start()
    result['n_workers'] = i
    
    return Response(response=json.dumps(result), status=200)

if __name__ == "__main__":
    app.run(debug=True)