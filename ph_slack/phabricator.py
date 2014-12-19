#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import

import re

import phabricator


class PhabricatorObject(object):

    def __init__(self, phabricator, phid):
        self.phabricator = phabricator
        self.phid = phid
        self.synced = False
        self._id = None
        self._url = None
        self.init()

    def init(self):
        pass

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
        datadict = cls.query_data_by_phids(phabricator, *phid_map.keys())
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
        self.sync()
        return self._id

    @property
    def url(self):
        self.sync()
        return self._url

    def __repr__(self):
        return '<%r phid=%r, id=%r>' % (self.__class__, self.phid, self.id)

    def __eq__(self, other):
        return (
            self.__class__ == other.__class__
            and self.phid == other.phid
        )

    def __ne__(self, other):
        return not self.__eq__(other)

    def __hash__(self):
        return hash(self.__class__) ^ hash(self.phid)


class Subscriable(PhabricatorObject):

    def __init__(self, phabricator, phid):
        super(Subscriable, self).__init__(phabricator, phid)
        self._cc_objs = []
        self._subscribers = set()

    @property
    def subscribers(self):
        # sync projects first
        to_sync_projects = [
            obj for obj in self.cc_objs if isinstance(obj, Project)
        ]
        Project.batch_sync(self.phabricator, to_sync_projects)

        users = []
        for obj in self.cc_objs:
            if isinstance(obj, User):
                users.append(obj)
            elif isinstance(obj, Project):
                users.extend(obj.members)

        self._subscribers = set(users)
        User.batch_sync(self.phabricator, self._subscribers)
        return self._subscribers

    @property
    def cc_objs(self):
        self.sync()
        return self._cc_objs

    @cc_objs.setter
    def cc_objs(self, cc_objs):
        self._cc_objs = cc_objs


class Task(Subscriable):

    @classmethod
    def query_data_by_phids(cls, phabricator, *phids):
        if not phids:
            return {}
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
            self.phabricator.get_object_by_phid(phid)
            for phid in cc_phids
        ]
        self.cc_objs = cc_objs


class Revision(Subscriable):

    @classmethod
    def query_data_by_phids(cls, phabricator, *phids):
        if not phids:
            return {}
        result = dict((phid, None) for phid in phids)
        r = phabricator.client.differential.query(phids=phids)
        if r.response:
            r = dict([(d['phid'], d) for d in r.response])
            result.update(r)
        return result

    def _fill_data(self, data):
        self._id = data['id']
        self._url = data['uri']
        cc_phids = data['reviewers'] + data['ccs']
        cc_objs = [
            self.phabricator.get_object_by_phid(phid)
            for phid in cc_phids
        ]
        self.cc_objs = cc_objs


class Project(PhabricatorObject):

    def init(self):
        self._members = []

    @classmethod
    def query_data_by_phids(cls, phabricator, *phids):
        if not phids:
            return {}
        result = dict((phid, None) for phid in phids)
        r = phabricator.client.project.query(phids=phids)['data']
        if r:
            result.update(r)
        return result

    @property
    def members(self):
        self.sync()
        User.batch_sync(self.phabricator, self._members)
        return self._members

    def _fill_data(self, data):
        self._id = data['id']
        member_phids = data['members']
        members = [
            self.phabricator.get_object_by_phid(phid)
            for phid in member_phids
        ]
        self._members = members


class User(PhabricatorObject):

    def init(self):
        self._username = None
        self._realname = None

    @classmethod
    def query_data_by_phids(cls, phabricator, *phids):
        if not phids:
            return {}
        result = dict([(phid, None) for phid in phids])
        r = phabricator.client.user.query(phids=phids)
        if r.response:
            r = dict([(m['phid'], m) for m in r.response])
            result.update(r)
        return result

    def _fill_data(self, data):
        self._id = data['userName']
        self._username = data['userName']
        self._realname = data['realName']

    @property
    def username(self):
        self.sync()
        return self._username

    @property
    def realname(self):
        self.sync()
        return self._realname


class Phabricator(object):

    _OBJ_TYPE_MAPPING = {
        'TASK': Task,
        'DREV': Revision,
        'USER': User,
        'PROJ': Project,
    }

    def __init__(self, host=None, username=None, cert=None):
        self.client = phabricator.Phabricator()
        if host is not None:
            self.client.host = host
        if username is not None:
            self.client.username = username
        if cert is not None:
            self.client.certificate = cert

    def get_object_type_by_phid(self, phid):
        type_ = self._recognize_phid_type(phid)
        r = self._OBJ_TYPE_MAPPING.get(type_) or PhabricatorObject
        return r

    def get_object_by_phid(self, phid):
        return self.get_object_type_by_phid(phid)(self, phid)

    def _recognize_phid_type(self, phid):
        if phid is None:
            return None

        matches = re.match(r'^PHID-(\w+)-\w+$', phid)
        if matches:
            return matches.group(1)
