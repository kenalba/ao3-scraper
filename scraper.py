from bs4 import BeautifulSoup
import urllib.request
import csv
from time import sleep
import pickle
from os import path

# for whatever reason, ao3_api imports as AO3. Don't look at me.
import AO3


TEST_URL = "https://archiveofourown.org/tags/Pride%20and%20Prejudice%20-%20Jane%20Austen/"
EMMA_TEST_URL = "https://archiveofourown.org/tags/Emma%20-%20Jane%20Austen/"

# The metadata fields we want to use for our eventual CSV file.
WORK_METADATA_FIELDS = ['authors', 'bookmarks', 'categories', 'characters', 'comments', 'date_published',
						'date_updated', 'fandoms', 'hits', 'kudos', 'language', 'loaded', 'oneshot', 'rating',
						'relationships', 'series', 'summary', 'tags', 'title', 'url', 'warnings', 'words', 'workid',
						'filename']


# TODO: Remove the AO3 library entirely and grab metadata from the single full-text html query. Halves download time.
# TODO: Modularize downloading such that interrupted downloads result in partially full work_dicts rather than nothing.


def download_and_soupify(url, parser="html.parser"):
	"""
	Given a URL, downloads the site and turns it into beautiful soup.
	"""

	full_url = url + "works"
	response = urllib.request.urlopen(full_url)
	directory_html = response.read()
	index_soup = BeautifulSoup(directory_html, parser)

	return index_soup


def get_directory_urls(url, index_soup):
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

	url_prefix = url + "works?page="
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


def get_all_story_ids(directory_urls, sleep_time=0):
	"""
	Given a list of directory URLs, goes through each directory and grabs all of the story IDs from every page.
	"""

	# WARNING: AO3 has a rate limiter that'll catch you if you try this with a full list of Story IDs.
	# It doesn't trip up the limiter with up to 80 pages of stories. If it breaks on something higher, let me know.

	all_story_ids = []
	for url in directory_urls:
		sleep(sleep_time)
		all_story_ids += get_story_ids(url)

	return all_story_ids


def get_all_story_ids_pickles(directory_urls, storage_path, sleep_time=0):
	"""
	Given a list of directory URLs, goes through each directory and grabs all of the story IDs from every page.
	This version is more robust because it pickles progress as you go and resumes.
	"""

	# WARNING: AO3 has a rate limiter that'll catch you if you try this with a full list of Story IDs.
	# It doesn't trip up the limiter with up to 80 pages of stories. If it breaks on something higher, let me know.
	with open(storage_path, "rb") as fp:
		all_story_ids = pickle.load(fp)
	starting_point = int(len(all_story_ids)/20)

	for url in directory_urls[starting_point:]:
		try:
			all_story_ids += get_story_ids(url)
			print("Page " + url.split("page=")[1] + " of " + str(len(directory_urls)) + " complete.")
			with open(storage_path, "wb") as fp:
				pickle.dump(all_story_ids, fp)
			sleep(sleep_time)
		except urllib.error.HTTPError:
			print("HTTP error! Probably too many requests. Waiting 2 minutes and then trying again.")
			sleep(120)
			pass

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


def create_work_dict(story_id_list, sleep_time=6):
	"""
	The meat of the script. This takes in a list of story_ids from either get_story_ids or get_all_story_ids
	and downloads every one of them with the AO3 library as a Work object.

	Unfortunately, Work objects do not contain the full text of the story - hence the add_texts_to_work function.

	Eventually, this function and that function should be combined; the full text of the story downloaded
	for the other function contains the raw metadata, it just isn't formatted nicely like AO3's is.

	sleep_time is the time, in seconds, to wait between web requests if there are more than 60
	story IDs. This stops the script from being rate limited. 7 seconds seems to work okay; it may
	be possible to go faster.
	"""
	work_dict = {}

	num = 0

	number_of_stories = len(story_id_list)

	if number_of_stories < 60:
		sleep_time = 0

	for story_id in story_id_list:
		work = AO3.Work(story_id)
		work_dict[story_id] = {}
		work_dict[story_id]['work'] = work
		# this is to avoid violating their rate-limit policy
		sleep(sleep_time)

		num += 1
		print("Finished story", num, "/", number_of_stories)

	return work_dict


