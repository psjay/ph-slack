#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import time

from flask import request, abort

from ph_slack.phabricator import Phabricator, Subscriable
from ph_slack.slack import Slack
from ph_slack import app


# load settings
app.config.from_object('ph_slack.settings.Default')
app.config.from_pyfile(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'config.py')
    )
)

slack = Slack(
    auth_token=app.config['SLACK_AUTH_TOKEN'],
    disable_list_file=app.config['SLACK_DISABLED_USERS_FILE'],
    username=app.config['SLACK_BOT_NAME'],
    avatar=app.config.get('SLACK_BOT_ICON'),
)


phabricator = Phabricator(
    host=app.config.get('PHABRICATOR_HOST'),
    username=app.config.get('PHABRICATOR_USER'),
    cert=app.config.get('PHABRICATOR_CERT'),
)


@app.route('/handle', methods=['POST'])
def handle():
    author_phid = request.form.get('storyAuthorPHID')
    story_id = request.form.get('storyID')
    object_phid = request.form.get('storyData[objectPHID]')
    story_text = request.form.get('storyText')
    app.logger.info('Got story #%s on #%s: %s', story_id, object_phid, story_text)

    # Refresh member email mapping
    now = time.time()
    if now - slack.email_name_map_updated >= app.config['SLACK_EMAIL_REFRESH_INTEVAL']:
        app.logger.info('Refreshing slack members.')
        slack.refresh_email_name_map()

    if object_phid is None:
        resp = 'Unsupported story: %r' % request.form
        app.logger.info(resp)
        return resp

    ph_obj = phabricator.get_object_by_phid(object_phid)
    if not isinstance(ph_obj, Subscriable):
        resp = "Unsupported object: %s" % object_phid
        app.logger.info(resp)
        return resp

    subscribers = [s for s in ph_obj.subscribers if s.phid != author_phid]
    emails = [
        '%s@%s' % (s.username, app.config['EMAIL_DOMAIN'])
        for s in subscribers
    ]
    slack.post_msg_to_users(story_text, emails=emails)
    return 'success'


@app.route('/switch', methods=['POST'])
def switch():
    username = request.form.get('user_name')
    token = request.form.get('token')
    action = request.form.get('text')
    if not action or action not in ['disable', 'enable']:
        action = 'enable'
    action = action.strip()

    if token != app.config['SLACK_COMMAND_TOKEN']:
        abort(403)

    if action == 'enable':
        slack.enable(username)
    elif action == 'disable':
        slack.disable(username)
    else:
        abort(401)
    return '%s success.' % action


def main():
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    main()
