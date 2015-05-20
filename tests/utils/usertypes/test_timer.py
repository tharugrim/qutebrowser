# vim: ft=python fileencoding=utf-8 sts=4 sw=4 et:

# Copyright 2015 Florian Bruhin (The Compiler) <mail@qutebrowser.org>
#
# This file is part of qutebrowser.
#
# qutebrowser is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# qutebrowser is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with qutebrowser.  If not, see <http://www.gnu.org/licenses/>.

"""Tests for Timer."""

from qutebrowser.utils import usertypes

import pytest
from PyQt5.QtCore import QObject


class Parent(QObject):

    pass


def test_parent():
    parent = Parent()
    t = usertypes.Timer(parent)
    assert t.parent() is parent


def test_named():
    t = usertypes.Timer(name='foobar')
    assert t._name == 'foobar'
    assert t.objectName() == 'foobar'
    assert repr(t) == "<qutebrowser.utils.usertypes.Timer name='foobar'>"


def test_unnamed():
    t = usertypes.Timer()
    assert not t.objectName()
    assert t._name == 'unnamed'
    assert repr(t) == "<qutebrowser.utils.usertypes.Timer name='unnamed'>"


def test_setInterval_overflow():
    t = usertypes.Timer()
    with pytest.raises(OverflowError):
        t.setInterval(2 ** 64)


def test_start_overflow():
    t = usertypes.Timer()
    with pytest.raises(OverflowError):
        t.start(2 ** 64)


def test_timeout_start(qtbot):
    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout):
        t.start(200)


def test_timeout_setInterval(qtbot):
    t = usertypes.Timer()
    with qtbot.waitSignal(t.timeout):
        t.setInterval(200)
        t.start()