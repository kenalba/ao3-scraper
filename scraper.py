from bs4 import BeautifulSoup
import urllib.request

# for whatever reason, ao3_api imports as AO3. Don't look at me.
import AO3
import csv
from progress.bar import Bar

TEST_URL = "https://archiveofourown.org/tags/Pride%20and%20Prejudice%20-%20Jane%20Austen/works?page=1"
PAP_BASE_DIR_URL = "https://archiveofourown.org/tags/Pride%20and%20Prejudice%20-%20Jane%20Austen/"

# The metadata fields we want to use for our eventual CSV file.
WORK_METADATA_FIELDS = ['authors', 'bookmarks', 'categories', 'characters', 'comments', 'date_published',
						'date_updated', 'fandoms', 'hits', 'kudos', 'language', 'loaded', 'oneshot', 'rating',
						'relationships', 'series', 'summary', 'tags', 'title', 'url', 'warnings', 'words', 'workid',
						'filename']


def download_and_soupify(url, parser="html.parser"):
	"""
	Given a URL, downloads the site and turns it into beautiful soup.
	"""

	response = urllib.request.urlopen(url)
	directory_html = response.read()
	index_soup = BeautifulSoup(directory_html, parser)

	return index_soup


def get_directory_urls(index_soup):
	"""
	Given the base directory as soup, figure out how many pages there are,
	and return a list of the URLs of each directory page.
	"""

	page_numbers = index_soup.find_all("ol", class_="pagination actions")

	li_entries = page_numbers[0].find_all("li")

	li_texts = [number.text for number in li_entries]
	li_digits = [int(number) for number in li_texts if number.isdigit()]
	sorted_page_numbers = sorted(li_digits)

	number_of_pages = sorted_page_numbers[-1]

	url_prefix = PAP_BASE_DIR_URL + "works?page="
	directory_urls = [(url_prefix + str(page_number)) for page_number in range(0, number_of_pages+1)]

	return directory_urls


def get_story_ids(directory_url):
	"""
	Given a single directory URL, get all stories from that URL. Returns a list of story IDs.
	"""

	dir_soup = download_and_soupify(directory_url)
	dir_links = dir_soup.find_all("a", href=True)

	dir_hrefs = [link.attrs['href'] for link in dir_links]
	work_hrefs = [link for link in dir_hrefs if "/works/" in link]
	potential_ids = [work.split("/")[2] for work in work_hrefs]
	id_list = [int(work_id) for work_id in potential_ids if work_id.isdigit()]

	story_ids = list(set(id_list))

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
	Given a list of story IDs, returns a list of downloadable story URLs. We don't need this if we're using
	the AO3 package pipeline.
	"""

	story_urls = []
	for story_id in story_ids:
		story_url = "https://archiveofourown.org/works/" + story_id + "?view_adult=true?view_full_work=true"
		story_urls.append(story_url)

	return story_urls


def create_work_dict(story_id_list):

	work_dict = {}

	progress = Bar("Getting Works:", max=len(story_id_list))

	for story_id in story_id_list:
		work = AO3.Work(story_id)
		work_dict[story_id] = {}
		work_dict[story_id]['work'] = work
		progress.next()

	progress.finish()

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

	progress = Bar("Adding texts:", max=len(work_dict.keys()))

	for story_id in work_dict.keys():
		work_string = get_fulltext_of_work(work_dict[story_id]['work'])
		work_dict[story_id]['text'] = work_string
		progress.next()

	progress.finish()

	return work_dict


def work_dict_to_files(destination_path, csv_name, work_dict):
	"""
	Takes in a path for files to live, a name for the csv file, and a work_dict (with texts!) to turn into
	a folder of texts with a matching csv file.
	"""

	csv_path = destination_path + csv_name + ".csv"
	csv_file = open(csv_path, "w", encoding="utf-8", newline="")

	writer = csv.DictWriter(csv_file, fieldnames=WORK_METADATA_FIELDS)
	writer.writeheader()

	for work_id in work_dict.keys():

		work = work_dict[work_id]['work']
		file_path = destination_path + str(work_id) + ".txt"
		work_file = open(file_path, "w", encoding="utf-8")

		work_file.write(work_dict[work_id]['text'])

		meta_dict = {'authors': work.authors, 'bookmarks': work.bookmarks, 'categories': work.categories,
					'characters': work.characters, 'comments': work.comments, 'date_published': work.date_published,
					'date_updated': work.date_updated, 'fandoms': work.fandoms, 'hits': work.hits, 'kudos': work.kudos,
					'language': work.language, 'loaded': work.loaded, 'oneshot': work.oneshot, 'rating': work.rating,
					'relationships': work.relationships, 'series': work.series, 'summary': work.summary.strip("\n"),
					'tags': work.tags, 'title': work.title, 'url': work.url, 'warnings': work.warnings,
					'words': work.words, 'workid': work.workid, 'filename': str(work_id) + ".txt"}

		writer.writerow(meta_dict)

		work_file.close()

	csv_file.close()


def get_full_work_dict(base_dir_url):
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

	# Create a dictionary of Work objects from the AO3 package for each story_id...
	work_dict = create_work_dict(story_ids)

	# Add the full raw texts...
	work_dict = add_texts_to_work_dict(work_dict)

	# And then we just need the exporting function, work_dict_to_files
	return work_dict