def create_work_dict_pickle(story_id_list, pickle_filename, sleep_time=6):
	"""
	The meat of the script. This takes in a list of story_ids from either get_story_ids or get_all_story_ids
	and downloads every one of them with the AO3 library as a Work object.

	Unfortunately, Work objects do not contain the full text of the story - hence the add_texts_to_work function.

	Eventually, this function and that function should be combined; the full text of the story downloaded
	for the other function contains the raw metadata, it just isn't formatted nicely like AO3's is.

	sleep_time is the time, in seconds, to wait between web requests if there are more than 60
	story IDs. This stops the script from being rate limited. 7 seconds seems to work okay; it may
	be possible to go faster.
	
	# This version preserves progress in a pickle file.
	"""

	pickle_filepath = path.join("pickles", pickle_filename)
	if path.exists(pickle_filepath):
		with open(pickle_filepath, "rb") as fp:
			work_dict = pickle.load(fp)
	else:
		work_dict = {}

	num = 0

	number_of_stories = len(story_id_list)
	latest_story = len(work_dict)
	print("Starting at story number " + str(latest_story))

	if number_of_stories < 60:
		sleep_time = 0

	try:
		for story_id in story_id_list[latest_story:]:
			work = AO3.Work(story_id)
			work_dict[story_id] = {}
			work_dict[story_id]['work'] = work
			# this is to avoid violating their rate-limit policy
			sleep(sleep_time)

			num += 1
			print("Finished story", num, "/", number_of_stories)
			with open(pickle_filepath, "wb") as fp:
				pickle.dump(work_dict, fp)
	except urllib.error.HTTPError:
		print("HTTP error! Probably too many requests. Waiting 2 minutes and then trying again.")
		sleep(120)
		pass

	return work_dict


def create_new_work_dict(story_id_list, old_work_dict, sleep_time=6):

	"""
	Works a lot like the create_work_dict function, but has an additional parameter,
	old_work_dict, that's meant to be a completely full work_dict. If we've already downloaded the book we're
	looking for, there's no reason to download it again.
	"""
	work_dict = {}

	num = 0
	number_of_stories = len(story_id_list)

	if number_of_stories < 60:
		sleep_time = 0

	for story_id in story_id_list:
		if story_id in old_work_dict.keys():
			work_dict[story_id] = old_work_dict[story_id]
		else:
			work = AO3.Work(story_id)
			work_dict[story_id] = {}
			work_dict[story_id]['work'] = work
			# this is to avoid violating their rate-limit policy
			sleep(sleep_time)

		num += 1
		print("Finished story", num, "/", number_of_stories)

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


def add_texts_to_work_dict(work_dict, sleep_time=6):
	"""
	Takes in a work_dict that doesn't have its raw texts and adds the texts to them.

	Returns a work_dict in the form of work_dict[story_id] = { 'Work': Work_object, 'text': full_text_of_story}.

	sleep_time is the time, in seconds, to wait between web requests if there are more than 60
	story IDs. This stops the script from being rate limited. 8 seconds seems to work okay; it may
	be possible to go faster.

	See comment on create_work_dict for more details.
	"""

	texted_work_dict = {}

	num = 0

	number_of_stories = len(work_dict.keys())
	if number_of_stories < 60:
		sleep_time = 0

	for story_id in work_dict.keys():

		try:
			if work_dict[story_id]['text'] is not None:
				texted_work_dict[story_id] = work_dict[story_id]
				print("Already had full text of", story_id)

		except KeyError:
			print("Downloading", story_id)
			try:
				work_string = get_fulltext_of_work(work_dict[story_id]['work'])
				texted_work_dict[story_id] = {}
				texted_work_dict[story_id]['work'] = work_dict[story_id]['work']
				texted_work_dict[story_id]['text'] = work_string
				# this is to avoid violating their rate-limit policy
				sleep(sleep_time)
			except:
				print("Error downloading work", story_id)
				texted_work_dict[story_id] = {}
				texted_work_dict[story_id]['work'] = work_dict[story_id]['work']
				texted_work_dict[story_id]['text'] = "Error"

		print("Finished story", num, "/", number_of_stories)
		num += 1

	return texted_work_dict


