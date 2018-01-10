# -*- coding: utf-8 -*-

# Copyright (c) 2018 shmilee

import os
import unittest
import tempfile

from ..base import BasePlotter


class ImpBasePlotter(BasePlotter):
    style_available = ['s1', 's2', 's99', 'gdpy3-test']

    def __init__(self, name):
        super(ImpBasePlotter, self).__init__(
            name, style=['s99'], example_axes='{d,l,s}')

    def _check_style(self, sty):
        return sty in self.style_available

    def _filter_style(self, sty):
        return '/path/%s.style' % sty

    def _param_from_style(self, param):
        return 'param-%s' % param

    def _add_axes(self, fig, data, layout, axstyle):
        fig['datalist'].append(data)
        fig['layoutlist'].append(layout)
        fig['axstylelist'].append(axstyle)

    def _create_figure(self, num, axesstructures, figstyle):
        # fake figure object: dict
        fig = {'num': num, 'figstyle': figstyle,
               'datalist': [], 'layoutlist': [], 'axstylelist': []}
        for axstructure in axesstructures:
            self.add_axes(fig, axstructure)
        return fig

    def _show_figure(self, fig):
        return fig['num']

    def _close_figure(self, fig):
        pass

    def _save_figure(self, fig, fpath, **kwargs):
        with open(fpath, 'w') as f:
            f.write(fig['num'])


class TestBasePlotter(unittest.TestCase):
    '''
    Test class BasePlotter
    '''

    def setUp(self):
        self.tmpfile = tempfile.mktemp(suffix='-test')
        self.ImpBasePlotter = ImpBasePlotter
        self.plotter = ImpBasePlotter('test-plotter')

    def tearDown(self):
        if os.path.isfile(self.tmpfile):
            os.remove(self.tmpfile)

    def test_plotter_init(self):
        self.assertEqual(self.plotter.name, 'test-plotter')
        self.assertListEqual(self.plotter.style, ['s99'])
        self.assertEqual(self.plotter.example_axes, '{d,l,s}')
        self.assertListEqual(self.plotter.figures, [])

    def test_plotter_style(self):
        style = self.plotter.style
        self.plotter.style = ['s1']
        self.assertListEqual(self.plotter.style, ['s1'])
        self.plotter.style = ['s99']

    def test_plotter_check_style(self):
        self.assertListEqual(
            self.plotter.check_style(['s1', 's10', 's99', 's100']),
            ['s1', 's99'])

    def test_plotter_filter_style(self):
        self.assertListEqual(
            self.plotter.filter_style(['s1', 's10', 'gdpy3-test']),
            ['s1', 's10', '/path/gdpy3-test.style'])

    def test_plotter_param_from_style(self):
        self.assertEqual(self.plotter.param_from_style('tp'), 'param-tp')

    def test_plotter_add_axes(self):
        fig = {'datalist': [], 'layoutlist': [], 'axstylelist': []}
        self.plotter.add_axes(
            fig, dict(data=['data1'], layout=[1, 'layout1'], axstyle=['s1']))
        self.plotter.add_axes(
            fig, dict(data=['data2'], layout=[2, 'layout2'], axstyle=['s9']))
        self.assertListEqual(fig['datalist'], [['data1'], ['data2']])
        self.assertListEqual(fig['layoutlist'],
                             [[1, 'layout1'], [2, 'layout2']])
        self.assertListEqual(fig['axstylelist'], [['s1'], []])

    def test_plotter_create_figure(self):
        fig = self.plotter.create_figure(
            'test-f1',
            dict(data=['data1'], layout=[1, 'layout1'], axstyle=['s1']),
            dict(data=['data2'], layout=[2, 'layout2'], axstyle=['s2']),
            add_style=['gdpy3-test'])
        self.assertEqual(fig['num'], 'test-f1')
        self.assertListEqual(fig['figstyle'], ['s99', 'gdpy3-test'])
        self.assertListEqual(fig['datalist'], [['data1'], ['data2']])
        self.assertListEqual(fig['layoutlist'],
                             [[1, 'layout1'], [2, 'layout2']])
        self.assertListEqual(fig['axstylelist'], [['s1'], ['s2']])

    def test_plotter_get_show_save_figure(self):
        self.plotter.create_figure('test-f2')
        self.assertTrue(isinstance(self.plotter.get_figure('test-f2'), dict))
        self.assertEqual(self.plotter.show_figure('test-f2'), 'test-f2')
        self.plotter.save_figure('test-f2', self.tmpfile)
        with open(self.tmpfile, 'r') as f:
            self.assertEqual(f.read(), 'test-f2')