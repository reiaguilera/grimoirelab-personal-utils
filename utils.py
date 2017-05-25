#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright (C) 2017 J. Manrique Lopez de la Fuente
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to
# deal in the Software without restriction, including without limitation the
# rights to use, copy, modify, merge, publish, distribute, sublicense, and/or
# sell copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
# FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
# IN THE SOFTWARE.
#
# Authors:
#     J. Manrique Lopez <jsmanrique@bitergia.com>
#

import os

from elasticsearch import Elasticsearch, helpers
from elasticsearch_dsl import Search

from genderize import Genderize

import csv
import yaml

from tqdm import tqdm

def read_config_file(filename):
    """ Function to read yaml file with settings information
    """

    with open(filename) as data_file:
    	config_data = yaml.load(data_file)

    return config_data

def establish_connection(es_host):
    """ Function to estabilish connection with a running Elasticsearch

    The functions create a Elasticsearch client
    """

    es = Elasticsearch([es_host])

    if not es.ping():
        raise ValueError('Connection refused')
    else:
        print('Connection established')
        return es

def genderize(genderize_api_key):
    """ Function to set up Genderize
    """

    genderize_obj = Genderize(user_agent='GenderizeCommunities/0.0', \
                            api_key=genderize_api_key)
    return genderize_obj

def load_names(names_file):
    """ Function to load cached names information
    """

    names_cache = {}

    if os.path.exists(names_file):
        with open(names_file) as csvfile:
            reader = csv.DictReader(csvfile)
            for row in tqdm(reader, ascii=True, desc='Names'):
                names_cache[row['name']] = {}
                names_cache[row['name']]['gender'] = row['gender']
                names_cache[row['name']]['gender_prob'] = row['probability']
                names_cache[row['name']]['gender_count'] = row['count']
    else:
        print('Creating ' + names_file)
        with open(names_file, 'w') as outcsv:
            writer = csv.DictWriter(outcsv, fieldnames = ['name', 'gender',\
                                    'probability', 'count'])
            writer.writeheader()

    return names_cache

def genderize_index(es, es_index, names_file, name_es_index_field, genderize):
    """ Function to add gender information for a given ES index and field
    """

    names = load_names(names_file)

    query = {"query": {"match_all" :{}}}

    docs = []

    for item in tqdm(helpers.scan(es, query, scroll='300m', index=es_index), \
                    ascii=True, desc='Gender info extracted'):

        full_name = item['_source'][name_es_index_field]

        first_name = full_name.split(' ')[0]

        if first_name not in names.keys():
            names[first_name] = {}
            gender_info = genderize.get([first_name])
            if gender_info[0]['gender'] == None:
                names[first_name]['gender'] = 'unknown'
                names[first_name]['gender_prob'] = 1
                names[first_name]['gender_count'] = 0
            else:
                names[first_name]['gender'] = gender_info[0]['gender']
                names[first_name]['gender_prob'] = gender_info[0]['probability']
                names[first_name]['gender_count'] = gender_info[0]['count']
            # Let's update names file with new names gender information
            with open(names_file, 'a') as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=['name', 'gender', \
                                        'probability', 'count'])
                writer.writerow({'name': first_name, 'gender': names[first_name]['gender'],\
                                'probability': names[first_name]['gender_prob'],\
                                'count': names[first_name]['gender_count']})
        docs.append({'_op_type': 'update', '_index': es_index, '_type': 'items',\
                    '_id':item['_id'], 'doc':names[first_name]})
    helpers.bulk(es, docs)
    print('Gender info updated')