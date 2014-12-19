#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging
import sys

from flask import Flask

app = Flask(__name__)

# configure log
app.logger.setLevel(logging.INFO)
app.logger.addHandler(logging.StreamHandler(sys.stdout))

from ph_slack import phabricator
from ph_slack import slack
from ph_slack import web


__all__ = [
    'app',
    'phabricator',
    'slack',
    'web',
]
