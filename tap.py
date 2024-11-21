import pyvo as vo
import requests
import numpy as np
import math

class CTAOHTTPAdapter(requests.adapters.HTTPAdapter):
    """
    A subclass of HTTPAdapter to handle timeouts
    """

    def __init__(self, *args, **kwargs):
        self.timeout = kwargs.pop("timeout", None)
        super().__init__(*args, **kwargs)

    def send(self, *args, **kwargs):
        kwargs["timeout"] = self.timeout
        return super().send(*args, **kwargs)

class Tap:
    """
    Class to handle TAP/ADQL queries
    """

    def __init__(self, url):
        self.url = url
        self.conn = None

    def connect(self, timeout=5):
        """
        Retrieve a connection to the TAP server, setting a timeout for the connection
        """
        session = requests.Session()
        adapter = CTAOHTTPAdapter(timeout=timeout)
        session.mount('https://', adapter)
        session.mount('http://', adapter)
        self.conn = vo.dal.TAPService(self.url, session=session)

    def query(self, query):
        """
        Launch a TAP query
        """
        table = None
        exception = None
        try:
            table = self.conn.search(query)
        except Exception as e:
            exception = e
        return exception, table

def astropy_table_to_list(table):
    """
    Convert an astropy table to a list of lists suitable for JSON conversion
    """
    rows = []
    for row in table:
        row_data = []
        for col in table.fieldnames:
            cell = row[col]
            if isinstance(cell, (bytes, np.bytes_)):
                cell = cell.decode('utf-8')
            elif isinstance(cell, (int, np.integer)):
                cell = int(cell)
            elif isinstance(cell, (float, np.floating)):
                cell = float(cell)
                if math.isnan(cell):
                    cell = None
            else:
                cell = str(cell)
            row_data.append(cell)
        rows.append(row_data)
    return rows

def perform_query(fields):
    """
    Perform TAP query and return error (None if OK) and result table
    """
    # URL of TAP server
    url = 'http://voparis-tap-he.obspm.fr/tap'
    # Name of obscore table on the TAP server
    obscore_table = 'hess_dr.obscore_sdc'
    # Timeout for TAP server connection
    timeout = 5

    t = Tap(url)
    t.connect(timeout)

    # Construct ADQL query - cone search
    query = ("SELECT TOP 100 * FROM {} WHERE 1=CONTAINS(POINT('ICRS',s_ra,s_dec),"
             "CIRCLE('ICRS',{},{},{}))".format(
                 obscore_table,
                 fields['target_raj2000']['value'],
                 fields['target_dej2000']['value'],
                 fields['search_radius']['value']))

    exception, res_table = t.query(query)

    if exception is None:
        error = None
    else:
        error = f'Got exception with TAP query: {exception}'
    return error, res_table
