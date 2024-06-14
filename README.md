# PyDigger

[![GitHub stars](https://img.shields.io/github/stars/szabgab/pydigger.com.svg)](https://github.com/szabgab/pydigger.com/stargazers) [![GitHub forks](https://img.shields.io/github/forks/szabgab/pydigger.com.svg)](https://github.com/szabgab/pydigger.com/network/members) [![GitHub watchers](https://img.shields.io/github/watchers/szabgab/pydigger.com.svg)](https://github.com/szabgab/pydigger.com/watchers) [![GitHub commits](https://img.shields.io/github/commit-activity/m/szabgab/pydigger.com.svg)](https://github.com/szabgab/pydigger.com/commits)

Source code of [PyDigger](https://pydigger.com/)

See the [about page](https://pydigger.com/about) on the web site for some explanation.

See the [Video recording series](https://code-maven.com/pydigger) following the development of the application.
Specifically in the first episode you can see an explanation about it.

## Setup a development environment

* Clone the repository. `git clone https://github.com/szabgab/pydigger.com`
* [Install Docker](https://docs.docker.com/get-docker/).
* [Install docker-compose](https://docs.docker.com/compose/install/).
* Copy `config-skeleton.yml` to `dev.yml`.
* Sign up to [GitHub](https://github.com/)
* Create a [Personal access token](https://github.com/settings/tokens) with a name that you can easily recognize, e.g. "PyDigger Development Token" using the following rights:

```
repo
   x public_repo

user
   x read:user
   x user:email
```
* Save the token it in the `dev.yml` file in the `github-token` field.
* Copy `docker-compose.override.yml.example` to `docker-compose.override.yml` and personalize it if necessary.

If you're using Windows, make sure to have a docker daemon up and running, e.g. via Docker Desktop.

Open a terminal and run the following from within your cloned pydigger.com directory:
```
docker-compose up --build
```

Visit the web page at http://localhost:6001 At this point the database is empty.

### In another terminal connect to the shell of the Docker container

You can use either docker name or container ID:
```
docker exec -it pydiggercom-cron-1 bash
```

To run the tests type in

```
pytest --cache-clear -vs
```

To run the linter type in
```
flake8 --count --show-source --statistics
```

To collect data from a single GitHub repository:

```
python fetch_recent.py --update url --url https://github.com/szabgab/pydigger.com --log DEBUG --screen
```

To collect data for a single PyPI package:

```
python fetch_recent.py --update package --package <PyPI package name> --log DEBUG --screen
```

For example:

```
python fetch_recent.py --update package --package flask --log DEBUG --screen
```

Fetch data of recently uploaded packages using the RSS feed of PyPI:

```
python fetch_recent.py --update rss --screen --log DEBUG
python fetch_recent.py --update deps --screen --log DEBUG
```

### Connect to the shell of the MongoDB server

```
$ docker exec -it pydiggercom_mymongo_1 bash
# mongo -u root -p Secret # to login to mongodb
> use pydigger # pydigger is our database name
> db.dropDatabase() # To drop the pydigger database
> db.packages.find() # To list all the entries
```

Cleaning up database (during development)

```
docker exec pydiggercom_web_1 python remove_db.py
```

Remove a package

```
docker exec pydiggercom_web_1 python remove_package.py NAME
```


## Deployment

ssh to the server and run

```
./deploy.sh
```

Copyright and LICENSE
======================

Copyright 2023 Gábor Szabó

The source code in this repository is licensed under the MIT License.

The content of the site as collected from the various sources
are copyright the respective parties.

## Contributors

* Upasana Shukla
* Ed Sabol
* Greg Lawrance

