import requests
from itertools import cycle
from bs4 import BeautifulSoup
import AO3


def get_proxies(proxy_txt_filepath = "proxies.txt"):
    with open(proxy_txt_filepath) as f:
        proxies = [line.strip() for line in f]

    return proxies


def get_work_soup_from_url(url, proxy = None):
    try:
        if proxy:
            req = requests.get(url, proxies={"http": proxy, "https": proxy})
        else:
            req = requests.get(url)
    except Exception as e:
        print(e)
        return False

    soup = BeautifulSoup(req.content, 'lxml')

    return soup


def create_work_dict_proxy(story_id_list, proxies):
    proxy_pool = cycle(proxies)

    work_dict = {}


    for story_id in story_id_list:
        story_url = "https://archiveofourown.org/works/" + str(story_id) + "?view_adult=true?view_full_work=true"
        print("Downloading story ", story_id)
        work = AO3.Work(story_id, load=False)
        work_soup = False
        while not work_soup:
            proxy = next(proxy_pool)
            work_soup = get_work_soup_from_url(story_url, proxy)

        work._soup = work_soup
        work_dict[story_id] = {}
        work_dict[story_id]['work'] = work

        # Finding the work and downloading it.

        download_btn = work._soup.find("li", {"class": "download"})
        for download_type in download_btn.findAll("li"):
            if download_type.a.getText() == "HTML":
                got_it = False
                while not got_it:
                    print("Trying to download ", story_id)
                    url = f"https://archiveofourown.org/{download_type.a.attrs['href']}"
                    proxy = next(proxy_pool)
                    req = requests.get(url, proxy)
                    if req.status_code == 429:
                        print("Rate limited. Trying with a new proxy...")
                    elif not req.ok:
                        print("Rate limited.")
                    else:
                        text_html_string = req.content
                        got_it = True

        soup = BeautifulSoup(text_html_string, "html.parser")
        paras = soup.find_all("p")
        paras_list = [para.text for para in paras]
        output_string = "\n".join(paras_list)
        work_dict[story_id]['text'] = output_string

    return work_dict