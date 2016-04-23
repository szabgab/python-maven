from __future__ import print_function
import argparse
import base64
import json
import logging
import re
import requirements
import sys
import time
import urllib2
import xml.etree.ElementTree as ET
from pymongo import MongoClient
from datetime import datetime
from github3 import login

parser = argparse.ArgumentParser()
parser.add_argument('--verbose', help='Set verbosity level', action='store_true')
parser.add_argument('--update', help='update the entries: rss - the ones received via rss; all - all of the packages already in the database')
parser.add_argument('--name', help='Name of the package to update')
parser.add_argument('--sleep', help='How many seconds to sleep between packages (Help avoiding the GitHub API limit)', type=float)
args = parser.parse_args()

# Updated:
# 1) All the entries that don't have last_update field
# 2) All the entries that were updated more than N days ago
# 3) All the entries that were updated in the last N days ??

with open('github-token') as fh:
    token = fh.readline().strip()
github = login(token=token)

client = MongoClient()
db = client.pydigger
logging.basicConfig(level= logging.DEBUG if args.verbose else logging.WARNING)
log=logging.getLogger('fetch')

def main():
    log.info("Staring")
    names = []
    packages = None

    #args.update == 'new' or args.update == 'old'):
    if args.update:
        if args.update == 'rss':
            names = get_from_rss()
        elif args.update == 'deps':
            seen = {}
            packages_with_requirements = db.packages.find({'requirements' : { '$exists' : True }}, { 'name' : True, 'requirements' : True})
            for p in packages_with_requirements:
                for r in p['requirements']:
                    name = r['name']
                    if not name:
                        log.error("Requirement {} found without a name in package {}".format(r, p))
                        continue
                    if name not in seen:
                        seen[name] = True
                        p = db.packages.find_one({'name': name})
                        if not p:
                            names.append(name)
        elif args.update == 'all':
            packages = db.packages.find({}, {'name': True})
        elif re.search(r'^\d+$', args.update):
            packages = db.packages.find().sort([('pubDate', 1)]).limit(int(args.update))
        else:
            print("The update option '{}' is not implemented yet".format(args.update))
    elif args.name:
        names.append(args.name)

    if packages:
        names = [ p['name'] for p in packages ]

    log.info("Start updating packages")
    for name in names:
        get_details(name)
        if args.sleep:
            print('sleeping', args.sleep)
            time.sleep(args.sleep)

    log.info("Finished")

#my_entries = []
def save_entry(e):
    log.info("save_entry: '{}'".format(e['name']))
    #log.debug("save_entry: {}".format(e)

    #my_entries.append(e)
    #print(e)
    # TODO make sure we only add newer version!
    # Version numbers I've seen:
    # 1.0.3
    # 20160325.161225
    # 0.2.0.dev20160325161211
    # 3.1.0a12
    # 2.0.0.dev11

    #doc = db.packages.find_one({'name' : e['name']})
    #if doc:
        #print(doc)
    db.packages.remove({'name' : e['name']})
    db.packages.remove({'name' : e['name'].lower()})
    db.packages.insert(e)


def check_github(entry):
    log.debug("check_github user='{}', project='{}".format(entry['github_user'], entry['github_project']))

    repo = github.repository(entry['github_user'], entry['github_project'])
    if not repo:
        log.error("Could not fetch GitHub repository for {}".format(entry['name']))
        entry['error'] = "Could not fetch GitHub repository"
        return

    log.debug("default_branch: ", repo.default_branch)

    # get the last commit of the default branch
    branch = repo.branch(repo.default_branch)
    if not branch:
        log.error("Could not fetch GitHub branch {} for {}".format(repo.default_branch, entry['name']))
        entry['error'] = "Could not fetch GitHub branch"
        return

    last_sha = branch.commit.sha
    log.debug("last_sha: ", last_sha)
    t = repo.tree(last_sha)
    entry['travis_ci'] = False
    entry['coveralis'] = False
    for e in t.tree:
        if e.path == '.travis.yml':
                entry['travis_ci'] = True
        if e.path == '.coveragerc':
                entry['coveralis'] = True
        if e.path == 'requirements.txt':
                entry['requirements'] = []
                try:
                    fh = urllib2.urlopen(e.url)
                    as_json = fh.read()
                    file_info = json.loads(as_json)
                    content = base64.b64decode(file_info['content'])

                    # https://github.com/ingresso-group/pyticketswitch/blob/master/requirements.txt
                    # contains -r requirements/common.txt  which means we need to fetch that file as well
                    # for now let's just skip this
                    match = re.search(r'^\s*-r', content)
                    if not match:
                        for req in requirements.parse(content):
                            log.debug("requirements: {} {} {}".format(req.name, req.specs, req.extras))
                            # we cannot use the req.name as a key in the dictionary as some of the package names have a . in them
                            # and MongoDB does not allow . in fieldnames.
                            entry['requirements'].append({ 'name' : req.name, 'specs' : req.specs })
                except Exception as e:
                    log.error("Exception when handling the requirements.txt:", e)
        # test_requirements.txt
    return()

