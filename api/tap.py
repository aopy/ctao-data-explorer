import pyvo as vo
import requests
import numpy as np
import math
from astropy.table import Table
import traceback


def _process_tap_results(tap_results: vo.dal.TAPResults) -> Table | None:
    """Converts TAPResults to Astropy Table."""
    if tap_results is None:
        return None
    try:
        astro_table = tap_results.to_table()
        print(f"DEBUG: Converted TAPResults to Astropy Table with {len(astro_table)} rows.")
        return astro_table
    except Exception as convert_error:
        print(f"Error: Failed converting TAPResults: {convert_error}")
        traceback.print_exc()
        return None


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

def astropy_table_to_list(table: Table | None):
    """
    Convert an Astropy Table object to a list of lists suitable for JSON conversion,
    along with the list of column names.
    """
    if table is None:
        print("DEBUG astropy_table_to_list: Received None table.")
        return [], []

    try:
        columns = table.colnames
        rows = []
        for row in table:
            row_data = []
            for col in columns:
                cell = row[col]
                if isinstance(cell, np.ma.core.MaskedConstant): cell = None
                elif isinstance(cell, (bytes, np.bytes_)):
                    try: cell = cell.decode('utf-8')
                    except UnicodeDecodeError: cell = repr(cell)
                elif isinstance(cell, (int, np.integer)):
                    cell = int(cell)
                elif isinstance(cell, (float, np.floating)):
                    if np.isnan(cell) or np.isinf(cell): cell = None
                    else:
                        try:
                            cell = float(cell.__str__()) # temporary fix for floating point issue
                            if math.isnan(cell) or math.isinf(cell): cell = None
                        except Exception as e:
                            print(f"Warning: Failed float(str()) conversion for col '{col}', val '{row[col]}': {e}")
                            try:
                                cell = float(row[col])
                                if math.isnan(cell) or math.isinf(cell): cell = None
                            except: cell = None
                else:
                    if cell is None or isinstance(cell, (np.void)): cell = None
                    else: cell = str(cell)
                row_data.append(cell)
            rows.append(row_data)
        print(f"DEBUG astropy_table_to_list: Processed {len(rows)} rows.")
        return columns, rows
    except Exception as e:
        print(f"ERROR in astropy_table_to_list: {e}")
        traceback.print_exc()
        return [],[]


def perform_coords_query(fields):
    """Perform coordinate query, return error, Astropy Table, query string."""
    url, obscore_table, timeout = fields['tap_url']['value'], fields['obscore_table']['value'], 5
    error, astro_table = None, None
    query = ""

    try:
        t = Tap(url)
        t.connect(timeout)
        query = (
            "SELECT TOP 100 * FROM {} WHERE 1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
            "CIRCLE('ICRS', {}, {}, {}))".format(
                obscore_table, fields['target_raj2000']['value'],
                fields['target_dej2000']['value'], fields['search_radius']['value']
            )
        )
        print(f"DEBUG: Running ADQL Query: {query}")
        exception, tap_results = t.query(query)

        if exception: error = f'Got exception with TAP query: {exception}'
        elif tap_results is None: error = 'TAP query succeeded but returned no results object.'
        else:
            astro_table = _process_tap_results(tap_results)
            if astro_table is None and error is None:
                error = "Failed processing TAP results after query."

    except Exception as outer_exception:
        error = f"Failed TAP operation: {outer_exception}"
        print(f"Error during TAP operation: {outer_exception}")
        traceback.print_exc()
        astro_table = None

    print(f"DEBUG Returning from perform_coords_query: error={error}, table type={type(astro_table)}")

    return error, astro_table, query

def perform_time_query(fields):
    """Perform time query, return error, Astropy Table, query string."""
    url, obscore_table, timeout = fields['tap_url']['value'], fields['obscore_table']['value'], 5
    error, astro_table = None, None
    query = ""

    try:
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
        print(f"DEBUG: Running ADQL Query: {query}")
        exception, tap_results = t.query(query)

        if exception: error = f'Got exception with TAP query: {exception}'
        elif tap_results is None: error = 'TAP query succeeded but returned no results object.'
        else:
            astro_table = _process_tap_results(tap_results)
            if astro_table is None and error is None:
                error = "Failed processing TAP results after query."

    except Exception as outer_exception:
        error = f"Failed TAP operation: {outer_exception}"
        print(f"Error during TAP operation: {outer_exception}")
        traceback.print_exc()
        astro_table = None

    print(f"DEBUG Returning from perform_time_query: error={error}, table type={type(astro_table)}")
    return error, astro_table, query


def perform_coords_time_query(fields):
    """Perform coordinate and time query, return error, Astropy Table, query string."""
    url, obscore_table, timeout = fields['tap_url']['value'], fields['obscore_table']['value'], 5
    error, astro_table = None, None
    query = ""

    try:
        t = Tap(url)
        t.connect(timeout)
        query = (
           "SELECT TOP 100 * FROM {} WHERE 1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
           "CIRCLE('ICRS', {}, {}, {})) AND t_min < {} AND t_max > {}"
           .format(
               obscore_table, fields['target_raj2000']['value'],
               fields['target_dej2000']['value'], fields['search_radius']['value'],
               fields['search_mjd_end']['value'], fields['search_mjd_start']['value']
           )
        )
        print(f"DEBUG: Running ADQL Query: {query}")
        exception, tap_results = t.query(query)

        if exception: error = f'Got exception with TAP query: {exception}'
        elif tap_results is None: error = 'TAP query succeeded but returned no results object.'
        else:
            astro_table = _process_tap_results(tap_results)
            if astro_table is None and error is None:
                error = "Failed processing TAP results after query."

    except Exception as outer_exception:
        error = f"Failed TAP operation: {outer_exception}"
        print(f"Error during TAP operation: {outer_exception}")
        traceback.print_exc()
        astro_table = None

    print(f"DEBUG Returning from perform_coords_time_query: error={error}, table type={type(astro_table)}")
    return error, astro_table, query
