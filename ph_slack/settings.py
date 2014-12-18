#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os


class Default(object):

    SLACK_EMAIL_REFRESH_INTEVAL = 3600  # 1h
    SLACK_BOT_NAME = 'Phabricator'
    SLACK_DISABLED_USERS_FILE = os.path.abspath(
        os.path.join(os.path.dirname(__file__), '..', 'disabled_users.txt')
    )
