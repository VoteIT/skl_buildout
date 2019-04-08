# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from unittest import TestCase

from colander import Invalid
from pyramid import testing
from pyramid.request import apply_request_extensions
from voteit.core.models.meeting import Meeting
from voteit.core.testing_helpers import bootstrap_and_fixture

from skl_owner_groups.interfaces import GROUPS_NAME


_TYPICAL_ASSIGNMENT_TXT = """
hej@email.com\ta Blabla
kalas@email.com\tb Hejhej
"""


class CSVTextValidatorTests(TestCase):

    def setUp(self):
        self.config = testing.setUp()

    def tearDown(self):
        testing.tearDown()

    def _fixture(self):
        root = bootstrap_and_fixture(self.config)
        self.config.include('skl_owner_groups.resources')
        request = testing.DummyRequest()
        apply_request_extensions(request)
        self.config.begin(request)
        request.root = root
        # root.users['adam']
        root['m'] = meeting = Meeting()
        groups = meeting[GROUPS_NAME] = request.content_factories['VGroups']()
        gfact = request.content_factories['VGroup']
        groups['a'] = gfact(title='A')
        groups['b'] = gfact(title='B')
        groups['c'] = gfact(title='C')
        return groups, request

    @property
    def _cut(self):
        from skl_owner_groups.schemas import CSVTextValidator
        return CSVTextValidator

    def _mk_validator(self):
        groups, request = self._fixture()
        # Node is not important here, so it's okay that it's None. The dict is the bound data
        return self._cut(None, {'context': groups})

    def test_typical_assignment(self):
        validator = self._mk_validator()
        self.assertIsNone(validator(None, _TYPICAL_ASSIGNMENT_TXT))

    def test_bad_group_name(self):
        validator = self._mk_validator()
        txt = _TYPICAL_ASSIGNMENT_TXT + "annan@email.com\t404 Hejhej"
        self.assertRaises(Invalid, validator, None, txt)

    def test_bad_email(self):
        validator = self._mk_validator()
        txt = _TYPICAL_ASSIGNMENT_TXT + "kallespostat.com\tc bka"
        self.assertRaises(Invalid, validator, None, txt)

    def test_tab_missing(self):
        validator = self._mk_validator()
        txt = _TYPICAL_ASSIGNMENT_TXT + "annan@email.com c Hej"
        self.assertRaises(Invalid, validator, None, txt)

    def test_more_tabs(self):
        validator = self._mk_validator()
        txt = _TYPICAL_ASSIGNMENT_TXT + "annan@email.com\tc\tHej"
        self.assertRaises(Invalid, validator, None, txt)

    def test_error_row_num(self):
        validator = self._mk_validator()
        txt = _TYPICAL_ASSIGNMENT_TXT + "xxxx"
        try:
            validator(None, txt)
            self.fail("Invalid not raised")
        except Invalid as exc:
            self.assertEqual("Rad 4 verkar inte innehålla något tabtecken", exc.msg)

    def test_double_entry(self):
        validator = self._mk_validator()
        txt = _TYPICAL_ASSIGNMENT_TXT + "annan@email.com\ta Hejhej"
        self.assertRaises(Invalid, validator, None, txt)
