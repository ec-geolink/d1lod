"""A Repository is a light-weight wrapper around a Sesame Repository API:

    http://rdf4j.org/sesame/2.7/docs/system.docbook?view#The_Sesame_Server_REST_API
    http://docs.s4.ontotext.com/display/S4docs/Fully+Managed+Database#FullyManagedDatabase-cURL%28dataupload%29
"""

import requests

class Repository:
    def __init__(self, store, name, ns={}):
        self.store = store
        self.name = name
        self.ns = ns
        self.endpoints = {
            'size': 'http://%s:%s/openrdf-sesame/repositories/%s/size' % (self.store.host, self.store.port, self.name),
            'export': 'http://%s:%s/openrdf-workbench/repositories/%s/export' % (self.store.host, self.store.port, self.name),
            'statements': 'http://%s:%s/openrdf-sesame/repositories/%s/statements' % (self.store.host, self.store.port, self.name),
            'namespaces': 'http://%s:%s/openrdf-sesame/repositories/%s/namespaces' % (self.store.host, self.store.port, self.name),
            'query': 'http://%s:%s/openrdf-sesame/repositories/%s' % (self.store.host, self.store.port, self.name),
            'update': 'http://%s:%s/openrdf-sesame/repositories/%s/statements' % (self.store.host, self.store.port, self.name),
        }

        # Check if repository exists. Create if it doesn't.
        if not self.exists():
            print "Creating repository '%s'." % name
            self.store.createRepository(name)

        existing_namespaces = self.namespaces()

        for prefix in ns:
            if prefix in existing_namespaces:
                continue

            print "Adding namespace: @prefix %s: <%s>" % (prefix, ns[prefix])
            self.addNamespace(prefix, ns[prefix])

    def __str__(self):
        return "Repository: '%s'" % self.name

    def exists(self):
        repo_ids = self.store.repositories()

        if repo_ids is None:
            return False

        if self.name in repo_ids:
            return True
        else:
            return False

    def size(self):
        endpoint = self.endpoints['size']
        r = requests.get(endpoint)

        if r.text.startswith("Unknown repository:"):
            return -1

        return int(r.text)

    def clear(self):
        self.delete('?s', '?p', '?o')

    def export(self, format='turtle'):
        if format != 'turtle':
            print "Format of %s is not yet implemented. Doing nothing." % format
            return

        endpoint = "/".join(["http://" + self.store.host + ":" + self.store.port, "openrdf-workbench", "repositories", self.name, "export"])

        headers = {
            'Accept': 'text/turtle'
        }

        r = requests.get(endpoint, params=headers)

        return r.text

    def statements(self):
        headers = { "Accept": "application/json" }
        endpoint = self.endpoints['statements']

        query_params = {
            'infer': 'false'
        }

        r = requests.get(endpoint, params = query_params)

        return r.text

    def namespaces(self):
        """
        Return the namespaces for the repository as a Dict.
        """

        headers = { "Accept": "application/json" }
        endpoint = self.endpoints['namespaces']

        r = requests.get(endpoint, headers=headers)

        if r.text.startswith("Unknown repository:"):
            return {}

        response =  r.json()
        bindings = response['results']['bindings']

        namespaces = {}

        for binding in bindings:
            prefix = binding['prefix']['value']
            namespace = binding['namespace']['value']

            namespaces[prefix] = namespace

        return namespaces

    def getNamespace(self, namespace):
        endpoint = self.endpoints['namespaces']
        r = requests.get(endpoint)

        return r.text

    def addNamespace(self, namespace, value):
        endpoint = self.endpoints['namespaces'] + '/' + namespace
        print endpoint
        r = requests.put(endpoint, data = value)

        if r.status_code != 204:
            print "Adding namespace failed."
            print "Status Code: %d." % r.status_code
            print r.text

    def removeNamespace(self, namespace):
        endpoint = self.endpoints['namespaces']

        r = requests.delete(endpoint)

    def namespacePrefixString(self):
        ns = self.namespaces()

        ns_strings = []

        for key in ns:
            ns_strings.append("PREFIX %s:<%s>" % (key, ns[key]))

        return "\n".join(ns_strings)

    def query(self, query):
        headers = {
            "Accept": "application/sparql-results+json",
            "Content-Type": 'application/x-www-form-urlencoded'
        }

        endpoint = self.endpoints['query']
        query = query.strip()

        r = requests.post(endpoint, headers=headers, data={ 'query' : query })

        if r.status_code != 204:
            print "SPARQL Query failed. Status was not 204 as expected."
            print r.status_code
            print r.text

        print r.text
        return


    def update(self, query_string):
        headers = { 'Content-Type': 'application/x-www-form-urlencoded' }
        endpoint = self.endpoints['update']
        sparql_query = query_string.strip()

        r = requests.post(endpoint, headers=headers, data={ 'update': sparql_query })

        if r.status_code != 204:
            print "SPARQL UPDATE failed. Status was not 204 as expected."
            print r.text

    def all(self):
        headers = { "Accept": "application/json" }
        endpoint = self.endpoints['query']

        sparql_query = """
        %s
        SELECT * WHERE { ?s ?p ?o }
        """ % self.namespacePrefixString()

        sparql_query = sparql_query.strip()

        query_params = {
            'action': 'exec',
            'queryLn': 'SPARQL',
            'query': sparql_query,
            'infer': 'false'
        }

        r = requests.get(endpoint, params = query_params, headers=headers)
        response = r.json()
        results = self.processJSONResponse(response)

        return results

    def find(self, s, p, o):
        headers = { "Accept": "application/json" }
        endpoint = self.endpoints['query']

        sparql_query = """
        %s
        SELECT *
        WHERE { %s %s %s }
        """ % (self.namespacePrefixString(), s, p, o)

        sparql_query = sparql_query.strip()

        print sparql_query
        query_params = {
            'action': 'exec',
            'queryLn': 'SPARQL',
            'query': sparql_query,
            'infer': 'false'
        }

        r = requests.get(endpoint, params = query_params, headers=headers)
        response = r.json()
        results = self.processJSONResponse(response)

        return results

    def insert(self, s, p, o):
        endpoint = self.endpoints['update']

        sparql_query = """
        %s
        INSERT DATA { %s %s %s }
        """ % (self.namespacePrefixString(), s, p, o)
        sparql_query = sparql_query.strip()

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        # print sparql_query

        query_params = {
            'queryLn': 'SPARQL',
            'update': sparql_query,
        }

        r = requests.post(endpoint, headers=headers, data = query_params)

    def delete(self, s, p, o):
        endpoint = self.endpoints['update']

        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }

        sparql_query = """
        %s
        DELETE { ?s ?p ?o }
        WHERE { %s %s %s }
        """ % (self.namespacePrefixString(), s, p, o)

        sparql_query = sparql_query.strip()

        query_params = {
            'queryLn': 'SPARQL',
            'update': sparql_query,
        }

        r = requests.post(endpoint, headers=headers, data = query_params)

    def processJSONResponse(self, response):
        results = []

        if 'results' not in response or 'bindings' not in response['results']:
            return results

        variable_names = response['head']['vars']

        for binding in response['results']['bindings']:
            row = {}

            for var in variable_names:
                value_type = binding[var]['type']

                if value_type == "uri":
                    row[var] = "<%s>" % binding[var]['value']
                else:
                    row[var] = binding[var]['value']

            results.append(row)

        return results