def add_texts_to_work_dict_pickle(work_dict, pickle_filename, sleep_time=6):
	"""
	Takes in a work_dict that doesn't have its raw texts and adds the texts to them.

	Returns a work_dict in the form of work_dict[story_id] = { 'Work': Work_object, 'text': full_text_of_story}.

	sleep_time is the time, in seconds, to wait between web requests if there are more than 60
	story IDs. This stops the script from being rate limited. 8 seconds seems to work okay; it may
	be possible to go faster.

	See comment on create_work_dict for more details.
	"""
	pickle_filepath = path.join("pickles", pickle_filename)
	if path.exists(pickle_filepath):
		with open(pickle_filepath, "rb") as fp:
			work_dict = pickle.load(fp)

	texted_work_dict = {}

	num = 0

	number_of_stories = len(work_dict.keys())
	if number_of_stories < 60:
		sleep_time = 0

	for story_id in work_dict.keys():

		try:
			if work_dict[story_id]['text'] is not None:
				texted_work_dict[story_id] = work_dict[story_id]
				print("Already had full text of", story_id)

		except KeyError:
			print("Downloading", story_id)
			try:
				work_string = get_fulltext_of_work(work_dict[story_id]['work'])
				texted_work_dict[story_id] = {}
				texted_work_dict[story_id]['work'] = work_dict[story_id]['work']
				texted_work_dict[story_id]['text'] = work_string
				# this is to avoid violating their rate-limit policy
				sleep(sleep_time)
			except:
				print("Error downloading work", story_id)
				texted_work_dict[story_id] = {}
				texted_work_dict[story_id]['work'] = work_dict[story_id]['work']
				texted_work_dict[story_id]['text'] = "Error"

		with open(pickle_filepath, "wb") as fp:
			pickle.dump(texted_work_dict, fp)

		print("Finished story", num, "/", number_of_stories)
		num += 1

	return texted_work_dict


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

		try:
			meta_dict = {'authors': work.authors, 'bookmarks': work.bookmarks, 'categories': work.categories,
						'characters': work.characters, 'comments': work.comments, 'date_published': work.date_published,
						'date_updated': work.date_updated, 'fandoms': work.fandoms, 'hits': work.hits, 'kudos': work.kudos,
						'language': work.language, 'loaded': work.loaded, 'oneshot': work.oneshot, 'rating': work.rating,
						'relationships': work.relationships, 'series': work.series, 'summary': work.summary.strip("\n"),
						'tags': work.tags, 'title': work.title, 'url': work.url, 'warnings': work.warnings,
						'words': work.words, 'workid': work.workid, 'filename': str(work_id) + ".txt"}
		except AttributeError:
			print("Couldn't write ",work_id)

		writer.writerow(meta_dict)

		work_file.close()

	csv_file.close()


def get_full_work_dict(url):
	"""
	This isn't actually ready to use - it's just where I'm keeping a note of the sequence these functions
	should be used in order to initialize a corpus.

	What remains to be done is to turn the dump the downloaded work_dict into text files _and_ CSV lines.

	Work objects already have a lot of metadata. The easiest solution will be to just grab all of that + to add
	in the file name.
	"""

	# Directory URL has to be the base URL for a given fandom. e.g.
	# https://archiveofourown.org/tags/Pride%20and%20Prejudice%20-%20Jane%20Austen/works?page=1
	fandom_id = url.split("/")[5]
	directory_soup = download_and_soupify(url)
	directory_urls = get_directory_urls(url, directory_soup)

	# This function will grab all of the story IDs. It'll take its time doing so and will store them in a pickle file
	# in case it gets interrupted.

	story_id_pickle_filename = fandom_id + "_storyIDs.pickle"
	story_ids = get_all_story_ids_pickles(directory_urls, story_id_pickle_filename, sleep_time=7)

	work_dict = {}

	# Create a dictionary of Work objects from the AO3 package for each story_id...
	work_dict_pickle_filename = fandom_id + "_works.pickle"
	work_dict = create_work_dict_pickle(story_ids, work_dict_pickle_filename, sleep_time=7)

	# Add the full raw texts...
	work_dict = add_texts_to_work_dict(work_dict)

	# And then we just need the exporting function, work_dict_to_files
	output_path = path('output', fandom_id)
	csv_name = fandom_id
	work_dict_to_files(output_path, csv_name, work_dict)

	print("Complete!)")

	return work_dict
