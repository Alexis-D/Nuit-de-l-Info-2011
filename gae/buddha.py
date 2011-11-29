#!/usr/bin/env python2
#-*- coding: utf-8 -*-

# TODO
# - templates
# - try catché les int()
# - checker bornes params (+ xmin != xmax ...)
# - img handler check finalized
# - var pour les defaults values
# - créer le bmp une fois pour toute et non pas à chaque fois qu'on demande /img
# - utiliser des namedtuples plutôt que des dicos...
# - doc

from collections import Counter

import logging
import os
import random

import jinja2

from google.appengine.ext import webapp
from google.appengine.ext.webapp.util import run_wsgi_app

import bmp
import pipeline

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

# ça c'est juste pour éviter d'avoir à être loggué
pipeline.set_enforce_auth(False)

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)))

class IndexHandler(webapp.RequestHandler):
    # GET
    def get(self):
        # Default values for budha
        config = {
            'width': 256,
            'height': 256,
            'red': 5,
            'green': 50,
            'blue': 500,
            'xmin': -2,
            'xmax': 1,
            'ymin': -1.5,
            'ymax': 1.5,
            'pointspermapper': 4096,
            'numberofmappers': 4, ###
        }
        # Get template with set values
        head_template = jinja_environment.get_template('head.html')
        budha_form_template = jinja_environment.get_template('BudhaGenerator.html')

        # Write responses
        self.response.out.write(head_template.render(title = "Buddhabrot Generator"))
        self.response.out.write(budha_form_template.render(config))

    # POST
    def post(self):
        # Store posted data
        config = {}
        config['width'] = int(self.request.get('width'))
        config['height'] = int(self.request.get('height'))

        config['red'] = int(self.request.get('red'))
        config['green'] = int(self.request.get('green'))
        config['blue'] = int(self.request.get('blue'))

        config['xmin'] = float(self.request.get('xmin'))
        config['xmax'] = float(self.request.get('xmax'))
        config['ymin'] = float(self.request.get('ymin'))
        config['ymax'] = float(self.request.get('ymax'))

        config['pointspermapper'] = int(self.request.get('pointspermapper'))
        config['numberofmappers'] = int(self.request.get('numberofmappers'))

        # c'est le pipeline qui va faire les calculs
        bp = BuddhaPipeline(config)
        bp.start()

        self.response.out.write('''
            <a href="/res?pid=%s">result</a>''' % bp.pipeline_id)
        self.response.out.write('''
            <a href="/_ah/pipeline/status?root=%s">status</a>''' % bp.pipeline_id)


# L'ideal serait de normaliser le nom de l'image generée
# utilisateur logué genere une image nomé : login_budha.bmp
# Script ajax cherchera l'image toute les x secondes et demande a l'utilisateur de bien vouloir attendre
class ResultHandler(webapp.RequestHandler):
    def get(self):
        # affiche :( si le calcul n'est pas fini, ou le résultat s'il est fini
        pid = self.request.get('pid')
        bp = BuddhaPipeline.from_id(pid)

        if bp.has_finalized:
            self.response.out.write('<img src=/img?pid=%s>' % pid)

        else:
            self.response.out.write(''':(''')


def minmax(c):
    mc = c.most_common()
    return mc[0][1], mc[-1][1]

class ImgHandler(webapp.RequestHandler):
    def get(self):
        pid = self.request.get('pid')
        bp = BuddhaPipeline.from_id(pid)
        config, r, g, b = bp.outputs.default.value

        w, h = config['width'], config['height']

        r = Counter(tuple(x) for x in r if x)
        g = Counter(tuple(x) for x in g if x)
        b = Counter(tuple(x) for x in b if x)

        ra, rb = minmax(r)
        ga, gb = minmax(g)
        ba, bb = minmax(b)

        self.response.headers['Content-Type'] = 'image/bmp'
        img = bmp.BitMap(w, h)

        for y in range(h):
            for x in range(w):
                rc = int(round(255.0 * (r[(x, y)] - ra) / (rb - ra)))
                gc = int(round(255.0 * (g[(x, y)] - ga) / (gb - ga)))
                bc = int(round(255.0 * (b[(x, y)] - ba) / (bb - ba)))
                img.setPenColor(bmp.Color(rc, gc, bc))
                img.plotPoint(x, y)

        self.response.out.write(img.getBitmap())


class Cpx2Px:
    def __init__(self, xmin, xmax, ymin, ymax, width, height):
        self.xmin = xmin
        self.ymax = ymax

        self.width = width
        self.height = height

        self.xratio = width / (xmax - xmin)
        self.yratio = height / (ymax - ymin)

    def __call__(self, p):
        x = int(round((p.real - self.xmin) * self.xratio))
        y = int(round((self.ymax - p.imag) * self.yratio))

        if x < 0 or x >= self.width or y < 0 or y >= self.height:
            return None

        return x, y

class PointGenerator(pipeline.Pipeline):
    def run(self, maxiter, config):
        points = []
        xmin, xmax = config['xmin'], config['xmax']
        ymin, ymax = config['ymin'], config['ymax']
        cpx2px = Cpx2Px(xmin, xmax, ymin, ymax, config['width'], config['height'])

        for _ in range(config['pointspermapper']):
            path = []
            in_set = False
            c = random.uniform(xmin, xmax) + 1j * random.uniform(xmin, xmax)
            z = c

            for _ in range(maxiter):
                z = z ** 2 + c
                path.append(z)

                if (z.real ** 2 + z.imag ** 2) > 4:
                    in_set = True
                    break

            if in_set:
                points.extend(cpx2px(z) for z in path)

        return points


class Result(pipeline.Pipeline):
    def run(self, *l):
        return l


class BuddhaPipeline(pipeline.Pipeline):
    def run(self, config):
        red = yield PointGenerator(config['red'], config)
        green = yield PointGenerator(config['green'], config)
        blue = yield PointGenerator(config['blue'], config)
        yield Result(config, red, green, blue)


app = webapp.WSGIApplication([
                                ('/', IndexHandler),
                                ('/res', ResultHandler),
                                ('/img', ImgHandler),
                             ], debug=True)

if __name__ == '__main__':
    run_wsgi_app(app)