# going over the RSS feed most recent first
def get_from_rss():
    log.debug("get_from_rss")
    rss_data = get_rss()
    packages = []
    names = []

    root = ET.fromstring(rss_data)

    for item in root.iter('item'):
        title = item.find('title').text.split(' ')
        log.debug("Seen {}".format(title))
        name = title[0]
        version = title[1]

        lcname = name.lower()

        # The same package can appear in the RSS feed twice. We only need to process it once.
        if lcname in names:
            continue

        # If this package is already in the database we only need to process if
        # the one coming in the RSS feed has a different (hopefully newer) version
        # number
        doc = db.packages.find_one({'lcname' : lcname})
        if doc and version == doc.get('version', ''):
            log.debug("Skipping '{}'. It is already in the database with this version".format(title))
            continue

        log.debug("Processing {}".format(title))
        # entry = {
        #     'link'    : item.find('link').text,
        #     'summary' : item.find('description').text,
        #     'pubDate' : datetime.strptime(item.find('pubDate').text, "%d %b %Y %H:%M:%S %Z"),
        #save_entry(entry)
        names.append(lcname)
        # packages.append((lcname, ))

    return names

def get_rss():
    latest_url = 'https://pypi.python.org/pypi?%3Aaction=rss'
    log.debug('get_rss from ' + latest_url)
    try:
        f = urllib2.urlopen(latest_url)
        rss_data = f.read()
        f.close()
        #raise Exception("hello")
    except (urllib2.HTTPError, urllib2.URLError):
        log.exception('Error while fetching ' + latest_url)
        raise Exception('Could not fetch RSS feed ' + latest_url)
    #log.debug(rss_data)
    return rss_data


def get_details(name):
    log.debug("get_details of " + name)
    entry = {}

    url = 'http://pypi.python.org/pypi/' + name + '/json'
    log.debug("Fetching url {}".format(url))
    try:
        f = urllib2.urlopen(url)
        json_data = f.read()
        f.close()
        #print(json_data)
    except (urllib2.HTTPError, urllib2.URLError):
        log.exeception("Could not fetch details of PyPI package from '{}'".format(url))
        return
    package_data = json.loads(json_data)
    #log.debug('package_data: {}'.format(package_data))

    if 'info' in package_data:
        info = package_data['info']
        if 'home_page' in info:
            entry['home_page'] = info['home_page']

        # package_url  we can deduct this from the name
        # _pypi_hidden
        # _pypi_ordering
        # release_url
        # downloads - a hash, but as we are monitoring recent uploads, this will be mostly 0
        # classifiers - an array of stuff
        # releases
        # urls
        for f in ['name', 'maintainer', 'docs_url', 'requires_python', 'maintainer_email',
        'cheesecake_code_kwalitee_id', 'cheesecake_documentation_id', 'cheesecake_installability_id',
        'keywords', 'author', 'author_email', 'download_url', 'platform', 'description', 'bugtrack_url',
        'license', 'summary', 'version']:
            if f in info:
                entry[f] = info[f]

        entry['split_keywords'] = []
        if 'keywords' in info:
            keywords = info['keywords']
            if keywords != None and keywords != "":
                keywords = keywords.encode('utf-8')
                keywords = keywords.lower()
                if re.search(',', keywords):
                    entry['split_keywords'] = keywords.split(',')
                else:
                    entry['split_keywords'] = keywords.split(' ')

    process_release(name, entry, package_data)

    if 'home_page' in entry and entry['home_page'] != None:
        try:
            match = re.search(r'^https?://github.com/([^/]+)/([^/]+)/?$', entry['home_page'])
        except Exception:
            log.exception('Error while tying to match home_page:' + entry['home_page'])

        if match:
            entry['github'] = True
            entry['github_user'] = match.group(1)
            entry['github_project'] = match.group(2)
            check_github(entry)
        else:
            entry['github'] = False
            #entry['error'] = 'Home page URL is not GitHub'
    entry['lcname'] = entry['name'].lower()
    save_entry(entry)


def process_release(name, entry, package_data):
    version = entry['version']
    if 'urls' in package_data:
        entry['urls'] = package_data['urls']
    if not 'releases' in package_data:
        log.error("There are no releases in package {} --- {}".format(name, package_data))
    elif not version in package_data['releases']:
        log.error("Version {} is not in the releases of package {} --- {}".format(version, name, package_data))
    elif len(package_data['releases'][version]) == 0:
        log.error("Version {} has no elements in the releases of package {} --- {}".format(version, name, package_data))
    else:
        # find the one that has python_version: "source",
        # actually we find the first one that has python_version: source
        # maybe there are more?
        source = package_data['releases'][version][0]
        for version_pack in package_data['releases'][version]:
            if 'python_version' in version_pack and version_pack['python_version'] == 'source':
                if 'url' in version_pack:
                    entry['download_url'] = version_pack['url']
                else:
                    log.error("Version {} has no download_url in the releases of package {} --- {}".format(version, name, package_data))
                source = version_pack
                break

            #url: https://pypi.python.org/packages/ce/c7/6431a8ba802bf93d611bfd53c05abcc078165b8aad3603d66c02a847af7d/codacy-coverage-1.2.10.tar.gz
            #filename: codacy-coverage-1.2.10.tar.gz
            #url: https://pypi.python.org/packages/84/85/5ce28077fbf455ddf0ba2506cdfdc2e5caa0822b8a4a2747da41b683fad8/purepng-0.1.3.zip

        if not 'upload_time' in source:
            log.error("upload_time is missing from version {} in the releases of package {} --- {}".format(version, name, package_data))
        else:
            upload_time = source['upload_time']
            entry['upload_time'] = datetime.strptime(upload_time, "%Y-%m-%dT%H:%M:%S")
