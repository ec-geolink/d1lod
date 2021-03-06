"""
For testing purposes: Process a specific page on the Solr index.
"""

import os
import sys
import datetime
import json
import uuid
import pandas
import xml.etree.ElementTree as ET
import urllib

# Append parent dir so we can keep these scripts in /scripts
sys.path.insert(1, os.path.join(sys.path[0], '../'))

from d1lod import settings
from d1lod import dataone
from d1lod import util
from d1lod import validator
from d1lod import store
from d1lod import multi_store

from d1lod.people import processing

from d1lod.people.formats import eml
from d1lod.people.formats import dryad
from d1lod.people.formats import fgdc


if __name__ == "__main__":
    # query = "https://cn.dataone.org/cn/v1/query/solr/?fl=author,identifier,title,authoritativeMN&q=author:*Jones*Matthew*&rows=1000&start=0"
    # query = "https://cn.dataone.org/cn/v1/query/solr/?fl=author,identifier,title,authoritativeMN&q=author:*Jones*&rows=20&start=0"
    query = "https://cn.dataone.org/cn/v1/query/solr/?fl=author,identifier,title,authoritativeMN&q=author:Jeremy*Jones*&rows=20&start=0"

    cache_dir = "/Users/mecum/src/d1dump/documents/"
    formats_map = util.loadFormatsMap()

    namespaces = {
        "foaf": "http://xmlns.com/foaf/0.1/",
        "dcterms": "http://purl.org/dc/terms/",
        "datacite": "http://purl.org/spar/datacite/",
        "owl": "http://www.w3.org/2002/07/owl#",
        "xsd": "http://www.w3.org/2001/XMLSchema#",
        "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
        "rdf": "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
        "glview": "http://schema.geolink.org/dev/view/",
        "d1people": "https://dataone.org/person/",
        "d1org": "https://dataone.org/organization/",
        "d1resolve": "https://cn.dataone.org/cn/v1/resolve/",
        "prov": "http://www.w3.org/ns/prov#",
        "d1node": "https://cn.dataone.org/cn/v1/node/",
        "d1landing": "https://search.dataone.org/#view/",
        "d1repo": "https://cn.dataone.org/cn/v1/node/"
    }

    # Load triple stores
    stores = {
        'people': store.Store("http://virtuoso/", "8890", 'geolink', namespaces),
        'organizations': store.Store("http://virtuoso/",  "8890", 'geolink', namespaces),
        'datasets': store.Store("http://virtuoso/", "8890", 'geolink', namespaces)
    }

    for store_name in stores:
        stores[store_name].delete_all()

    stores = multi_store.MultiStore(stores, namespaces)
    vld = validator.Validator()

    page_xml = util.getXML(query)
    documents = page_xml.findall(".//doc")

    for doc in documents:
        identifier = doc.find(".//str[@name='identifier']").text

        print identifier

        scimeta = dataone.getScientificMetadata(identifier, cache=True)

        if scimeta is None:
            continue

        records = processing.extractCreators(identifier, scimeta)

        # Add records and organizations
        people = [p for p in records if 'type' in p and p['type'] == 'person']
        organizations = [o for o in records if 'type' in o and o['type'] == 'organization']

        # Always do organizations first, so peoples' organization URIs exist
        for organization in organizations:
            organization = vld.validate(organization)
            stores.addOrganization(organization)

        for person in people:
            person = vld.validate(person)
            stores.addPerson(person)

        stores.addDataset(doc, scimeta, formats_map)

    stores.save()
