"""Test package for the published skill bundles.

This file exists so that a bare ``python3 -m unittest discover`` finds both suites.

Without it, unittest's default discovery walks the top-level directory and imports
``test_*.py`` as top-level modules; these modules import their neighbours by the
``tests.`` package path, so discovery silently finds nothing and reports
``NO TESTS RAN`` — a green-looking result that proves nothing. Being a package makes the
default command equivalent to the explicit ``-s tests`` form the README documents.
"""
