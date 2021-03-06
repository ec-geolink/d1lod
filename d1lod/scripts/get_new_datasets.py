"""
    file: get_new_datasets.py
    author: Bryce Meucm

    Gets identifiers, system metadata, and science metadata from the DataOne CN
    which have been uploaded since the provided datetime.
"""

import os
import sys
import datetime
import json
import uuid
import pandas

# Append parent dir so we can keep these scripts in /scripts
sys.path.insert(1, os.path.join(sys.path[0], '../'))

from d1lod import settings
from d1lod import dataone
from d1lod import util
from d1lod import validator
from d1lod.graph import Graph
from d1lod import multi_store

from d1lod.people import processing


def main():
    # Settings
    config = util.loadJSONFile('settings.json')

    if 'last_run' not in config:
        print "Last run datetime not found in settings.json. Exiting."
        sys.exit()

    # Create from and to strings
    # from_string = config['last_run']
    # to_string = datetime.datetime.today().strftime("%Y-%m-%dT%H:%M:%S.0Z")
    from_string =   "2015-01-01T15:00:00.0Z"
    to_string   =   "2015-01-06T16:05:00.0Z"

    from_string = "2015-01-06T16:00:00.0Z"
    to_string = "2015-01-06T16:05:00.0Z"

    # from_string =   "2015-01-01T15:00:00.0Z"
    # to_string   =   "2015-01-06T16:05:00.0Z"

    from_string =   "2015-03-15T23:21:15.567Z"
    to_string   =   "2015-05-30T23:21:15.567Z"

    # Load scimeta cache
    cache_dir = "/Users/mecum/src/d1dump/documents/"
    identifier_map = util.createIdentifierMap("/Users/mecum/src/d1dump/idents.csv")
    print "Read in %d identifier mappings." % len(identifier_map)

    # Load formats map
    print "Loading formats map from GitHub..."
    formats_map = util.loadFormatsMap()
    print "Loaded %d format URIs from GitHub." % len(formats_map)

    # Load triple stores
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

    graph_dict = {
        'people': graph.Graph("http://virtuoso/","8890", 'geolink', namespaces),
        'organizations': graph.Graph("http://virtuoso/","8890", 'geolink', namespaces),
        'datasets': graph.Graph("http://virtuoso/", "8890", 'geolink', namespaces)
    }



    graphs = multi_store.MultiStore(graph_dict, namespaces)

    # Create a record validator
    vld = validator.Validator()

    query_string = dataone.createSinceQuery(from_string, to_string, None, 0)
    num_results = dataone.getNumResults(query_string)

    # Calculate the number of pages we need to get to get all results
    page_size=1000
    num_pages = num_results / page_size
    if num_results % page_size > 0:
        num_pages += 1

    # Establish which fields we want to get from the Solr index
    fields = ["identifier","title","abstract","author",
    "authorLastName", "origin","submitter","rightsHolder","documents",
    "resourceMap","authoritativeMN","obsoletes","northBoundCoord",
    "eastBoundCoord","southBoundCoord","westBoundCoord","startDate","endDate",
    "datasource","replicaMN","resourceMap"]

    print "Found %d documents over %d page(s)." % (num_results, num_pages)

    sys.exit()


    # Process each page
    for page in range(1, num_pages + 1):
        print "Processing page %d." % page

        page_xml = dataone.getSincePage(from_string, to_string, fields, page, page_size)
        docs = page_xml.findall(".//doc")

        for doc in docs:
            identifier = doc.find("./str[@name='identifier']").text
            print "Adding dataset for %s. " % identifier

            # Skip if it's already in the datasets graph
            if graphs.datasetExists(identifier):
                print "Dataset %s already in graph. Continuing." % identifier
                # continue

            # continue
            scimeta = dataone.getScientificMetadata(identifier, identifier_map, cache_dir, cache=True)

            if scimeta is None:
                print "Unable to get scimeta for %s. Skipping." % identifier
                continue

            records = processing.extractCreators(identifier, scimeta)

            # Add records and organizations
            people = [p for p in records if 'type' in p and p['type'] == 'person']
            organizations = [o for o in records if 'type' in o and o['type'] == 'organization']

            # Always do organizations first, so peoples' organization URIs exist
            for organization in organizations:
                organization = vld.validate(organization)
                graphs.addOrganization(organization)

            for person in people:
                person = vld.validate(person)
                graphs.addPerson(person)

            graphs.addDataset(doc, scimeta, formats_map)


    graphs.save()

    # Save settings
    # config['last_run'] = to_string
    # util.saveJSONFile(config, 'settings.json')

    return


if __name__ == "__main__":
    main()
