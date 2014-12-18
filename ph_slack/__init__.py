#!/usr/bin/env python
# -*- coding: utf-8 -*-


import logging
import os
import re
import sys
import time

from flask import Flask, request, abort
from phabricator import Phabricator
from slacker import Slacker


app = Flask(__name__)
app.config.from_object('ph_slack.settings.Default')
app.config.from_pyfile(
    os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'config.py')
    )
)

slack = Slacker(app.config['SLACK_AUTH_TOKEN'])


phabricator = Phabricator()
if 'PHABRICATOR_HOST' in app.config:
    phabricator.host = app.config['PHABRICATOR_HOST']
if 'PHABRICATOR_USER' in app.config:
    phabricator.username = app.config['PHABRICATOR_USER']
if 'PHABRICATOR_CERT' in app.config:
    phabricator.certificate = app.config['PHABRICATOR_CERT']


def recognize_ph_object_type(object_phid):
    if object_phid is None:
        return None

    matches = re.match(r'^PHID-(\w+)-\w+$', object_phid)
    if matches:
        return matches.group(1)


def get_noti_ph_users_by_obj(object_phid):
    result = []
    obj_type = recognize_ph_object_type(object_phid)
    if obj_type == 'TASK':
        tasks = phabricator.maniphest.query(phids=[object_phid])
        if tasks.response:
            for task in tasks.itervalues():
                result.extend(parse_task_cc_user_phids(task))
    elif obj_type == 'DREV':
        diffs = phabricator.differential.query(phids=[object_phid])
        if diffs.response:
            for diff in diffs:
                result.extend(parse_diff_cc_user_phids(diff))
    else:
        app.logger.info('Unsupported object: %s.', object_phid)

    return set(result)


def parse_task_cc_user_phids(task):
    result = []
    for ccphid in task.get('ccPHIDs', []):
        cctype = recognize_ph_object_type(ccphid)
        if cctype == 'USER':
            result.append(ccphid)
        elif cctype == 'PROJ':
            result.extend(get_ph_projects_user_phids(ccphid))
        else:
            app.logger.warn('Unrecognized ccphid: %s', ccphid)
    return result


def get_ph_projects_user_phids(*project_phids):
    result = []
    if not project_phids:
        return result

    projects = phabricator.project.query(phids=project_phids)['data']
    for project in projects.itervalues():
        user_phids = project.get('members', [])
        result.extend(user_phids)
    return result


def get_ph_user_emails(user_phids):
    if not user_phids:
        return []
    users = phabricator.user.query(phids=list(user_phids))
    return [
        '%s@%s' % (user['userName'], app.config['EMAIL_DOMAIN'])
        for user in users
    ]


def parse_diff_cc_user_phids(diff):
    result = []
    ccphids = diff.get('reviewers', []) + diff.get('ccs', [])
    for ccphid in ccphids:
        cctype = recognize_ph_object_type(ccphid)
        if cctype == 'USER':
            result.append(ccphid)
        elif cctype == 'PROJECT':
            pass
        else:
            app.logger.warn('Unrecognized ccphid: %s', ccphid)
    return result


SLACK_USER_EMAIL_MAP = {
    "last_update": 0,
    "map": {}
}


def refresh_slack_email_map():
    members = slack.users.list().body['members']
    SLACK_USER_EMAIL_MAP['map'] = dict(
        [
            (member['profile']['email'], member['name'])
            for member in members
        ]
    )


def get_disabled_slack_users():
    if not os.path.exists(app.config['SLACK_DISABLED_USERS_FILE']):
        return []
    with open(app.config['SLACK_DISABLED_USERS_FILE'], 'r') as disabled_users_file:
        return [line.strip() for line in disabled_users_file.readlines() if line.strip()]


@app.route('/handle', methods=['POST'])
def handle():
    story_id = request.form.get('storyID')
    object_phid = request.form.get('storyData[objectPHID]')
    story_text = request.form.get('storyText')
    app.logger.info('Got story #%s on #%s: %s', story_id, object_phid, story_text)

    # Refresh member email mapping
    now = time.time()
    if now - SLACK_USER_EMAIL_MAP['last_update'] >= app.config['SLACK_EMAIL_REFRESH_INTEVAL']:
        app.logger.info('Refreshing slack members.')
        refresh_slack_email_map()
        SLACK_USER_EMAIL_MAP['last_update'] = now

    if object_phid is None:
        app.logger.info('Unsupported story: %s', repr(request.form))
        return 'Unsupported'

    noti_user_phids = get_noti_ph_users_by_obj(object_phid)
    noti_user_mails = get_ph_user_emails(noti_user_phids)
    disabled_users = get_disabled_slack_users()
    slack_usernames = []
    for mail in noti_user_mails:
        slack_name = SLACK_USER_EMAIL_MAP['map'].get(mail)
        if slack_name is not None and slack_name not in disabled_users:
            slack_usernames.append(slack_name)
            # post message
            params = dict(
                channel='@%s' % slack_name,
                text=story_text,
                username=app.config['SLACK_BOT_NAME'],
            )
            if 'SLACK_BOT_ICON' in app.config:
                params['icon_url'] = app.config['SLACK_BOT_ICON']
            slack.chat.post_message(**params)
        else:
            app.logger.info('%s is not in slack members.', mail)
    if slack_usernames:
        app.logger.info('Message: \n\t %s \n has been send to %r', story_text, slack_usernames)
    return "Message: \n\t %s \n has been send to %r." % (story_text, slack_usernames)


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

    disabled_users = get_disabled_slack_users()
    if action == 'enable':
        if username in disabled_users:
            with open(app.config['SLACK_DISABLED_USERS_FILE'], 'w+') as f:
                for name in disabled_users:
                    if name != username:
                        f.write(name + '\n')
    elif action == 'disable':
        if username not in disabled_users:
            with open(app.config['SLACK_DISABLED_USERS_FILE'], 'a+') as f:
                f.write(username + '\n')
    else:
        abort(401)

    return 'OK.'


def main():
    app.logger.setLevel(logging.INFO)
    app.logger.addHandler(logging.StreamHandler(sys.stdout))
    app.run(host='0.0.0.0')


if __name__ == '__main__':
    main()
