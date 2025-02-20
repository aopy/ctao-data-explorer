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
    Convert a TAPResults table to a list of lists suitable for JSON conversion,
    along with the list of column names.
    """
    # print("Available attributes:", dir(table))
    columns = table.fieldnames
    rows = []
    for row in table:
        row_data = []
        for col in columns:
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
    return columns, rows

def perform_coords_query(fields):
    """
    Perform a coordinate (cone search) query.
    """
    # Get URL of TAP server from fields
    url = fields['tap_url']['value']
    # Get name of obscore table from fields
    obscore_table = fields['obscore_table']['value']
    # Timeout for TAP server connection
    timeout = 5

    t = Tap(url)
    t.connect(timeout)

    # Construct ADQL query - cone search
    query = (
        "SELECT TOP 100 * FROM {} WHERE 1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
        "CIRCLE('ICRS', {}, {}, {}))".format(
            obscore_table,
            fields['target_raj2000']['value'],
            fields['target_dej2000']['value'],
            fields['search_radius']['value']
        )
    )
    exception, res_table = t.query(query)
    if exception is None:
        error = None
    else:
        error = f'Got exception with TAP query: {exception}'
    return error, res_table

def perform_time_query(fields):
    """
    Perform a time‑only query.
    Expects fields to contain 'search_mjd_start' and 'search_mjd_end',
    which define the time window (in MJD) corresponding to the user’s day.
    """
    url = fields['tap_url']['value']
    obscore_table = fields['obscore_table']['value']
    timeout = 5

    t = Tap(url)
    t.connect(timeout)
    query = (
        "SELECT TOP 100 * FROM {} WHERE t_min < {} AND t_max > {}"
        .format(
            obscore_table,
            fields['search_mjd_end']['value'],
            fields['search_mjd_start']['value']
        )
    )
    exception, res_table = t.query(query)
    if exception is None:
        error = None
    else:
        error = f'Got exception with TAP query: {exception}'
    return error, res_table

def perform_coords_time_query(fields):
    """
    Perform a query that combines a cone search with a time filter.
    Expects fields to include both coordinate keys and time keys.
    """
    url = fields['tap_url']['value']
    obscore_table = fields['obscore_table']['value']
    timeout = 5

    t = Tap(url)
    t.connect(timeout)
    query = (
        "SELECT TOP 100 * FROM {} WHERE 1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
        "CIRCLE('ICRS', {}, {}, {})) AND t_min < {} AND t_max > {}"
        .format(
            obscore_table,
            fields['target_raj2000']['value'],
            fields['target_dej2000']['value'],
            fields['search_radius']['value'],
            fields['search_mjd_end']['value'],
            fields['search_mjd_start']['value']
        )
    )
    exception, res_table = t.query(query)

    if exception is None:
        error = None
    else:
        error = f'Got exception with TAP query: {exception}'
    return error, res_table
