from pprint import pprint
from operator import itemgetter 

servers = [{'Id': u'd27a4f681a5746d79ee0bb29b52aad55', 'DateLastAccessed': '2019-12-02T21:53:55Z', 'Name': u'Testing Server', 'address': u'http://jelly.local'}, {'Id': u'd27a4f681a5746d79ee0bb29b52aad56', 'DateLastAccessed': '2019-12-27T20:53:55Z', 'Name': u'Other Testing Server', 'address': u'http://jelly2.local'}]
pprint(servers)
servers.sort(key=itemgetter('DateLastAccessed'), reverse=True)
pprint(servers)