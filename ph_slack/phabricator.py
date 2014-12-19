#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re
import itertools

import phabricator


class PhabricatorObject(object):

    def __init__(self, phabricator, phid):
        self.phabricator = phabricator
        self.phid = phid
        self.synced = False
        self._id = None
        self._url = None
        self.init()

    def sync(self):
        if self.synced:
            return False
        datadict = self.query_data_by_phids(self.phabricator, self.phid)
        data = datadict.get(self.phid)
        if data:
            self._fill_data(data)
            r = True
        r = False
        self.synced = True
        return r

    @classmethod
    def batch_sync(cls, phabricator, instances):
        not_synced = [i for i in instances if not i.synced]
        phid_map = dict([(i.phid, i) for i in not_synced])
        datadict = cls.query_data_by_phids(phabricator, phid_map.keys())
        for phid, data in datadict.iteritems():
            phid_map[phid]._fill_data(data)
            phid_map[phid].synced = True

    def _fill_data(self, data):
        raise NotImplementedError()

    @classmethod
    def query_by_phids(cls, phabricator, *phids):
        result = dict((phid, None) for phid in phids)
        datadict = cls.query_data_by_phids(phabricator, *phids)
        for phid, data in datadict.iteritems():
            instance = cls(phabricator, phid)
            instance._fill_data(data)
            instance.synced = True
        return result

    @classmethod
    def query_data_by_phids(cls, phabricator, *phids):
        raise NotImplementedError()

    @property
    def id(self):
        return self._id

    @property
    def url(self):
        return self._url


class Subscriable(PhabricatorObject):

    def __init__(self, phabricator, phid):
        super(Subscriable, self).__init__(phabricator, phid)
        self._subscribers = []

    @property
    def subscribers(self):
        not_synced = [s for s in self._subscribers if not s.synced]
        for k, g in itertools.groupby(not_synced, key=lambda s: type(s)):
            k.batch_sync(self.phabricator, g)
        return self._subscribers

    @subscribers.setter
    def subscribers(self, subscribers):
        self._subscribers = subscribers


class Task(Subscriable):

    @classmethod
    def query_data_by_phids(cls, phabricator, *phids):
        result = dict((phid, None) for phid in phids)
        r = phabricator.client.maniphest.query(phids=phids)
        if r.response:
            result.update(dict(r))
        return result

    def _fill_data(self, data):
        self._id = data['id']
        self._url = data['uri']
        cc_phids = data['ccPHIDs']
        cc_objs = [
            self.phabricator.get_object_type_by_phid(phid)
            for phid in cc_phids
        ]
        self.subscribers = cc_objs


class Revision(Subscriable):
    pass


class Project(PhabricatorObject):
    pass


class User(PhabricatorObject):
    pass


class Phabricator(object):

    _OBJ_TYPE_MAPPING = {
        'TASK': Task,
        'DREV': Revision,
    }

    def __init__(self, host=None, username=None, cert=None):
        client = phabricator.Phabricator()
        if host is not None:
            client.host = host
        if username is not None:
            client.username = username
        if cert is not None:
            client.certificate = cert

    def get_object_type_by_phid(self, phid):
        type_ = self._recognize_phid_type(phid)
        return self._OBJ_TYPE_MAPPING[type_]

    def get_object_by_phid(self, phid):
        return self.get_object_type_by_phid(phid)(self, phid)

    def _recognize_phid_type(phid):
        if phid is None:
            return None

        matches = re.match(r'^PHID-(\w+)-\w+$', phid)
        if matches:
            return matches.group(1)
