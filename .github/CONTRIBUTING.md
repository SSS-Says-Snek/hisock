# Notes

1. When building for PyPI, use the following commands:
   ```shell
   $ py -3.9 setup.py sdist bdist_wheel
   $ twine upload dist/*
   ```