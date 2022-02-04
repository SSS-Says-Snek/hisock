## Contributing Guidelines

1. Please follow PEP-8. Code is more often read than written, so it is extremely recommended for you to format your code with `black` after contributing.
2. Follow PEP-20 (The Zen of Python) as well.
3. Follow the Code of Conduct.

## Notes

1. When building for PyPI, use the following commands:
   ```shell
   $ py -3.9 setup.py sdist bdist_wheel
   $ twine upload dist/*
  ```
