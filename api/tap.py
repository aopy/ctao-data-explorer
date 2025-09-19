import pyvo as vo
import requests
import numpy as np
import math
from astropy.table import Table
import traceback
import logging
logger = logging.getLogger(__name__)


def build_spatial_icrs_condition(ra: float, dec: float, radius_deg: float) -> str:
    """
    CONTAINS(CIRCLE) spatial filter in ICRS using s_ra/s_dec from ObsCore.
    """
    return (
        "1=CONTAINS(POINT('ICRS', s_ra, s_dec), "
        f"CIRCLE('ICRS', {float(ra)}, {float(dec)}, {float(radius_deg)}))"
    )

def build_time_overlap_condition(tstart_mjd_tt: float, tend_mjd_tt: float) -> str:
    """
    Half-open/overlap style constraint: any record overlapping [tstart, tend]
    """
    return f"t_min < {float(tend_mjd_tt)} AND t_max > {float(tstart_mjd_tt)}"

def build_where_clause(conditions: list[str]) -> str:
    """
    Join a list of WHERE snippets with AND, falling back to TRUE (1=1).
    """
    parts = [c.strip() for c in conditions if c and c.strip()]
    return " AND ".join(parts) if parts else "1=1"

def build_select_query(table: str, where: str, limit: int = 100, columns: str = "*") -> str:
    """
    Compose the final SELECT with WHERE.
    """
    return f"SELECT TOP {int(limit)} {columns} FROM {table} WHERE {where}"

def perform_query_with_conditions(fields, conditions: list[str], limit: int = 100):
    """
    Build a WHERE clause from `conditions`, compose the SELECT, execute, and return:
    (error_message_or_None, astropy_table_or_None, adql_query_string)
    """
    url = fields['tap_url']['value']
    obscore_table = fields['obscore_table']['value']
    timeout = 5

    error, astro_table = None, None
    query = ""

    try:
        t = Tap(url)
        t.connect(timeout)

        where = build_where_clause(conditions)  # <<< " AND ".join(mylist) used here
        query = build_select_query(obscore_table, where, limit=limit)

        logger.debug("Running ADQL Query: %s", query)
        exception, tap_results = t.query(query)

        if exception:
            error = f'Got exception with TAP query: {exception}'
        elif tap_results is None:
            error = 'TAP query succeeded but returned no results object.'
        else:
            astro_table = _process_tap_results(tap_results)
            if astro_table is None and error is None:
                error = "Failed processing TAP results after query."
    except Exception as outer_exception:
        error = f"Failed TAP operation: {outer_exception}"
        logger.exception("Error during TAP operation: %s",outer_exception)
        traceback.print_exc()
        astro_table = None

    logger.debug("Returning from perform_query_with_conditions: error=%s, table type=%s",
                 error, type(astro_table))
    return error, astro_table, query


def _process_tap_results(tap_results: vo.dal.TAPResults) -> Table | None:
    """Converts TAPResults to Astropy Table."""
    if tap_results is None:
        return None
    try:
        astro_table = tap_results.to_table()
        logger.debug("Converted TAPResults to Astropy Table with %s rows.", len(astro_table))
        return astro_table
    except Exception as convert_error:
        logger.exception(f"Error: Failed converting TAPResults: %s", convert_error)
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
        logger.debug("astropy_table_to_list: Received None table.")
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
                            logger.exception("Warning: Failed float(str()) conversion for col '%s', val '%s': %s",
                                             col, row[col], e)
                            try:
                                cell = float(row[col])
                                if math.isnan(cell) or math.isinf(cell): cell = None
                            except: cell = None
                else:
                    if cell is None or isinstance(cell, (np.void)): cell = None
                    else: cell = str(cell)
                row_data.append(cell)
            rows.append(row_data)
        logger.debug("astropy_table_to_list: Processed %s rows.", len(rows))
        return columns, rows
    except Exception as e:
        logger.exception("ERROR in astropy_table_to_list: %s", e)
        traceback.print_exc()
        return [],[]

def perform_coords_query(fields):
    conds = [
        build_spatial_icrs_condition(
            fields['target_raj2000']['value'],
            fields['target_dej2000']['value'],
            fields['search_radius']['value'],
        )
    ]
    return perform_query_with_conditions(fields, conds, limit=100)

def perform_time_query(fields):
    conds = [
        build_time_overlap_condition(
            fields['search_mjd_start']['value'],
            fields['search_mjd_end']['value'],
        )
    ]
    return perform_query_with_conditions(fields, conds, limit=100)

def perform_coords_time_query(fields):
    conds = [
        build_spatial_icrs_condition(
            fields['target_raj2000']['value'],
            fields['target_dej2000']['value'],
            fields['search_radius']['value'],
        ),
        build_time_overlap_condition(
            fields['search_mjd_start']['value'],
            fields['search_mjd_end']['value'],
        ),
    ]
    return perform_query_with_conditions(fields, conds, limit=100)
