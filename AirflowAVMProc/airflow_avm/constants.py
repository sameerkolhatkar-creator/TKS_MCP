"""Shared constants for Airflow AVM process operations."""

from __future__ import annotations

PROCESS_TYPES = [
    "AGENT",
    "IMDG_LOCATOR",
    "IMDG_PWINFO",
    "IMDG_RTN",
    "IMDG_SERVER",
    "HB_IMDG_LOADER",
    "HB_FETCHER_LAZY",
    "RCND",
    "IMDG_VIEWER",
    "MASD",
    "AEM_CM",
    "UHI",
    "JAP",
    "APP_SERVER",
    "AC",
    "IMDG_DELTA",
    "IMDG_ALL",
]

TABLE_COLUMNS = ("sid", "processType", "processName", "status", "host")

DEFAULT_WAIT_SECONDS = 30
DEFAULT_PAGE_SIZE = 500
COOKIE_JAR = "/tmp/airflow.cj"
