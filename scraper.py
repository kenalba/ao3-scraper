from bs4 import BeautifulSoup
import urllib.request

# for whatever reason, ao3_api imports as AO3.
import AO3

TEST_URL = "https://archiveofourown.org/tags/Pride%20and%20Prejudice%20-%20Jane%20Austen/works?page=1"
PAP_BASE_DIR_URL = "https://archiveofourown.org/tags/Pride%20and%20Prejudice%20-%20Jane%20Austen/"


def test_main(base_dir_url):
	"""
	This isn't actually ready to use - it's just where I'm keeping a note of the sequence these functions
	should be used in order to initialize a corpus.

	What remains to be done is to turn the dump the downloaded work_dict into text files _and_ CSV lines.

	Work objects already have a lot of metadata. The easiest solution will be to just grab all of that + to add
	in the file name.

	Filenames should probably be work IDs.
	"""

	# Directory URL has to be the base URL for a given fandom. e.g.
	# https://archiveofourown.org/tags/Pride%20and%20Prejudice%20-%20Jane%20Austen/works?page=1

	directory_soup = download_and_soupify(base_dir_url)
	directory_urls = get_directory_urls(directory_soup)

	# For right now, just grab the first page's worth of stories.
	story_ids = get_story_ids(directory_urls[0])

	work_dict = {}

	# Create a dictionary of Work objects from the AO3 package.
	work_dict = create_work_dict(story_ids)

	work_dict = add_texts_to_work_dict(work_dict)

	return work_dict


def download_and_soupify(url, parser="html.parser"):
	"""
	Given a URL, downloads the site and turns it into beautiful soup.
	"""
	response = urllib.request.urlopen(url)
	directory_html = response.read()
	index_soup = BeautifulSoup(directory_html, 'html.parser')

	return index_soup


def get_directory_urls(index_soup):
	"""
	Given the base directory as soup, figure out how many pages there are, and return a list of the URLs of each directory page.
	"""

	page_numbers = index_soup.find_all("ol", class_="pagination actions")
	page_numbers = page_numbers[0].find_all("li")
	page_numbers = [number.text for number in page_numbers if number.text.isdigit()]
	page_numbers = [int(number) for number in page_numbers]
	page_numbers.sort()
	number_of_pages = page_numbers[-1]

	url_prefix = PAP_BASE_DIR_URL + "works?page="
	directory_urls = [(url_prefix + str(page_number)) for page_number in range(0, number_of_pages+1)]

	return directory_urls


def get_story_ids(directory_url):
	"""
	Given a single directory URL, get all stories from that URL. Returns a list of story IDs.
	"""

	dir_soup = download_and_soupify(directory_url)
	dir_links = dir_soup.find_all("a", href=True)
	less_dir_links = [link.attrs['href'] for link in dir_links if "/works/" in link.attrs['href']]
	even_less_dir_links = [int(work.split("/")[2]) for work in less_dir_links if work.split("/")[2].isdigit()]

	story_ids = list(set(even_less_dir_links))

	return story_ids


def get_all_story_ids(directory_urls):
	"""
	Given a list of directory URLs, goes through each directory and grabs all of the story IDs from every page.
	"""

	all_story_ids = []
	for url in directory_urls:
		all_story_ids += get_story_ids(url)

	return all_story_ids


def get_story_urls(story_ids):
	"""
	Given a list of story IDs, returns a list of downloadable story URLs.
	"""

	story_urls = []
	for story_id in story_ids:
		story_url = "https://archiveofourown.org/works/" + story_id + "?view_adult=true?view_full_work=true"
		story_urls.append(story_url)

	return story_urls


def create_work_dict(story_id_list):

	work_dict = {}

	for story_id in story_id_list:
		work = AO3.Work(story_id)
		work_dict[story_id] = {}
		work_dict[story_id]['Work'] = work

	return work_dict


def get_fulltext_of_work(work):
	"""
	Takes in a work object, returns the plaintext version of the text.
	"""

	text_html_string = work.download("HTML")
	soup = BeautifulSoup(text_html_string, "html.parser")
	paras = soup.find_all("p")
	paras_list = [para.text for para in paras]
	output_string = "\n".join(paras_list)

	return output_string


def add_texts_to_work_dict(work_dict):
	"""
	Takes in a work_dict that doesn't have its raw texts and adds the texts to them.

	Returns a work_dict in the form of work_dict[story_id] = { 'Work': Work_object, 'text': full_text_of_story}
	"""

	for story_id in work_dict.keys():
		work_string = get_fulltext_of_work(work_dict[story_id]['Work'])
		work_dict[story_id]['text'] = work_string

	return work_dict
