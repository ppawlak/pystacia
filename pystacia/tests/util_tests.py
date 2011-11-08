# coding: utf-8
# pystacia/tests/util_tests.py
# Copyright (C) 2011 by Paweł Piotr Przeradowski
#
# This module is part of Pystacia and is released under
# the MIT License: http://www.opensource.org/licenses/mit-license.php

from pystacia.tests import TestCase


class Util(TestCase):
    def test_memoized(self):
        class A(object):
            pass
        
        @memoized
        def producer(arg=None):
            """doc"""
            return A()
        
        self.assertEquals(producer(), producer())
        self.assertNotEqual(producer(), producer(1))
        self.assertEquals(producer.__name__, 'producer')
        self.assertEquals(producer.__doc__, 'doc')


from pystacia.util import memoized
