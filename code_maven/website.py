from __future__ import division
from flask import Flask, render_template, redirect, abort, request
import time, json, os, math
from pymongo import MongoClient
import pymongo
import datetime
#import re

app = Flask(__name__)

client = MongoClient()
db = client.pydigger
#root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def get_int(field, default):
    value = request.args.get(field, default)
    try:
        value = int(value)
    except Exception:
        value = default
    return value

cases = {
    'no_summary'   : { '$or' : [{'summary' : ''}, {'summary' : None}] },
    'no_license'   : { '$or' : [{'license' : ''}, {'license' : None}] },
    'no_github'    : { 'github' : False },
    'has_github'   : { 'github' : True },
    'no_docs_url'  : { '$or' : [ { 'docs_url' : { '$exists' : False} }, { 'docs_url' : None} ] },
    'has_docs_url' : { 'docs_url' : { '$not' : { '$eq' : None }}},
    'no_requires_python' : { '$or' : [ { 'requires_python' : { '$exists' : False} }, { 'requires_python' : None}, { 'requires_python' : ''} ] },
    'no_cheesecake_installability_id' : { '$or' : [ { 'cheesecake_installability_id' : { '$exists' : False} }, { 'cheesecake_installability_id' : None}, { 'cheesecake_installability_id' : ''} ] },
    'no_author' : { '$or' : [ { 'author' : { '$exists' : False} }, { 'author' : None}, { 'author' : ''}, { 'author' : 'UNKNOWN'} ] },
    'has_author' : { '$and' : [ {'author' : { '$not' : { '$eq' : None} } }, {'author' : { '$not' : { '$eq' : ''} }}, {'author' : { '$not' : {'$eq' : 'UNKNOWN'}}} ] },
    'no_keywords'    : {'$or' : [ { 'keywords' : "" }, { 'keywords' : None } ] },
    'has_keywords'   : { '$and' : [ { 'keywords' : { '$not' : { '$eq' : "" } } }, { 'keywords' : { '$not' : { '$eq' : None } } } ] },
}


@app.route("/keyword/<kw>")
@app.route("/search/<word>")
@app.route("/search")
@app.route("/")
def main(word = '', kw = ''):
    total_indexed = db.packages.find().count()
    limit = get_int('limit', 20)
    page = get_int('page', 1)
    query = {}
    q = request.args.get('q', '')
    license = request.args.get('license', '')

    word = word.replace('-', '_')
    if (word in cases):
        query = cases[word]
        q = ''

    if kw:
        import re
        regx = re.compile(kw)
        query = { 'keywords' : regx}
        q = ''

    if q != '':
        query['name'] = { '$regex' : q, '$options' : 'i'}

    if license != '':
        query['license'] = license
        if license == 'None':
            query['license'] = None


    data = db.packages.find(query).sort([("pubDate", pymongo.DESCENDING)]).skip(limit * (page-1)).limit(limit)
#    total_found = db.packages.find(query).count()
    total_found = data.count(with_limit_and_skip=False)
    count = data.count(with_limit_and_skip=True)

    return render_template('main.html',
        title = "PyDigger - unearthing stuff about Python",
        page = {
            'total_indexed' : total_indexed,
            'total_found' : total_found,
            'count' : count,
            'pages' : int(math.ceil(total_found / limit)),
            'current' : page,
            'limit' : limit,
        },
        data = data,
        search = {
            'q' : q,
         },
    )

@app.route("/stats")
def stats():
    stats = {
        'total'        : db.packages.find().count(),
    }
    for word in cases:
        stats[word] = db.packages.find(cases[word]).count()

    #github_not_exists = db.packages.find({ 'github' : { '$not' : { '$exists': True }}}).count()

    #licenses = db.packages.group({ key: {license : 1}, reduce: function (curr, result) { result.count++; }, initial: { count : 0} });
    licenses = db.packages.group(['license'], {}, { 'count' : 0}, 'function (curr, result) { result.count++; }' );
    for l in licenses:
        l['count'] = int(l['count'])

    return render_template('stats.html',
        title = "PyDigger - Statistics",
        stats = stats,
        licenses = licenses,
    )



@app.route("/pypi/<name>")
def pypi(name):
    package = db.packages.find_one({'name' : name})
    if not package:
        return render_template('404.html',
            title = name + " not found",
            package_name = name), 404
    # if 'keywords' in package and package['keywords']:
    #     package['keywords'] = package['keywords'].split(' ')
    # else:
    #     package['keywords'] = []

    return render_template('package.html',
        title = name,
        package = package,
        raw = json.dumps(package, indent=4, default = json_converter)
    )

@app.route("/robots.txt")
def robots():
    return ''


@app.route("/about")
def about():
    return render_template('about.html',
        title = "About PyDigger"
    )

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

def json_converter(o):
    if isinstance(o, datetime.datetime):
        return o.__str__()
