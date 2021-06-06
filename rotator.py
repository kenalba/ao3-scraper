import requests
import AO3
import time
from itertools import cycle
from bs4 import BeautifulSoup
from scraper import download_and_soupify, get_directory_urls

"""
Developer's Note

This version of the scraper uses rotating proxies to get around AO3's rate limiting. As such, it's ethically dubious
to use. 

I suggest making a donation to AO3 any time you substantively stress their servers! That's what I do.

"""
def get_proxies(proxy_txt_filepath = "proxies.txt"):
    """ Put at least 7 proxy IPs in proxies.txt. """

    with open(proxy_txt_filepath) as f:
        proxies = [line.strip() for line in f]

    return proxies


def get_all_story_ids_proxy(directory_urls, proxies):
    """ Gets all story ids, given the list of directory urls. Uses rotating proxies."""

    start = time.time()
    all_story_ids = []
    proxy_pool = cycle(proxies)

    for x in range(0, len(directory_urls)):

        url = directory_urls[x]
        print("Getting directory", x, "of", len(directory_urls))

        proxy = next(proxy_pool)
        req = requests.get(url, proxies={"http": proxy, "https": proxy})

        dir_soup = BeautifulSoup(req.content, "html.parser")
        dir_links = dir_soup.find_all("a", href=True)
        dir_hrefs = [link.attrs['href'] for link in dir_links]
        work_hrefs = [link for link in dir_hrefs if "/works/" in link]
        potential_ids = [work.split("/")[2] for work in work_hrefs]
        id_list = [int(work_id) for work_id in potential_ids if work_id.isdigit()]
        story_ids = list(set(id_list))

        all_story_ids += story_ids

    end = time.time()
    print("It took ", end-start, " seconds to download ", len(directory_urls), " indices. Est. Time for work-dict = ",(end-start)*20)

    return all_story_ids


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

    for x in range(0, len(story_id_list)):
        story_id = story_id_list[x]
        story_url = "https://archiveofourown.org/works/" + str(story_id) + "?view_adult=true?view_full_work=true"
        print("Starting story ", x, "of ", len(story_id_list))
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


def pipeline(url, proxies):

    directory_soup = download_and_soupify(url)
    directory_urls = get_directory_urls(directory_soup, url.replace("works", ""))

    story_ids = get_all_story_ids_proxy(directory_urls, proxies)

    work_dict = create_work_dict_proxy(story_ids, proxies)

    return work_dict