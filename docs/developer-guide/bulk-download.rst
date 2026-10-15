=========================
Bulk download from Basket
=========================

Download the primary data product for each observation in a basket using a
standalone Python script. Duplicate file references are removed. The configured
default limit is 100 unique file references.

How to use
----------

1. Sign in, open **Basket**, and select a basket group.
2. Click **Download script**. Check the displayed expiry and any preparation errors.
3. From the folder containing the script, run:

   .. code-block:: bash

      python3 ctao-download-20260925-143000.py --output-dir ./ctao-data

Use the exact command shown in the Basket info box. Script names use
``ctao-download-YYYYMMDD-HHMMSS.py`` with a UTC timestamp. If your browser renames
the saved file, use that actual filename instead.

Python 3.9 or newer is required; no additional packages are needed. Run the script
promptly. If credentials expire, generate a new script from Basket.

Files download sequentially, with up to three attempts for transient failures.
Use ``--attempts 1`` through ``--attempts 5`` to change this. Failed transfers restart
from the beginning; partial-file resume is not supported.

Downloaded files retain their archive basenames (for example, ``dl3-*.fits.gz``).
Unsafe filename characters are replaced. If multiple entries
resolve to the same basename, those entries are reported as conflicts; download
them separately into different directories.

Existing files are left untouched and reported as unverified. To download them
again, choose a new output directory or explicitly remove the existing files.
Each completed run writes a ``download-report-*.json`` containing ``script_name``,
``executed_at`` (UTC run start time), and a ``results`` list with per-file outcomes. Exit status is zero only
when every requested file downloads successfully in that run; failed, unprepared,
or existing files produce a nonzero status.

Authentication and security
---------------------------

The existing auth relay and IAM token exchange prepare temporary storage tokens
when the script is generated. The script then downloads directly from storage;
it does not call the download service or refresh credentials while running.

.. warning::

   Keep the script private. It contains bearer credentials. Do not share it,
   commit it to Git, or attach it to issues. Delete it when finished.

- No session cookie, user IAM access token, refresh token, or client secret is
  embedded. One-hour validity is requested, but the actual expiry is set by IAM.
- Tokens are sent in Authorization headers. HTTPS redirects are supported with
  bounded hops; the bearer header is removed when the host or port changes.
  HTTP downgrades are rejected and TLS certificate verification remains enabled.
- Download permission comes from IAM/storage policy, not basket membership.
  ``DOWNLOAD_TOKEN_EXCHANGE_SCOPE`` and ``DOWNLOAD_TOKEN_EXCHANGE_AUDIENCE`` override
  URL-derived values.
- Script responses disable caching. Download reports omit tokens and URLs.

Unresolved observation metadata stops generation. If only some files are authorized,
the script contains those files and the interface lists the exclusions.

Deployment notes
----------------

Rebuild the frontend and download service; no database migration is needed.
Verify the LFN prefix mapping and allowed storage hosts. Review the auth relay and
proxy timeouts: preparing a large basket may exceed the default 30-second relay
timeout.

The output filesystem must support hard links. Transfers check available size
information, but do not verify a storage-provided cryptographic checksum.
