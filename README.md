# ph-slack

[Phabricator](http://phabricator.org/) notification [Slack](https://slack.com/) integration.
Instantly receive Phabricator notification in Slack.

## Features

* Instant:
* Customizable:
* Togglable:
 
## Usage

Your team members can receive Phabricator notification and can easily disable/enable it **in Slack** at anytime, like:

```
/your-slash-cmd [enable | disable]
```

## Deploy

In order to deploy ph-slack, you need to prepare these things:

* A Slack [API Authentication Token](https://api.slack.com/tokens).
* A Phabricator user (bot user is much better).
* The administation privileges of your Phabricator and Slack.
* An new [Slack slash command](https://slack.com/services/new/slash-commands).
* A server that can be accessed from Slack server. 

The last two things are optional if you don't want to your user to disable ph-slack.

Here we go.

First, clone code and build:

```bash
$ git clone git@github.com:psjay/ph-slack.git
$ cd ph-slack
$ python bootstrap.py
$ bin/buildout
```

You don't need a virtual environment with [Buildout](http://www.buildout.org).

Create a configuration file with sample:

```bash
$ cp config_sample.py config.py
```

Modify `config.py` like this:

```
PHABRICATOR_HOST = 'http://ph.your.domain/api/'

PHABRICATOR_USER = 'ph-bot-name'

PHABRICATOR_CERT = 'ph-bot-cert'

SLACK_AUTH_TOKEN = 'slack api token'

# optional
SLACK_COMMAND_TOKEN = 'slack slash command token'

EMAIL_DOMAIN = 'business-domain.com'
```

Full explanation of configuration, see `config_sample.py`.

Run the server on 5000 port  behind [Gunicorn](http://gunicorn.org/):

```bash
$ bin/gunicorn -w 4 -b 0.0.0.0:5000 'ph_slack:app' --log-file - --access-logfile -
```

Then, add `http://ph-slack.domain:5000/handle` to your Phabricator feed http hooks on `http://your-ph.domain/config/edit/feed.http-hooks/ ` page.

Configure `http://ph-slack.domain:5000/handle` as the URL of  the Slack slash command you just created for ph-slack.

Done!

## Limitations

By now, it only supports two kinds of Phabricator object:

* Task
* Revision

Pull request is welcome!
