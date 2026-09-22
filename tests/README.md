# Recipe tests

Every recipe in this repo, run as a subprocess against a stand-in API — the same
way a customer runs it, so argparse, the `__main__` entry point, file output and
exit codes are all exercised.

```sh
pip install -r ../python-sdk/requirements-dev.txt   # pytest
pytest                                             # Python recipes + FastAPI receiver
```

The mock API comes from the `python-sdk` checkout, which is the reference
implementation of the API contract. It is expected beside this repo; point
elsewhere with `pytest --sdk-path /path/to/python-sdk`.

The Express webhook receiver additionally needs a Node harness, and is skipped
without one:

```sh
cd tests/node_harness && npm install
```

## Why the recipes need `SPEECHREVOLUTIONS_BASE_URL`

Recipes construct `SpeechRevolutions()` with no arguments, as a reader should.
Without an environment override there is no way to point them anywhere but
production — which is why none of this was testable before. The SDKs now read
`SPEECHREVOLUTIONS_BASE_URL`, symmetric with the API key.
That is also what you want for staging or an egress proxy.
